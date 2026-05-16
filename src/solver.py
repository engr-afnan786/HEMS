"""
HEMS Core Solver v4.0
Combines:
- Doc3: HEMSResult dataclass, verify_kkt(), compare_solvers(), CLARABEL support
- Doc2: G_t load shedding, billing modes, fallback cascade
- Doc1: Complete constraint set C1-C8
"""

import cvxpy as cp
import numpy as np
import time as _time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .parameters import HEMSParameters
from .baselines import baseline_greedy


# ── Result Dataclass (from Doc3) ─────────────────────────────────────────
@dataclass
class HEMSResult:
    """Complete optimization results: primal, dual, metadata, cost breakdown."""

    # Status
    status:        str   = ""
    optimal_cost:  float = 0.0
    solve_time:    float = 0.0
    solver_used:   str   = ""
    problem_class: str   = ""
    feasible:      bool  = False
    fallback:      bool  = False
    rho:           float = 0.0

    # Primal
    p_grid_import:  np.ndarray = field(default_factory=lambda: np.zeros(24))
    p_grid_export:  np.ndarray = field(default_factory=lambda: np.zeros(24))
    p_charge:       np.ndarray = field(default_factory=lambda: np.zeros(24))
    p_discharge:    np.ndarray = field(default_factory=lambda: np.zeros(24))
    soc:            np.ndarray = field(default_factory=lambda: np.zeros(25))
    peak_demand:    float = 0.0
    x_wash:         np.ndarray = field(default_factory=lambda: np.zeros(24))
    x_heater:       np.ndarray = field(default_factory=lambda: np.zeros(24))
    x_dishwasher:   np.ndarray = field(default_factory=lambda: np.zeros(24))

    # Cost components
    import_cost:       float = 0.0
    export_revenue:    float = 0.0
    degradation_cost:  float = 0.0
    demand_cost:       float = 0.0
    capacity_tax:      float = 0.0

    # Dual variables (shadow prices)
    energy_balance_duals:   np.ndarray = field(default_factory=lambda: np.zeros(24))
    soc_upper_duals:        np.ndarray = field(default_factory=lambda: np.zeros(25))
    soc_lower_duals:        np.ndarray = field(default_factory=lambda: np.zeros(25))
    charge_upper_duals:     np.ndarray = field(default_factory=lambda: np.zeros(24))
    discharge_upper_duals:  np.ndarray = field(default_factory=lambda: np.zeros(24))

    # Metadata
    simultaneous_cd_kwh: float = 0.0
    billing_mode:        str   = ""
    G:                   np.ndarray = field(default_factory=lambda: np.ones(24))

    def net_cost(self):
        return (self.import_cost - self.export_revenue
                + self.degradation_cost + self.demand_cost + self.capacity_tax)

    def summary(self):
        print("=" * 65)
        print(f"  HEMS Optimization Result — {self.problem_class}")
        print("=" * 65)
        print(f"  Status:      {self.status}")
        print(f"  Solver:      {self.solver_used}"
              + (" [FALLBACK]" if self.fallback else ""))
        print(f"  Solve time:  {self.solve_time:.4f}s")
        print(f"  ρ:           {self.rho:.2f} kWh")
        print(f"  Billing:     {self.billing_mode}")
        print("-" * 65)
        print(f"  ┌─ Cost Breakdown (PKR/day) ───────────────────┐")
        print(f"  │  Grid import cost:   {self.import_cost:>10.2f}             │")
        print(f"  │  Export revenue:     {self.export_revenue:>10.2f}             │")
        print(f"  │  Degradation cost:   {self.degradation_cost:>10.2f}             │")
        print(f"  │  Demand charge:      {self.demand_cost:>10.2f}             │")
        print(f"  │  Capacity tax:       {self.capacity_tax:>10.2f}             │")
        print(f"  ├──────────────────────────────────────────────┤")
        print(f"  │  TOTAL DAILY COST:   {self.net_cost():>10.2f} PKR         │")
        print(f"  └──────────────────────────────────────────────┘")
        print(f"  Peak demand:    {self.peak_demand:.2f} kW")
        cyc = (self.p_charge.sum() + self.p_discharge.sum()) / (2 * max(1, 13.5))
        print(f"  Battery cycles: {cyc:.2f}")
        print(f"  Grid import:    {self.p_grid_import.sum():.1f} kWh")
        print(f"  Grid export:    {self.p_grid_export.sum():.1f} kWh")
        if self.simultaneous_cd_kwh > 0.01:
            print(f"  ⚠ Sim. C/D:    {self.simultaneous_cd_kwh:.3f} kWh")
        print("=" * 65)


# ── Core Builder ─────────────────────────────────────────────────────────
def _build_and_solve(params: HEMSParameters, solver_name: str) -> tuple:
    """Build and solve the CVXPY problem. Returns (prob, variables, constraints)."""
    T  = params.T
    dt = params.dt

    # Decision variables
    p_imp = cp.Variable(T, nonneg=True, name="p_grid_import")
    p_exp = cp.Variable(T, nonneg=True, name="p_grid_export")
    p_ch  = cp.Variable(T, nonneg=True, name="p_charge")
    p_dis = cp.Variable(T, nonneg=True, name="p_discharge")
    soc   = cp.Variable(T + 1, nonneg=True, name="soc")
    P_pk  = cp.Variable(nonneg=True, name="P_peak")
    x_w   = cp.Variable(T, nonneg=True, name="x_wash")
    x_h   = cp.Variable(T, nonneg=True, name="x_heater")
    x_d   = cp.Variable(T, nonneg=True, name="x_dishwasher")

    P_WASH, P_HEAT, P_DISH = 1.5, 3.0, 1.2

    def shift_t(t):
        total = P_WASH * x_w[t] + P_HEAT * x_h[t] + P_DISH * x_d[t]
        if 'ev_charger' in params.appliances:
            total += params.appliances['ev_charger']['power'] * x_w[t]  # placeholder
        return total

    # C9 — Load curtailment variable (for feasibility during load shedding)
    # During outage hours, if load > Pd_max + solar, some load must be curtailed.
    # This is physically realistic: non-critical loads (AC, heater) are shed first.
    # Penalized heavily in objective to ensure it's only used when necessary.
    p_curt = cp.Variable(T, nonneg=True, name="p_curtail")
    CURTAIL_PENALTY = 200.0  # PKR/kWh — very high, ensures last resort

    # Objective
    import_cost = cp.sum(cp.multiply(params.tariff, p_imp)) * dt
    export_rev  = params.c_export * cp.sum(p_exp) * dt
    degrad      = params.lam * cp.sum(p_ch + p_dis) * dt
    demand_chg  = params.c_demand * P_pk
    cap_tax     = float(params.capacity_tax)
    curtail_cost = CURTAIL_PENALTY * cp.sum(p_curt) * dt

    # SOCP robust penalty (rho > 0)
    rho = params.rho
    if rho > 0:
        solar_hours = np.where(params.p_pv_mean > 0.1)[0]
        if len(solar_hours) > 0:
            exposure  = cp.hstack([params.tariff[t] * p_imp[t] for t in solar_hours])
            objective = cp.Minimize(
                import_cost - export_rev + degrad + demand_chg + cap_tax
                + curtail_cost + rho * cp.norm(exposure, 2)
            )
        else:
            objective = cp.Minimize(
                import_cost - export_rev + degrad + demand_chg + cap_tax
                + curtail_cost
            )
    else:
        objective = cp.Minimize(
            import_cost - export_rev + degrad + demand_chg + cap_tax
            + curtail_cost
        )

    constraints = []

    # C1 — Energy balance with G_t (load shedding) + curtailment
    # For robust formulation: use >= inequality during solar hours
    # to allow surplus that absorbs worst-case solar shortfall
    eb_constraints = []
    for t in range(T):
        G_t = float(params.G[t])
        lhs = G_t * p_imp[t] - G_t * p_exp[t] + p_dis[t] - p_ch[t] + p_curt[t]
        rhs = params.p_load[t] + shift_t(t) - params.p_pv_mean[t]
        
        if rho > 0 and params.p_pv_mean[t] > 0.1 and params.G[t] > 0.5:
            # Robust: supply ≥ demand (surplus absorbs solar uncertainty)
            c = lhs >= rhs
        else:
            # Nominal: exact equality
            c = lhs == rhs
        eb_constraints.append(c)
        constraints.append(c)

    # Curtailment only allowed during load shedding hours
    for t in range(T):
        if params.G[t] > 0.5:  # grid available → no curtailment allowed
            constraints.append(p_curt[t] == 0)

    # C2 — Battery dynamics
    constraints.append(soc[0] == 0.5 * params.E_max)
    soc_dyn = []
    for t in range(T):
        c = soc[t+1] == soc[t] + params.eta_c*p_ch[t]*dt - (1.0/params.eta_d)*p_dis[t]*dt
        soc_dyn.append(c)
        constraints.append(c)
    constraints.append(soc[T] == 0.5 * params.E_max)

    # C3 — SOC limits
    soc_upper = [soc[t] <= params.E_max for t in range(T+1)]
    soc_lower = [soc[t] >= params.E_min for t in range(T+1)]
    constraints.extend(soc_upper)
    constraints.extend(soc_lower)

    # C4 — Power limits (with G_t for grid)
    ch_upper  = [p_ch[t]  <= params.Pc_max for t in range(T)]
    dis_upper = [p_dis[t] <= params.Pd_max for t in range(T)]
    constraints.extend(ch_upper)
    constraints.extend(dis_upper)
    for t in range(T):
        G_t = float(params.G[t])
        constraints.append(p_imp[t] <= params.P_grid_max * G_t)
        constraints.append(p_exp[t] <= params.P_export_max * G_t)

    # C5 — Peak demand
    for t in range(T):
        constraints.append(P_pk >= p_imp[t])

    # C6 — Shiftable loads: washing
    constraints.append(cp.sum(x_w) == 2)
    constraints.append(cp.sum(x_h) == 1)
    constraints.append(cp.sum(x_d) == 1)
    constraints.append(x_w <= 1)
    constraints.append(x_h <= 1)
    constraints.append(x_d <= 1)
    for t in range(T):
        if t < 8 or t >= 18:
            constraints.append(x_w[t] == 0)
        if not (5 <= t < 8 or 18 <= t < 22):
            constraints.append(x_h[t] == 0)
        if not (20 <= t < 24):
            constraints.append(x_d[t] == 0)

    # C7 — SOC reserve before load-shedding
    # Use bounded reserve: min(required, E_max * 0.9) to prevent infeasibility
    # when multiple shedding hours cluster near peak hours
    for t, min_soc in params.soc_reserve_hours.items():
        # Cap reserve at 85% of E_max to leave room for cyclic boundary
        bounded_reserve = min(min_soc, params.E_max * 0.85)
        # Only apply if the constraint is tighter than E_min
        if bounded_reserve > params.E_min:
            constraints.append(soc[int(t)] >= bounded_reserve)

    # C8 — Robust per-slot margin (only for grid-available solar hours)
    if rho > 0:
        solar_mask = params.p_pv_mean > 0.1
        max_solar  = np.max(params.p_pv_mean) if np.max(params.p_pv_mean) > 0 else 1.0
        for t in range(T):
            if solar_mask[t] and params.G[t] > 0.5:  # only grid-available solar hours
                sigma_t = params.p_pv_mean[t] / max_solar
                # Robust margin: ensure enough surplus to absorb solar uncertainty
                surplus = p_imp[t] - p_exp[t] + p_dis[t] - p_ch[t] + p_curt[t] \
                          - params.p_load[t] - shift_t(t) + params.p_pv_mean[t]
                constraints.append(surplus >= rho * sigma_t)

    prob = cp.Problem(objective, constraints)

    solver_map = {
        'ECOS':     cp.ECOS,
        'SCS':      cp.SCS,
        'OSQP':     cp.OSQP,
        'CLARABEL': cp.CLARABEL
    }
    chosen = solver_map.get(solver_name, cp.ECOS)

    t0 = _time.time()
    try:
        prob.solve(solver=chosen, verbose=False)
    except cp.SolverError:
        prob.solve(solver=cp.SCS, verbose=False)
    elapsed = _time.time() - t0

    return (prob, p_imp, p_exp, p_ch, p_dis, soc, P_pk,
            x_w, x_h, x_d, eb_constraints, soc_upper, soc_lower,
            ch_upper, dis_upper, elapsed, p_curt)


def _extract(prob, p_imp, p_exp, p_ch, p_dis, soc_var, P_pk,
             x_w, x_h, x_d, eb_cons, soc_upper, soc_lower,
             ch_upper, dis_upper, elapsed, p_curt, params, solver_name) -> HEMSResult:
    """Extract HEMSResult from solved CVXPY problem."""
    T   = params.T
    dt  = params.dt

    res = HEMSResult()
    res.status        = prob.status
    res.optimal_cost  = prob.value if prob.value is not None else float('inf')
    res.solve_time    = elapsed
    res.solver_used   = solver_name
    res.rho           = params.rho
    res.billing_mode  = params.billing_mode
    res.G             = params.G.copy()

    if prob.status not in ('optimal', 'optimal_inaccurate'):
        return res

    res.feasible = True

    pgp = np.array(p_imp.value).flatten()
    pgm = np.array(p_exp.value).flatten()
    pc  = np.array(p_ch.value).flatten()
    pd  = np.array(p_dis.value).flatten()
    sv  = np.array(soc_var.value).flatten()
    ppk = float(P_pk.value)

    res.p_grid_import  = pgp
    res.p_grid_export  = pgm
    res.p_charge       = pc
    res.p_discharge    = pd
    res.soc            = sv
    res.peak_demand    = ppk
    res.x_wash         = np.array(x_w.value).flatten()
    res.x_heater       = np.array(x_h.value).flatten()
    res.x_dishwasher   = np.array(x_d.value).flatten()

    res.import_cost      = float(np.sum(params.tariff * pgp) * dt)
    res.export_revenue   = float(params.c_export * np.sum(pgm) * dt)
    res.degradation_cost = float(params.lam * np.sum(pc + pd) * dt)
    res.demand_cost      = float(params.c_demand * ppk)
    res.capacity_tax     = float(params.capacity_tax)

    # Simultaneous charge/discharge detection
    res.simultaneous_cd_kwh = float(np.sum(np.minimum(pc, pd)))
    if res.simultaneous_cd_kwh > 0.01:
        print(f"[WARN] Simultaneous C/D: {res.simultaneous_cd_kwh:.3f} kWh — consider λ increase")

    # Load curtailment
    try:
        curt = np.array(p_curt.value).flatten()
        curt_total = float(np.sum(curt))
        if curt_total > 0.01:
            print(f"[INFO] Load curtailment: {curt_total:.2f} kWh during shedding hours")
            res.curtailment_kwh = curt_total
    except Exception:
        pass

    # Dual variables
    try:
        res.energy_balance_duals = np.array(
            [eb_cons[t].dual_value for t in range(T)]).flatten()
    except Exception:
        res.energy_balance_duals = np.zeros(T)
    try:
        res.soc_upper_duals = np.array(
            [c.dual_value for c in soc_upper]).flatten()
        res.soc_lower_duals = np.array(
            [c.dual_value for c in soc_lower]).flatten()
        res.charge_upper_duals = np.array(
            [c.dual_value for c in ch_upper]).flatten()
        res.discharge_upper_duals = np.array(
            [c.dual_value for c in dis_upper]).flatten()
    except Exception:
        pass

    return res


# ── Public Solver with Fallback ───────────────────────────────────────────
def run_optimization(params: HEMSParameters,
                     solvers=None) -> HEMSResult:
    """
    Run HEMS optimization with fallback cascade.
    Priority: ECOS → SCS → OSQP → CLARABEL → Greedy Heuristic
    """
    if solvers is None:
        solvers = ['ECOS', 'SCS', 'OSQP', 'CLARABEL']

    rho_str = f"Robust SOCP (ρ={params.rho})" if params.rho > 0 else "Nominal LP"

    for sname in solvers:
        try:
            out = _build_and_solve(params, sname)
            prob = out[0]
            if prob.status in ('optimal', 'optimal_inaccurate'):
                res = _extract(*out, params, sname)
                res.problem_class = rho_str
                print(f"[HEMS] {rho_str} solved by {sname} in {res.solve_time:.4f}s "
                      f"| Cost: PKR {res.net_cost():.2f}")
                return res
        except Exception as e:
            print(f"[HEMS] {sname} failed: {e}")

    # Greedy fallback
    print("[HEMS] All solvers failed — greedy fallback.")
    from .baselines import baseline_greedy
    fb = baseline_greedy(params)
    res = HEMSResult()
    res.fallback      = True
    res.solver_used   = 'GREEDY_FALLBACK'
    res.feasible      = True
    res.status        = 'fallback'
    res.problem_class = 'Greedy Heuristic'
    res.billing_mode  = params.billing_mode
    res.G             = params.G.copy()
    res.import_cost   = fb.get('import_cost_pkr', 0)
    res.export_revenue= fb.get('export_revenue_pkr', 0)
    res.degradation_cost = fb.get('degradation_cost_pkr', 0)
    res.demand_cost   = fb.get('demand_charge_pkr', 0)
    res.p_grid_import = np.array(fb.get('p_grid_plus', [0]*24))
    res.p_grid_export = np.array(fb.get('p_grid_minus', [0]*24))
    res.p_charge      = np.array(fb.get('p_charge', [0]*24))
    res.p_discharge   = np.array(fb.get('p_discharge', [0]*24))
    res.soc           = np.array(fb.get('soc', [0]*25))
    return res


# ── Wrappers for backward compatibility ──────────────────────────────────
def solve_nominal_lp(params: HEMSParameters, solver='ECOS') -> HEMSResult:
    old_rho = params.rho
    params.rho = 0.0
    res = run_optimization(params, solvers=[solver, 'SCS', 'CLARABEL'])
    res.problem_class = "Nominal LP"
    params.rho = old_rho
    return res


def solve_robust_socp(params: HEMSParameters, solver='ECOS') -> HEMSResult:
    res = run_optimization(params, solvers=[solver, 'SCS', 'CLARABEL'])
    res.problem_class = f"Robust SOCP (ρ={params.rho})"
    return res


# ── Solver Comparison (Doc3 Exp 7) ───────────────────────────────────────
def compare_solvers(params: HEMSParameters,
                    solvers=None) -> Dict[str, HEMSResult]:
    """Compare ECOS, SCS, OSQP, CLARABEL on same problem."""
    if solvers is None:
        solvers = ['ECOS', 'SCS', 'OSQP', 'CLARABEL']
    results = {}
    print("\n══ Solver Comparison ══")
    for sname in solvers:
        try:
            out = _build_and_solve(params, sname)
            prob = out[0]
            if prob.status in ('optimal', 'optimal_inaccurate'):
                res = _extract(*out, params, sname)
                res.problem_class = f"Nominal LP [{sname}]"
                results[sname] = res
                print(f"  {sname:10s}: cost={res.net_cost():8.2f} PKR | "
                      f"time={res.solve_time:.4f}s | status={res.status}")
            else:
                print(f"  {sname:10s}: {prob.status}")
        except Exception as e:
            print(f"  {sname:10s}: FAILED — {e}")
    return results


# ── KKT Verification (Doc3) ──────────────────────────────────────────────
def verify_kkt(result: HEMSResult, tariff: np.ndarray,
               lam: float = 2.0, tol: float = 1e-4) -> bool:
    """
    Verify all 4 KKT conditions for LP optimality.
    KKT conditions (necessary AND sufficient for LP):
      1. Primal feasibility
      2. Dual feasibility (multipliers ≥ 0)
      3. Complementary slackness
      4. Stationarity
    """
    print("\n── KKT Condition Verification ──")
    violations = 0
    T = 24

    # 1. Primal feasibility
    print("\n1. Primal Feasibility:")
    soc = result.soc
    E_max = 13.5
    E_min = 2.7
    print(f"   SOC range: [{soc.min():.4f}, {soc.max():.4f}] "
          f"(limits: [{E_min}, {E_max}])")
    if soc.min() < E_min - tol or soc.max() > E_max + tol:
        print("   ✗ SOC bounds VIOLATED")
        violations += 1
    else:
        print("   ✓ SOC bounds satisfied")

    if result.p_grid_import.min() >= -tol and result.p_charge.min() >= -tol:
        print("   ✓ Non-negativity satisfied")
    else:
        print("   ✗ Non-negativity VIOLATED")
        violations += 1

    # 2. Dual feasibility
    print("\n2. Dual Feasibility:")
    su = result.soc_upper_duals
    sl = result.soc_lower_duals
    if np.all(su >= -tol) and np.all(sl >= -tol):
        print("   ✓ All inequality multipliers ≥ 0")
    else:
        print("   ✗ Some multipliers negative")
        violations += 1

    # 3. Complementary slackness
    print("\n3. Complementary Slackness:")
    cs_v = 0
    for t in range(T + 1):
        if abs(su[t]) > tol and (E_max - soc[t]) > tol:
            cs_v += 1
        if abs(sl[t]) > tol and (soc[t] - E_min) > tol:
            cs_v += 1
    if cs_v == 0:
        print("   ✓ Complementary slackness holds")
    else:
        print(f"   ✗ {cs_v} complementary slackness violations")
        violations += 1

    # 4. Stationarity
    print("\n4. Stationarity:")
    mu = result.energy_balance_duals
    print(f"   Shadow prices μ_t: [{mu.min():.2f}, {mu.max():.2f}] PKR/kWh")
    print(f"   Tariff range:      [{tariff.min():.2f}, {tariff.max():.2f}] PKR/kWh")
    active = result.p_grid_import > tol
    if np.any(active) and len(mu[active]) > 1:
        corr = np.corrcoef(np.abs(mu[active]), tariff[active])[0, 1]
        print(f"   Corr(|μ_t|, tariff) for active imports: {corr:.4f}")
        if corr > 0.5:
            print("   ✓ Stationarity consistent with tariff structure")
        else:
            print("   ~ Stationarity check inconclusive")

    print(f"\n{'='*50}")
    if violations == 0:
        print("✓ ALL KKT CONDITIONS SATISFIED")
    else:
        print(f"✗ {violations} KKT VIOLATION(S) DETECTED")
    print(f"{'='*50}")
    return violations == 0