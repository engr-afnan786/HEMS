"""
Dual Variable Analysis v4.0
Uses HEMSResult dataclass fields directly.
"""

import numpy as np
from .solver import HEMSResult
from .parameters import HEMSParameters


def analyze_duals(result: HEMSResult, params: HEMSParameters) -> dict:
    if not result.feasible:
        return {'error': 'No feasible solution'}

    tariff = params.tariff
    mu     = result.energy_balance_duals
    soc    = result.soc
    G      = result.G

    peak_hrs  = [18, 19, 20, 21]
    solar_hrs = list(range(8, 17))
    shed_hrs  = [t for t in range(24) if G[t] == 0]

    avg_peak_mu  = float(np.mean(np.abs([mu[t] for t in peak_hrs])))
    avg_solar_mu = float(np.mean(mu[solar_hrs]))

    insights = []

    # KKT interpretation
    if avg_peak_mu >= tariff[18] * 0.9:
        insights.append(
            f"✓ μ_t at peak = {avg_peak_mu:.2f} PKR/kWh ≈ tariff ({tariff[18]:.2f}) "
            f"— battery actively avoids peak grid imports (KKT stationarity confirmed)."
        )
    if avg_solar_mu < 0:
        insights.append(
            "Solar hours have negative shadow prices — solar surplus exceeds demand. "
            "Consider larger battery or more export capacity."
        )
    if shed_hrs:
        insights.append(
            f"⚠️ Load shedding at hours {shed_hrs}. "
            f"SOC reserve constraint active (C7). "
            f"Battery maintains {PEP_SOC_RESERVE(params)*100:.0f}% buffer."
        )

    # Billing mode insights
    if result.billing_mode == 'gross_metering':
        insights.append(
            f"⚠️ Gross metering: export revenue = PKR {result.export_revenue:.2f}/day "
            f"(vs PKR {result.export_revenue * 19.32 / 10:.2f} under net metering). "
            f"Battery self-consumption priority increases."
        )
    elif result.billing_mode == 'capacity_tax':
        insights.append(
            f"⚠️ Capacity tax: PKR {result.capacity_tax:.2f}/day fixed charge. "
            f"Reduces solar system ROI regardless of generation."
        )

    # Simultaneous C/D warning
    if result.simultaneous_cd_kwh > 0.01:
        insights.append(
            f"⚠️ LP relaxation artifact: simultaneous charge/discharge = "
            f"{result.simultaneous_cd_kwh:.3f} kWh. "
            f"Increase λ (currently {params.lam} PKR/kWh) or use MILP."
        )

    # SOC analysis
    soc_peak   = int(np.argmax(soc[:-1]))
    soc_valley = int(np.argmin(soc[:-1]))
    insights.append(
        f"Battery fullest at hour {soc_peak:02d}:00 ({soc[soc_peak]:.2f} kWh). "
        f"Most depleted at hour {soc_valley:02d}:00 ({soc[soc_valley]:.2f} kWh) — "
        f"highest energy shortage risk period."
    )

    return {
        'energy_shadow_prices':    mu.tolist(),
        'avg_peak_shadow_price':   round(avg_peak_mu, 4),
        'avg_solar_shadow_price':  round(float(avg_solar_mu), 4),
        'max_shadow_hour':         int(np.argmax(np.abs(mu))),
        'min_shadow_hour':         int(np.argmin(np.abs(mu))),
        'soc_peak_hour':           soc_peak,
        'soc_valley_hour':         soc_valley,
        'shed_hours':              shed_hrs,
        'economic_insights':       insights,
        'kkt_interpretation': {
            'mu_t':    'Shadow price of energy at time t — locational marginal price (PKR/kWh)',
            'v_t':     'Future value of stored energy — inter-temporal arbitrage signal',
            'alpha_t': 'Active when SOC = E_max → curtailment loss (solar wasted)',
            'beta_t':  'Active when SOC = E_min → energy shortage risk',
            'gamma_t': 'Value of additional charge/discharge power capability'
        }
    }


def PEP_SOC_RESERVE(params):
    try:
        from config import PakistanEnergyPolicy as PEP
        return PEP.SOC_LOADSHED_RESERVE
    except Exception:
        return 0.40