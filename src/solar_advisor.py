"""
HEMS Solar Investment Advisor v5.0
==================================
NEW MODULE — Recommends complete solar system configurations
based on user's budget, monthly consumption, and location.

Features:
- Budget-constrained system sizing
- Equipment recommendation (panels, inverters, batteries)
- On-grid / Off-grid / Hybrid comparison
- ROI & payback period calculation
- Net metering vs no-metering analysis
- Multiple scenarios ranked by payback time

Real Pakistan market prices (2026 Q1).
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ══════════════════════════════════════════════════════════════════
# PAKISTAN SOLAR MARKET DATABASE (2026 prices)
# ══════════════════════════════════════════════════════════════════

SOLAR_PANELS = [
    {"brand": "JA Solar", "model": "JAM72S30-545/MR", "watt": 545,
     "price_per_watt": 30, "efficiency": 21.3, "warranty_yrs": 25,
     "tier": 1, "type": "Mono PERC", "grade": "A"},
    {"brand": "JA Solar", "model": "JAM78S30-615/MR", "watt": 615,
     "price_per_watt": 32, "efficiency": 21.8, "warranty_yrs": 25,
     "tier": 1, "type": "Mono N-Type", "grade": "A"},
    {"brand": "Longi", "model": "Hi-Mo 6 LR5-72HBD-545", "watt": 545,
     "price_per_watt": 33, "efficiency": 21.5, "warranty_yrs": 25,
     "tier": 1, "type": "Mono PERC", "grade": "A"},
    {"brand": "Longi", "model": "Hi-Mo X6 LR5-72HTH-580", "watt": 580,
     "price_per_watt": 36, "efficiency": 22.5, "warranty_yrs": 30,
     "tier": 1, "type": "Mono HJT", "grade": "A"},
    {"brand": "Jinko", "model": "Tiger Neo N-Type 580W", "watt": 580,
     "price_per_watt": 34, "efficiency": 22.3, "warranty_yrs": 25,
     "tier": 1, "type": "Mono N-Type Bifacial", "grade": "A"},
    {"brand": "Canadian Solar", "model": "HiKu7 CS7N-665", "watt": 665,
     "price_per_watt": 33, "efficiency": 21.6, "warranty_yrs": 25,
     "tier": 1, "type": "Mono N-Type", "grade": "A"},
    {"brand": "Trina Solar", "model": "Vertex S+ TSM-440NEG9R", "watt": 440,
     "price_per_watt": 30, "efficiency": 22.2, "warranty_yrs": 25,
     "tier": 1, "type": "Mono N-Type", "grade": "A"},
]

INVERTERS = {
    "ongrid": [
        {"brand": "Sungrow", "model": "SG5.0RS", "kw": 5, "price": 120000,
         "type": "On-Grid", "warranty_yrs": 10, "efficiency": 98.4},
        {"brand": "Sungrow", "model": "SG8.0RS", "kw": 8, "price": 165000,
         "type": "On-Grid", "warranty_yrs": 10, "efficiency": 98.6},
        {"brand": "Sungrow", "model": "SG10RS", "kw": 10, "price": 195000,
         "type": "On-Grid", "warranty_yrs": 10, "efficiency": 98.6},
        {"brand": "Fronius", "model": "Primo 5.0-1", "kw": 5, "price": 180000,
         "type": "On-Grid", "warranty_yrs": 10, "efficiency": 98.1},
        {"brand": "Growatt", "model": "MIN 5000TL-X", "kw": 5, "price": 85000,
         "type": "On-Grid", "warranty_yrs": 5, "efficiency": 97.6},
        {"brand": "Growatt", "model": "MIN 10000TL-X", "kw": 10, "price": 140000,
         "type": "On-Grid", "warranty_yrs": 5, "efficiency": 97.8},
    ],
    "hybrid": [
        {"brand": "Sungrow", "model": "SH5.0RS", "kw": 5, "price": 220000,
         "type": "Hybrid", "warranty_yrs": 10, "efficiency": 97.8},
        {"brand": "Sungrow", "model": "SH8.0RS", "kw": 8, "price": 310000,
         "type": "Hybrid", "warranty_yrs": 10, "efficiency": 97.9},
        {"brand": "Sungrow", "model": "SH10RS", "kw": 10, "price": 380000,
         "type": "Hybrid", "warranty_yrs": 10, "efficiency": 97.9},
        {"brand": "Growatt", "model": "SPH 5000ES", "kw": 5, "price": 160000,
         "type": "Hybrid", "warranty_yrs": 5, "efficiency": 97.0},
        {"brand": "Inverex", "model": "Veyron II 6kW", "kw": 6, "price": 145000,
         "type": "Hybrid", "warranty_yrs": 3, "efficiency": 96.5},
        {"brand": "INVT", "model": "BN5048C", "kw": 5, "price": 130000,
         "type": "Hybrid", "warranty_yrs": 5, "efficiency": 96.8},
    ],
    "offgrid": [
        {"brand": "Inverex", "model": "Aerox 3.2kW", "kw": 3.2, "price": 65000,
         "type": "Off-Grid", "warranty_yrs": 2, "efficiency": 95.0},
        {"brand": "Growatt", "model": "SPF 5000ES", "kw": 5, "price": 110000,
         "type": "Off-Grid", "warranty_yrs": 5, "efficiency": 96.0},
    ]
}

BATTERIES = [
    {"brand": "Tesla", "model": "Powerwall 2", "kwh": 13.5, "price": 650000,
     "cycles": 5000, "warranty_yrs": 10, "type": "Li-ion NMC", "dod": 0.95},
    {"brand": "BYD", "model": "HVS 5.1", "kwh": 5.12, "price": 280000,
     "cycles": 6000, "warranty_yrs": 10, "type": "LFP", "dod": 0.96},
    {"brand": "BYD", "model": "HVS 10.2", "kwh": 10.24, "price": 520000,
     "cycles": 6000, "warranty_yrs": 10, "type": "LFP", "dod": 0.96},
    {"brand": "Pylontech", "model": "US3000C", "kwh": 3.55, "price": 145000,
     "cycles": 6000, "warranty_yrs": 10, "type": "LFP", "dod": 0.90},
    {"brand": "Pylontech", "model": "US5000 (x2)", "kwh": 9.6, "price": 380000,
     "cycles": 6000, "warranty_yrs": 10, "type": "LFP", "dod": 0.90},
    {"brand": "Narada", "model": "48NPFC100", "kwh": 4.8, "price": 110000,
     "cycles": 3500, "warranty_yrs": 5, "type": "LFP", "dod": 0.80},
    {"brand": "Tubular Lead-Acid", "model": "12V 200Ah (x4)", "kwh": 9.6,
     "price": 120000, "cycles": 1200, "warranty_yrs": 3,
     "type": "Lead-Acid", "dod": 0.50},
]

# Additional costs
INSTALLATION_COST_PER_KW = 8000      # PKR per kW installed
NET_METERING_SETUP = 135000          # PKR (green meter + AEDB fees)
WIRING_MOUNTING_FIXED = 30000        # PKR base
WIRING_PER_KW = 5000                 # PKR per kW
ANNUAL_MAINTENANCE_PER_KW = 3000     # PKR per kW per year

# Pakistan constants
AVG_PEAK_SUN_HOURS = 5.5             # Rawalpindi average
GRID_TARIFF_AVG = 55.0               # PKR/kWh effective average
ANNUAL_TARIFF_INCREASE = 0.12        # 12% annual increase
SYSTEM_DEGRADATION = 0.006           # 0.6% per year panel degradation


@dataclass
class SystemRecommendation:
    """A complete solar system configuration with financials."""
    system_type: str        # 'ongrid', 'hybrid', 'offgrid'
    system_kw: float
    panel: dict
    num_panels: int
    inverter: dict
    battery: Optional[dict]
    net_metering: bool

    # Costs
    panel_cost: float = 0
    inverter_cost: float = 0
    battery_cost: float = 0
    installation_cost: float = 0
    net_metering_cost: float = 0
    total_cost: float = 0

    # Generation
    daily_generation_kwh: float = 0
    monthly_generation_kwh: float = 0
    annual_generation_kwh: float = 0

    # Savings
    monthly_savings_pkr: float = 0
    annual_savings_pkr: float = 0
    payback_months: float = 0
    roi_10yr_pct: float = 0
    lifetime_savings_pkr: float = 0

    # Meta
    score: float = 0       # overall ranking score
    tag: str = ""           # e.g. "Best Value", "Premium", "Budget"


def estimate_monthly_bill(units_per_month: float) -> float:
    """Estimate monthly IESCO bill from consumption units."""
    if units_per_month <= 100:
        return units_per_month * 12.96
    elif units_per_month <= 200:
        return 100*12.96 + (units_per_month-100)*19.07
    elif units_per_month <= 300:
        return 100*12.96 + 100*19.07 + (units_per_month-200)*24.40
    elif units_per_month <= 500:
        return 100*12.96 + 100*19.07 + 100*24.40 + (units_per_month-300)*32.52
    elif units_per_month <= 700:
        return 100*12.96 + 100*19.07 + 100*24.40 + 200*32.52 + (units_per_month-500)*42.50
    else:
        return (100*12.96 + 100*19.07 + 100*24.40 + 200*32.52
                + 200*42.50 + (units_per_month-700)*55.0)


def size_system_from_load(monthly_units: float) -> float:
    """Calculate required PV system size from monthly consumption."""
    daily_kwh = monthly_units / 30.0
    # Account for system losses (inverter, wiring, soiling)
    system_kw = daily_kwh / (AVG_PEAK_SUN_HOURS * 0.82)
    return round(system_kw * 2) / 2  # round to nearest 0.5 kW


def recommend_systems(
    monthly_units: float,
    budget_pkr: float,
    has_loadshedding: bool = True,
    wants_battery: Optional[bool] = None,  # None = auto-decide
    location: str = "Rawalpindi"
) -> List[SystemRecommendation]:
    """
    Generate ranked solar system recommendations.

    Parameters
    ----------
    monthly_units : float — monthly electricity consumption in kWh
    budget_pkr : float — total budget in PKR
    has_loadshedding : bool — whether area has load shedding
    wants_battery : None/True/False — battery preference
    location : str — city name

    Returns
    -------
    List of SystemRecommendation sorted by score (best first)
    """
    ideal_kw = size_system_from_load(monthly_units)
    current_bill = estimate_monthly_bill(monthly_units)
    recommendations = []

    # Determine system types to explore
    if wants_battery is True:
        system_types = ['hybrid', 'offgrid']
    elif wants_battery is False:
        system_types = ['ongrid']
    else:
        system_types = ['ongrid', 'hybrid']
        if has_loadshedding:
            system_types.append('offgrid')

    for sys_type in system_types:
        for panel in SOLAR_PANELS:
            # Try different system sizes (80%, 100%, 120% of ideal)
            for size_factor in [0.6, 0.8, 1.0, 1.2]:
                target_kw = max(2, ideal_kw * size_factor)
                num_panels = max(2, int(np.ceil(target_kw * 1000 / panel['watt'])))
                actual_kw = num_panels * panel['watt'] / 1000

                # Find matching inverter
                inv_list = INVERTERS.get(sys_type, INVERTERS['hybrid'])
                inv = None
                for candidate in sorted(inv_list, key=lambda x: x['kw']):
                    if candidate['kw'] >= actual_kw * 0.9:
                        inv = candidate
                        break
                if inv is None:
                    inv = inv_list[-1]  # largest available

                # Battery selection
                batt = None
                batt_cost = 0
                include_battery = sys_type in ('hybrid', 'offgrid')
                if include_battery:
                    daily_kwh = monthly_units / 30
                    needed_kwh = daily_kwh * 0.35  # 35% backup
                    for candidate in sorted(BATTERIES, key=lambda x: x['kwh']):
                        if candidate['kwh'] >= needed_kwh * 0.7:
                            batt = candidate
                            break
                    if batt is None:
                        batt = BATTERIES[-2]
                    batt_cost = batt['price']

                # Net metering
                net_meter = sys_type == 'ongrid'
                nm_cost = NET_METERING_SETUP if net_meter else 0

                # Calculate costs
                p_cost = num_panels * panel['watt'] * panel['price_per_watt']
                i_cost = inv['price']
                inst = (INSTALLATION_COST_PER_KW * actual_kw
                        + WIRING_MOUNTING_FIXED + WIRING_PER_KW * actual_kw)
                total = p_cost + i_cost + batt_cost + nm_cost + inst

                if total > budget_pkr * 1.05:
                    continue  # over budget

                # Generation estimate
                daily_gen = actual_kw * AVG_PEAK_SUN_HOURS * 0.82
                monthly_gen = daily_gen * 30
                annual_gen = daily_gen * 365

                # Savings calculation
                if net_meter:
                    if monthly_gen >= monthly_units:
                        monthly_save = current_bill * 0.92  # keep min charge
                    else:
                        saved_units = min(monthly_gen, monthly_units)
                        monthly_save = saved_units * GRID_TARIFF_AVG
                else:
                    self_consume = min(monthly_gen * 0.65, monthly_units)
                    monthly_save = self_consume * GRID_TARIFF_AVG

                annual_save = monthly_save * 12
                maintenance = ANNUAL_MAINTENANCE_PER_KW * actual_kw

                # Payback
                net_annual = annual_save - maintenance
                if net_annual > 0:
                    payback_months = total / (net_annual / 12)
                else:
                    payback_months = 999

                # 10-year ROI with tariff escalation
                total_10yr_savings = 0
                for year in range(1, 11):
                    escalated = annual_save * ((1+ANNUAL_TARIFF_INCREASE)**year)
                    degraded = escalated * ((1-SYSTEM_DEGRADATION)**year)
                    total_10yr_savings += degraded - maintenance
                roi_10yr = (total_10yr_savings - total) / total * 100

                # 25-year lifetime savings
                lifetime = 0
                for year in range(1, 26):
                    esc = annual_save * ((1+ANNUAL_TARIFF_INCREASE)**year)
                    deg = esc * ((1-SYSTEM_DEGRADATION)**year)
                    batt_replace = batt_cost * 0.7 if (batt and year in [10, 20]) else 0
                    lifetime += deg - maintenance - batt_replace
                lifetime -= total  # subtract initial investment

                # Scoring (lower payback = better)
                score = 100 - min(payback_months, 120) / 1.2
                if payback_months < 36:
                    score += 15
                if panel['tier'] == 1:
                    score += 5
                if batt and has_loadshedding:
                    score += 10
                if total <= budget_pkr * 0.8:
                    score += 5

                rec = SystemRecommendation(
                    system_type=sys_type,
                    system_kw=round(actual_kw, 1),
                    panel=panel,
                    num_panels=num_panels,
                    inverter=inv,
                    battery=batt,
                    net_metering=net_meter,
                    panel_cost=round(p_cost),
                    inverter_cost=round(i_cost),
                    battery_cost=round(batt_cost),
                    installation_cost=round(inst),
                    net_metering_cost=round(nm_cost),
                    total_cost=round(total),
                    daily_generation_kwh=round(daily_gen, 1),
                    monthly_generation_kwh=round(monthly_gen),
                    annual_generation_kwh=round(annual_gen),
                    monthly_savings_pkr=round(monthly_save),
                    annual_savings_pkr=round(annual_save),
                    payback_months=round(payback_months, 1),
                    roi_10yr_pct=round(roi_10yr, 1),
                    lifetime_savings_pkr=round(lifetime),
                    score=round(score, 1)
                )
                recommendations.append(rec)

    # Sort by score, deduplicate similar configs
    recommendations.sort(key=lambda x: x.score, reverse=True)

    # Tag top picks
    seen = set()
    unique = []
    for r in recommendations:
        key = (r.system_type, r.system_kw, r.panel['brand'],
               r.battery['brand'] if r.battery else 'none')
        if key not in seen:
            seen.add(key)
            unique.append(r)
        if len(unique) >= 12:
            break

    # Assign tags
    if unique:
        unique[0].tag = "⭐ Best Overall"
    for r in unique:
        if r.payback_months == min(x.payback_months for x in unique if x.payback_months > 0):
            r.tag = r.tag or "⚡ Fastest Payback"
        if r.total_cost == min(x.total_cost for x in unique):
            r.tag = r.tag or "💰 Most Affordable"
        if r.roi_10yr_pct == max(x.roi_10yr_pct for x in unique):
            r.tag = r.tag or "📈 Best ROI"
        if r.battery and r.tag == "":
            r.tag = "🔋 Battery Backup"
        if r.tag == "":
            r.tag = "✓ Good Option"

    return unique


def recommendation_to_dict(rec: SystemRecommendation) -> dict:
    """Convert to JSON-serializable dict for API."""
    return {
        'tag': rec.tag,
        'system_type': rec.system_type,
        'system_kw': rec.system_kw,
        'net_metering': rec.net_metering,
        'panel': {
            'brand': rec.panel['brand'],
            'model': rec.panel['model'],
            'watt': rec.panel['watt'],
            'efficiency': rec.panel['efficiency'],
            'type': rec.panel['type'],
            'warranty': rec.panel['warranty_yrs']
        },
        'num_panels': rec.num_panels,
        'inverter': {
            'brand': rec.inverter['brand'],
            'model': rec.inverter['model'],
            'kw': rec.inverter['kw'],
            'type': rec.inverter['type'],
            'warranty': rec.inverter['warranty_yrs']
        },
        'battery': {
            'brand': rec.battery['brand'],
            'model': rec.battery['model'],
            'kwh': rec.battery['kwh'],
            'type': rec.battery['type'],
            'cycles': rec.battery['cycles'],
            'warranty': rec.battery['warranty_yrs']
        } if rec.battery else None,
        'costs': {
            'panels': rec.panel_cost,
            'inverter': rec.inverter_cost,
            'battery': rec.battery_cost,
            'installation': rec.installation_cost,
            'net_metering': rec.net_metering_cost,
            'total': rec.total_cost
        },
        'generation': {
            'daily_kwh': rec.daily_generation_kwh,
            'monthly_kwh': rec.monthly_generation_kwh,
            'annual_kwh': rec.annual_generation_kwh
        },
        'financials': {
            'monthly_savings': rec.monthly_savings_pkr,
            'annual_savings': rec.annual_savings_pkr,
            'payback_months': rec.payback_months,
            'payback_years': round(rec.payback_months / 12, 1),
            'roi_10yr_pct': rec.roi_10yr_pct,
            'lifetime_savings_25yr': rec.lifetime_savings_pkr
        },
        'score': rec.score
    }
