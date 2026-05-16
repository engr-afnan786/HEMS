from flask import Blueprint, request, jsonify
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.parameters import HEMSParameters
from src.solver import run_optimization, verify_kkt, compare_solvers, HEMSResult
from src.baselines import run_all_baselines
from src.experiments import run_all_experiments
from src.dual_analysis import analyze_duals
from backend.utils.helpers import sanitize
import numpy as np

opt_bp = Blueprint('opt', __name__)


def _get_params(body: dict) -> HEMSParameters:
    return HEMSParameters(
        season          = body.get('season', 'summer'),
        use_ev          = body.get('use_ev', False),
        use_gst         = body.get('use_gst', True),
        use_fca         = body.get('use_fca', True),
        battery_size    = float(body.get('battery_size', 13.5)),
        solar_capacity  = float(body.get('solar_capacity', 10.0)),
        rho             = float(body.get('rho', 1.0)),
        billing_mode    = body.get('billing_mode', 'net_metering'),
        use_loadshedding= body.get('use_loadshedding', True)
    )


def _result_to_dict(res: HEMSResult) -> dict:
    """Convert HEMSResult dataclass to API dict."""
    return {
        'status':               res.status,
        'feasible':             res.feasible,
        'fallback':             res.fallback,
        'solver':               res.solver_used,
        'problem_class':        res.problem_class,
        'total_cost_pkr':       round(res.net_cost(), 2),
        'import_cost_pkr':      round(res.import_cost, 2),
        'export_revenue_pkr':   round(res.export_revenue, 2),
        'degradation_cost_pkr': round(res.degradation_cost, 2),
        'demand_charge_pkr':    round(res.demand_cost, 2),
        'capacity_tax_pkr':     round(res.capacity_tax, 2),
        'P_peak':               round(res.peak_demand, 3),
        'simultaneous_cd_kwh':  round(res.simultaneous_cd_kwh, 4),
        'p_grid_plus':          res.p_grid_import.tolist(),
        'p_grid_minus':         res.p_grid_export.tolist(),
        'p_charge':             res.p_charge.tolist(),
        'p_discharge':          res.p_discharge.tolist(),
        'soc':                  res.soc.tolist(),
        'schedules': {
            'washing_machine': res.x_wash.tolist(),
            'water_heater':    res.x_heater.tolist(),
            'dishwasher':      res.x_dishwasher.tolist()
        },
        'energy_duals':  res.energy_balance_duals.tolist(),
        'G':             res.G.tolist(),
        'billing_mode':  res.billing_mode,
        'rho':           res.rho
    }


@opt_bp.route('/solve', methods=['POST'])
def solve():
    body = request.get_json(force=True) or {}
    try:
        params = _get_params(body)
        result = run_optimization(params)
        rdict  = _result_to_dict(result)
        rdict['params']        = params.to_dict()
        rdict['tariff']        = params.tariff.tolist()
        rdict['p_pv']          = params.p_pv_mean.tolist()
        rdict['p_load']        = params.p_load.tolist()
        rdict['dual_analysis'] = analyze_duals(result, params)
        return jsonify(sanitize(rdict))
    except Exception as e:
        return jsonify({'error': str(e), 'feasible': False}), 500


@opt_bp.route('/compare', methods=['POST'])
def compare():
    body = request.get_json(force=True) or {}
    try:
        params  = _get_params(body)
        optimal = run_optimization(params)
        blines  = run_all_baselines(params)
        duals   = analyze_duals(optimal, params)

        opt_dict = _result_to_dict(optimal)
        opt_dict['tariff'] = params.tariff.tolist()
        opt_dict['p_pv']   = params.p_pv_mean.tolist()
        opt_dict['p_load'] = params.p_load.tolist()

        savings = []
        if optimal.feasible:
            oc = optimal.net_cost()
            for b in blines:
                bc = b.get('total_cost_pkr', 0)
                savings.append({
                    'baseline':      b['name'],
                    'baseline_cost': bc,
                    'optimal_cost':  round(oc, 2),
                    'savings_pkr':   round(bc - oc, 2),
                    'savings_pct':   round((bc-oc)/bc*100, 1) if bc else 0,
                    'monthly_pkr':   round((bc-oc)*30, 0)
                })

        # KKT verification
        kkt_ok = verify_kkt(optimal, params.tariff) if optimal.feasible else False

        return jsonify(sanitize({
            'optimal':          opt_dict,
            'baselines':        blines,
            'savings_analysis': savings,
            'dual_analysis':    duals,
            'kkt_verified':     kkt_ok,
            'params':           params.to_dict()
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@opt_bp.route('/experiments', methods=['GET'])
def experiments():
    try:
        season = request.args.get('season', 'summer')
        results = run_all_experiments(season=season)

        # Convert HEMSResult objects to dicts
        if 'optimal' in results and isinstance(results['optimal'], HEMSResult):
            results['optimal'] = _result_to_dict(results['optimal'])
        for exp_key in ['exp5_seasonal']:
            if exp_key in results:
                for season_key in results[exp_key]:
                    d = results[exp_key][season_key]
                    if 'result' in d and isinstance(d['result'], HEMSResult):
                        d['result_dict'] = _result_to_dict(d['result'])
                        del d['result']   # not JSON serializable

        return jsonify(sanitize(results))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@opt_bp.route('/billing-comparison', methods=['POST'])
def billing_comparison():
    body = request.get_json(force=True) or {}
    results = {}
    for mode in ['net_metering', 'gross_metering', 'capacity_tax']:
        try:
            body['billing_mode'] = mode
            p = _get_params(body)
            r = run_optimization(p)
            results[mode] = {
                'cost':           round(r.net_cost(), 2) if r.feasible else None,
                'export_revenue': round(r.export_revenue, 2) if r.feasible else 0,
                'capacity_tax':   round(r.capacity_tax, 2),
                'feasible':       r.feasible
            }
        except Exception as e:
            results[mode] = {'error': str(e)}
    return jsonify(sanitize(results))


@opt_bp.route('/kkt-verify', methods=['POST'])
def kkt_verify():
    """Dedicated KKT verification endpoint."""
    body = request.get_json(force=True) or {}
    try:
        params = _get_params(body)
        result = run_optimization(params)
        if not result.feasible:
            return jsonify({'error': 'No feasible solution', 'kkt_ok': False})
        kkt_ok = verify_kkt(result, params.tariff)
        return jsonify({
            'kkt_ok':              kkt_ok,
            'energy_duals':        result.energy_balance_duals.tolist(),
            'soc_upper_duals':     result.soc_upper_duals.tolist(),
            'soc_lower_duals':     result.soc_lower_duals.tolist(),
            'charge_upper_duals':  result.charge_upper_duals.tolist(),
            'discharge_upper_duals': result.discharge_upper_duals.tolist()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500