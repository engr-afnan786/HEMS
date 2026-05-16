"""
HEMS Parametric Experiments v4.0
7 experiments from Doc3 + billing mode comparison from Doc2
"""

import numpy as np
import time
from .parameters import (
    HEMSParameters, generate_load_profile, generate_solar_profile,
    get_tariff_vector, RHO_RANGE, BATTERY_SIZES, SOLAR_SIZES,
    TOU_RATIOS, DEGRADATION_COSTS, C_OFFPEAK
)
from .solver import run_optimization, solve_nominal_lp, compare_solvers
from .baselines import run_all_baselines


def _safe(params):
    r = run_optimization(params)
    return r.net_cost() if r.feasible else None, r.feasible


def exp_robustness(season='summer', rho_values=None):
    """Exp 1: Pareto frontier — cost vs robustness ρ."""
    rho_values = rho_values or RHO_RANGE
    results = []
    print("\n═══ Exp 1: Robustness Sweep ═══")
    print(f"{'ρ':>6} {'Cost':>12} {'Status':>12}")
    print("-" * 35)

    base_cost = None
    for rho in rho_values:
        p = HEMSParameters(season=season, rho=rho)
        cost, ok = _safe(p)
        if ok and rho == 0:
            base_cost = cost
        pct = (cost - base_cost) / base_cost * 100 if (base_cost and cost) else 0
        status = "optimal" if ok else "infeasible"
        print(f"{rho:>6.1f} {(cost or 0):>12.2f}  +{pct:.2f}% {status:>12}")
        results.append({'rho': rho, 'cost': cost, 'feasible': ok, 'pct_increase': pct})
    return results


def exp_battery_sizing(season='summer', sizes=None):
    """Exp 2: Marginal value of battery storage."""
    sizes = sizes or BATTERY_SIZES
    results = []
    print("\n═══ Exp 2: Battery Sizing ═══")

    # Reference: no battery
    p_ref = HEMSParameters(season=season, battery_size=0.01)
    p_ref.Pc_max = 0
    p_ref.Pd_max = 0
    ref_cost, _ = _safe(p_ref)

    for sz in sizes:
        p = HEMSParameters(season=season, battery_size=max(sz, 0.01))
        if sz == 0:
            p.Pc_max = 0
            p.Pd_max = 0
        r = run_optimization(p)
        cost = r.net_cost() if r.feasible else None
        savings = (ref_cost - cost) if (ref_cost and cost) else None
        cycles = ((r.p_charge.sum() + r.p_discharge.sum()) / (2 * max(sz, 0.1))
                  if r.feasible else None)
        results.append({'E_max': sz, 'cost': cost, 'savings': savings,
                        'cycles': cycles, 'feasible': r.feasible})
    return results, ref_cost


def exp_tou_ratio(season='summer', ratios=None):
    """Exp 3: TOU ratio → arbitrage profitability."""
    ratios = ratios or TOU_RATIOS
    results = []
    print("\n═══ Exp 3: TOU Ratio Sweep ═══")

    for ratio in ratios:
        tariff_mod = np.full(24, C_OFFPEAK)
        tariff_mod[18:22] = C_OFFPEAK * ratio
        p = HEMSParameters(season=season)
        p.tariff = tariff_mod
        cost, ok = _safe(p)
        results.append({'ratio': ratio, 'peak_rate': C_OFFPEAK*ratio,
                        'cost': cost, 'feasible': ok})
    return results


def exp_solar_capacity(season='summer', sizes=None):
    """Exp 4: Optimal PV-battery pairing."""
    sizes = sizes or SOLAR_SIZES
    results = []
    print("\n═══ Exp 4: Solar Capacity Sweep ═══")

    for cap in sizes:
        p = HEMSParameters(season=season, solar_capacity=cap)
        r = run_optimization(p)
        cost = r.net_cost() if r.feasible else None
        total_solar = p.p_pv_mean.sum()
        self_use = total_solar - r.p_grid_export.sum() if r.feasible else 0
        self_pct = self_use / max(total_solar, 0.01) * 100
        results.append({'PV_rated': cap, 'cost': cost,
                        'self_use_pct': round(self_pct, 1), 'feasible': r.feasible})
    return results


def exp_seasonal():
    """Exp 5: Summer vs winter strategy comparison."""
    results = {}
    print("\n═══ Exp 5: Seasonal Comparison ═══")

    for season in ['summer', 'winter']:
        p = HEMSParameters(season=season)
        r = run_optimization(p)
        print(f"\n  {season.upper()}:")
        print(f"    Load:   {p.p_load.sum():.1f} kWh/day")
        print(f"    Solar:  {p.p_pv_mean.sum():.1f} kWh/day")
        print(f"    Cost:   PKR {r.net_cost():.2f}/day" if r.feasible else "    INFEASIBLE")
        results[season] = {
            'result': r,
            'load':   p.p_load,
            'solar':  p.p_pv_mean,
            'cost':   r.net_cost() if r.feasible else None,
            'p_grid_plus': r.p_grid_import.tolist() if r.feasible else [],
            'soc':    r.soc.tolist() if r.feasible else [],
            'feasible': r.feasible
        }
    return results


def exp_degradation(season='summer', costs=None):
    """Exp 6: Degradation cost λ vs cycling."""
    costs = costs or DEGRADATION_COSTS
    results = []
    print("\n═══ Exp 6: Degradation Cost Sweep ═══")

    for lam in costs:
        p = HEMSParameters(season=season, custom_params={'lam': lam})
        r = run_optimization(p)
        throughput = (r.p_charge.sum() + r.p_discharge.sum()) if r.feasible else 0
        cycles = throughput / (2 * 13.5)
        results.append({'lambda': lam, 'cost': r.net_cost() if r.feasible else None,
                        'cycling_kwh': round(throughput, 2),
                        'cycles': round(cycles, 2), 'feasible': r.feasible})
    return results


def exp_solver_comparison(season='summer'):
    """Exp 7: ECOS vs SCS vs OSQP vs CLARABEL (from Doc3)."""
    p = HEMSParameters(season=season, rho=0.0)
    results = compare_solvers(p, solvers=['ECOS', 'SCS', 'OSQP', 'CLARABEL'])
    return {k: {'cost': v.net_cost(), 'time': v.solve_time,
                'status': v.status, 'feasible': v.feasible}
            for k, v in results.items()}


def exp_billing_modes(season='summer'):
    """Policy experiment: net vs gross vs capacity tax."""
    results = {}
    for mode in ['net_metering', 'gross_metering', 'capacity_tax']:
        p = HEMSParameters(season=season, billing_mode=mode)
        r = run_optimization(p)
        results[mode] = {
            'cost':           r.net_cost() if r.feasible else None,
            'export_revenue': r.export_revenue,
            'capacity_tax':   r.capacity_tax,
            'feasible':       r.feasible
        }
    return results


def run_all_experiments(season='summer'):
    """Master function: run all 8 experiments."""
    print("╔══════════════════════════════════════════╗")
    print("║  HEMS v4.0 — Complete Experiment Suite  ║")
    print("╚══════════════════════════════════════════╝")

    p_base = HEMSParameters(season=season)
    print(f"\n  Season: {season}")
    print(f"  Daily load:  {p_base.p_load.sum():.1f} kWh")
    print(f"  Daily solar: {p_base.p_pv_mean.sum():.1f} kWh")

    return {
        'exp1_robustness':  exp_robustness(season),
        'exp2_battery':     exp_battery_sizing(season),
        'exp3_tou':         exp_tou_ratio(season),
        'exp4_solar':       exp_solar_capacity(season),
        'exp5_seasonal':    exp_seasonal(),
        'exp6_degradation': exp_degradation(season),
        'exp7_solvers':     exp_solver_comparison(season),
        'exp8_billing':     exp_billing_modes(season),
        'baselines':        run_all_baselines(p_base),
        'optimal':          run_optimization(p_base)
    }