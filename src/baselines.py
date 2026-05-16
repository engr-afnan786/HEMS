"""
HEMS Baseline Strategies v4.0
4 baselines from Doc3:
  1. Grid-Only
  2. Greedy Self-Consumption
  3. Simple TOU Arbitrage
  4. Rule-Based Hybrid (NEW from Doc3)
"""

import numpy as np
from dataclasses import dataclass
from .parameters import HEMSParameters, C_EXPORT, C_DEMAND, LAMBDA_DEG


@dataclass
class BaselineResult:
    """Stores baseline strategy results."""
    name:             str
    total_cost:       float
    import_cost:      float
    export_revenue:   float
    degradation_cost: float
    demand_cost:      float
    grid_import:      np.ndarray
    grid_export:      np.ndarray
    battery_charge:   np.ndarray
    battery_discharge:np.ndarray
    soc:              np.ndarray
    peak_demand:      float

    def net_cost(self):
        return (self.import_cost - self.export_revenue
                + self.degradation_cost + self.demand_cost)

    def to_api_dict(self):
        return {
            'name':                 self.name,
            'feasible':             True,
            'solver':               'HEURISTIC',
            'total_cost_pkr':       round(self.net_cost(), 2),
            'import_cost_pkr':      round(self.import_cost, 2),
            'export_revenue_pkr':   round(self.export_revenue, 2),
            'degradation_cost_pkr': round(self.degradation_cost, 2),
            'demand_charge_pkr':    round(self.demand_cost, 2),
            'capacity_tax_pkr':     0.0,
            'p_grid_plus':          self.grid_import.tolist(),
            'p_grid_minus':         self.grid_export.tolist(),
            'p_charge':             self.battery_charge.tolist(),
            'p_discharge':          self.battery_discharge.tolist(),
            'soc':                  self.soc.tolist() if hasattr(self.soc, 'tolist') else self.soc
        }


def simulate_battery(p_ch, p_dis, E_init=6.75, E_max=13.5, E_min=2.7,
                     eta_c=0.95, eta_d=0.95, dt=1.0):
    """Simulate battery SOC with physics clipping (from Doc3)."""
    T = len(p_ch)
    soc = np.zeros(T + 1)
    soc[0] = E_init
    actual_ch  = np.zeros(T)
    actual_dis = np.zeros(T)

    for t in range(T):
        max_ch  = (E_max - soc[t]) / (eta_c * dt)
        actual_ch[t] = min(p_ch[t], max(0, max_ch))

        max_dis = (soc[t] - E_min) * eta_d / dt
        actual_dis[t] = min(p_dis[t], max(0, max_dis))

        soc[t+1] = (soc[t] + eta_c * actual_ch[t] * dt
                    - (1.0/eta_d) * actual_dis[t] * dt)
        soc[t+1] = np.clip(soc[t+1], E_min, E_max)

    return soc, actual_ch, actual_dis


def compute_cost(p_imp, p_exp, p_ch, p_dis, tariff,
                 c_export=C_EXPORT, lam=LAMBDA_DEG,
                 c_demand=C_DEMAND, dt=1.0):
    """Compute cost components (from Doc3)."""
    import_cost = float(np.sum(tariff * p_imp) * dt)
    export_rev  = float(c_export * np.sum(p_exp) * dt)
    degrad      = float(lam * np.sum(p_ch + p_dis) * dt)
    peak        = float(np.max(p_imp))
    demand      = float(c_demand * peak)
    return import_cost, export_rev, degrad, demand


# ── Baseline 1: Grid Only ────────────────────────────────────────────────
def baseline_grid_only(params: HEMSParameters) -> BaselineResult:
    """All load from grid. No battery. Solar exported if surplus."""
    T      = params.T
    tariff = params.tariff
    G      = params.G

    # Include unoptimized shiftable loads (worst-case: peak hours)
    p_load = params.p_load.copy()
    p_load[9]  += 1.5   # washing h1
    p_load[10] += 1.5   # washing h2
    p_load[19] += 3.0   # water heater at peak
    p_load[21] += 1.2   # dishwasher

    net   = p_load - params.p_pv_mean
    p_imp = np.maximum(net, 0) * G
    p_exp = np.minimum(np.maximum(-net, 0), params.P_export_max) * G

    p_ch  = np.zeros(T)
    p_dis = np.zeros(T)
    soc   = np.full(T + 1, 0.5 * params.E_max)

    ic, er, dg, dm = compute_cost(p_imp, p_exp, p_ch, p_dis, tariff,
                                   params.c_export, params.lam, params.c_demand)
    return BaselineResult(
        name="Grid-Only (No Battery)", total_cost=ic - er + dg + dm,
        import_cost=ic, export_revenue=er, degradation_cost=dg, demand_cost=dm,
        grid_import=p_imp, grid_export=p_exp,
        battery_charge=p_ch, battery_discharge=p_dis,
        soc=soc, peak_demand=float(np.max(p_imp))
    )


# ── Baseline 2: Greedy Self-Consumption ──────────────────────────────────
def baseline_greedy(params: HEMSParameters) -> dict:
    """Greedy: charge from solar surplus, discharge when solar < load."""
    T      = params.T
    tariff = params.tariff
    G      = params.G

    p_ch  = np.zeros(T)
    p_dis = np.zeros(T)
    p_imp = np.zeros(T)
    p_exp = np.zeros(T)

    for t in range(T):
        net = params.p_load[t] - params.p_pv_mean[t]
        if net < 0:
            p_ch[t] = min(-net, params.Pc_max)
            p_exp[t] = min(-net - p_ch[t], params.P_export_max)
        else:
            p_dis[t] = min(net, params.Pd_max)
            p_imp[t] = net - p_dis[t]

    soc, p_ch, p_dis = simulate_battery(
        p_ch, p_dis, E_init=0.5*params.E_max,
        E_max=params.E_max, E_min=params.E_min,
        eta_c=params.eta_c, eta_d=params.eta_d
    )

    # Recalculate grid after clipping
    for t in range(T):
        net = params.p_load[t] - params.p_pv_mean[t]
        if net < 0:
            p_exp[t] = min(-net - p_ch[t], params.P_export_max) * G[t]
            p_imp[t] = 0
        else:
            p_imp[t] = max(0, net - p_dis[t]) * G[t]
            p_exp[t] = 0

    ic, er, dg, dm = compute_cost(p_imp, p_exp, p_ch, p_dis, tariff,
                                   params.c_export, params.lam, params.c_demand)
    return {
        'name': 'Greedy Self-Consumption',
        'feasible': True, 'solver': 'GREEDY',
        'total_cost_pkr': round(ic - er + dg + dm, 2),
        'import_cost_pkr': round(ic, 2),
        'export_revenue_pkr': round(er, 2),
        'degradation_cost_pkr': round(dg, 2),
        'demand_charge_pkr': round(dm, 2),
        'capacity_tax_pkr': 0.0,
        'p_grid_plus': p_imp.tolist(),
        'p_grid_minus': p_exp.tolist(),
        'p_charge': p_ch.tolist(),
        'p_discharge': p_dis.tolist(),
        'soc': soc.tolist()
    }


# ── Baseline 3: TOU Arbitrage ─────────────────────────────────────────────
def baseline_tou_arbitrage(params: HEMSParameters) -> BaselineResult:
    """Charge 01-05h off-peak, discharge 18-22h peak (Doc3 approach)."""
    T      = params.T
    tariff = params.tariff
    G      = params.G

    p_ch  = np.zeros(T)
    p_dis = np.zeros(T)

    for t in [1, 2, 3, 4]:
        p_ch[t] = params.Pc_max
    for t in range(18, 22):
        p_dis[t] = params.Pd_max

    soc, p_ch, p_dis = simulate_battery(
        p_ch, p_dis, E_init=0.5*params.E_max,
        E_max=params.E_max, E_min=params.E_min,
        eta_c=params.eta_c, eta_d=params.eta_d
    )

    p_imp = np.zeros(T)
    p_exp = np.zeros(T)
    for t in range(T):
        net = params.p_load[t] - params.p_pv_mean[t] - p_dis[t] + p_ch[t]
        if net > 0:
            p_imp[t] = net * G[t]
        else:
            p_exp[t] = min(-net, params.P_export_max) * G[t]

    ic, er, dg, dm = compute_cost(p_imp, p_exp, p_ch, p_dis, tariff,
                                   params.c_export, params.lam, params.c_demand)
    return BaselineResult(
        name="Simple TOU Arbitrage", total_cost=ic - er + dg + dm,
        import_cost=ic, export_revenue=er, degradation_cost=dg, demand_cost=dm,
        grid_import=p_imp, grid_export=p_exp,
        battery_charge=p_ch, battery_discharge=p_dis,
        soc=soc, peak_demand=float(np.max(p_imp))
    )


# ── Baseline 4: Rule-Based Hybrid (NEW from Doc3) ─────────────────────────
def baseline_hybrid(params: HEMSParameters) -> BaselineResult:
    """
    Solar self-consumption + TOU-aware battery (Doc3 Baseline 4).
    - Solar surplus → charge battery
    - Off-peak early morning → charge from grid if low SOC
    - Peak hours → discharge to avoid grid
    """
    T      = params.T
    tariff = params.tariff
    G      = params.G
    peak_start, peak_end = 18, 22

    p_ch  = np.zeros(T)
    p_dis = np.zeros(T)

    for t in range(T):
        surplus = max(0, params.p_pv_mean[t] - params.p_load[t])
        deficit = max(0, params.p_load[t] - params.p_pv_mean[t])

        if peak_start <= t < peak_end:
            p_dis[t] = min(deficit, params.Pd_max)
        elif surplus > 0:
            p_ch[t] = min(surplus, params.Pc_max)
        elif t < 6:
            p_ch[t] = 3.0  # moderate off-peak charge

    soc, p_ch, p_dis = simulate_battery(
        p_ch, p_dis, E_init=0.5*params.E_max,
        E_max=params.E_max, E_min=params.E_min,
        eta_c=params.eta_c, eta_d=params.eta_d
    )

    p_imp = np.zeros(T)
    p_exp = np.zeros(T)
    for t in range(T):
        net = params.p_load[t] - params.p_pv_mean[t] - p_dis[t] + p_ch[t]
        if net > 0:
            p_imp[t] = net * G[t]
        else:
            p_exp[t] = min(-net, params.P_export_max) * G[t]

    ic, er, dg, dm = compute_cost(p_imp, p_exp, p_ch, p_dis, tariff,
                                   params.c_export, params.lam, params.c_demand)
    return BaselineResult(
        name="Rule-Based Hybrid", total_cost=ic - er + dg + dm,
        import_cost=ic, export_revenue=er, degradation_cost=dg, demand_cost=dm,
        grid_import=p_imp, grid_export=p_exp,
        battery_charge=p_ch, battery_discharge=p_dis,
        soc=soc, peak_demand=float(np.max(p_imp))
    )


def run_all_baselines(params: HEMSParameters) -> list:
    """Run all 4 baseline strategies. Returns list of API-compatible dicts."""
    b1 = baseline_grid_only(params)
    b2 = baseline_greedy(params)       # already dict
    b3 = baseline_tou_arbitrage(params)
    b4 = baseline_hybrid(params)

    # Print comparison table
    print("\n── Baseline Comparison ──")
    print(f"{'Strategy':<30} {'Cost (PKR/day)':>15}")
    print("-" * 50)
    for b in [b1, b3, b4]:
        print(f"{b.name:<30} {b.net_cost():>15.2f}")
    print(f"{'Greedy Self-Consumption':<30} {b2['total_cost_pkr']:>15.2f}")

    return [b1.to_api_dict(), b2, b3.to_api_dict(), b4.to_api_dict()]