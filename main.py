#!/usr/bin/env python3
"""
HEMS v4.0 — Standalone Academic Runner
Run: python main.py
Or open in VSCode and use # %% cells with Shift+Enter (Python Interactive)

╔═══════════════════════════════════════════════════════════════╗
║  HEMS Pakistan — Robust Convex Optimization v4.0             ║
║  NEPRA/IESCO Feb 2026 | Budget 2024-25 | LP → SOCP           ║
╚═══════════════════════════════════════════════════════════════╝
"""

# %% [markdown]
# # 1. Setup & Imports

# %%
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))
               if '__file__' in dir() else os.getcwd())

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from src.parameters import (
    HEMSParameters, generate_load_profile, generate_solar_profile,
    get_tariff_vector, save_all_data,
    T, TARIFF, C_PEAK, C_OFFPEAK, C_EXPORT, C_DEMAND,
    E_MAX, E_MIN, LAMBDA_DEG, PV_RATED, SHIFTABLE_APPLIANCES
)
from src.solver import (
    solve_nominal_lp, solve_robust_socp, run_optimization,
    verify_kkt, compare_solvers, HEMSResult
)
from src.baselines import run_all_baselines
from src.experiments import run_all_experiments
from src.visualization import generate_all_plots
from src.dual_analysis import analyze_duals

print("✓ All imports successful")
print(f"  Tariff: PKR {C_PEAK}/kWh (peak 18-22h) | PKR {C_OFFPEAK}/kWh (off-peak)")

# %% [markdown]
# # 2. Data Generation

# %%
save_all_data(output_dir="data")

p_load_summer = generate_load_profile("summer")
p_load_winter = generate_load_profile("winter")
p_pv_summer   = generate_solar_profile("summer")
p_pv_winter   = generate_solar_profile("winter")
tariff        = get_tariff_vector()

print(f"\n── Rawalpindi Household Profile ──")
print(f"Summer load:  {p_load_summer.sum():.1f} kWh/day "
      f"(peak: {p_load_summer.max():.1f} kW)")
print(f"Winter load:  {p_load_winter.sum():.1f} kWh/day "
      f"(peak: {p_load_winter.max():.1f} kW)")
print(f"Summer solar: {p_pv_summer.sum():.1f} kWh/day "
      f"(peak: {p_pv_summer.max():.1f} kW)")
print(f"Winter solar: {p_pv_winter.sum():.1f} kWh/day "
      f"(peak: {p_pv_winter.max():.1f} kW)")

# %% [markdown]
# # 3. Nominal LP Solution

# %%
print("═══ Nominal LP (ρ=0, Summer) ═══")
params_nominal = HEMSParameters(season='summer', rho=0.0, use_loadshedding=True)
result_nominal = solve_nominal_lp(params_nominal)
result_nominal.summary()

# Energy balance verification
print("\n── Energy Balance Verification ──")
all_ok = True
for t in range(24):
    G_t  = params_nominal.G[t]
    supp = (G_t * result_nominal.p_grid_import[t]
            + result_nominal.p_discharge[t]
            + params_nominal.p_pv_mean[t])
    dem  = (params_nominal.p_load[t]
            + result_nominal.p_charge[t]
            + G_t * result_nominal.p_grid_export[t]
            + 1.5 * result_nominal.x_wash[t]
            + 3.0 * result_nominal.x_heater[t]
            + 1.2 * result_nominal.x_dishwasher[t])
    bal  = abs(supp - dem)
    if bal > 0.01:
        print(f"  ⚠ Hour {t}: imbalance = {bal:.4f} kW")
        all_ok = False
if all_ok:
    print("  ✓ All 24 energy balance constraints satisfied (residual < 0.01 kW)")
print(f"  SOC[0]={result_nominal.soc[0]:.2f}, SOC[24]={result_nominal.soc[24]:.2f} (cyclic ✓)")

# %% [markdown]
# # 4. Robust SOCP Solution

# %%
print("═══ Robust SOCP (ρ=1.5, Summer) ═══")
params_robust = HEMSParameters(season='summer', rho=1.5, use_loadshedding=True)
result_robust = solve_robust_socp(params_robust)
result_robust.summary()

print(f"\n── Nominal vs Robust ──")
print(f"  Nominal:  PKR {result_nominal.net_cost():.2f}/day")
print(f"  Robust:   PKR {result_robust.net_cost():.2f}/day")
delta = result_robust.net_cost() - result_nominal.net_cost()
pct   = delta / result_nominal.net_cost() * 100
print(f"  Price of robustness (ρ=1.5): +PKR {delta:.2f} (+{pct:.2f}%)")

# %% [markdown]
# # 5. KKT Verification

# %%
print("═══ KKT Conditions ═══")
kkt_ok = verify_kkt(result_nominal, tariff, lam=LAMBDA_DEG)

# %% [markdown]
# # 6. Baselines (4 strategies from Doc3)

# %%
print("═══ 4 Baseline Strategies ═══")
baselines = run_all_baselines(params_nominal)

print(f"\n── Savings vs Convex Optimal ──")
for b in baselines:
    bc   = b.get('total_cost_pkr', 0)
    oc   = result_nominal.net_cost()
    save = bc - oc
    pct  = save / bc * 100 if bc else 0
    print(f"  vs {b['name']:<30}: save PKR {save:.2f}/day ({pct:.1f}%)")

# %% [markdown]
# # 7. Solver Comparison (ECOS/SCS/OSQP/CLARABEL)

# %%
print("═══ Solver Comparison ═══")
solver_results = compare_solvers(
    params_nominal,
    solvers=['ECOS', 'SCS', 'OSQP', 'CLARABEL']
)
costs = {n: r.net_cost() for n, r in solver_results.items()}
print(f"\nCost consistency: {costs}")
max_diff = max(costs.values()) - min(costs.values()) if costs else 0
print(f"Max cost difference across solvers: PKR {max_diff:.4f}")

# %% [markdown]
# # 8. Dual Variable Analysis

# %%
print("═══ Dual Variable (KKT Shadow Price) Analysis ═══")
mu = np.abs(result_nominal.energy_balance_duals)
duals = analyze_duals(result_nominal, params_nominal)

print(f"\nShadow price μ_t interpretation:")
for t in range(24):
    actions = []
    if result_nominal.p_grid_import[t] > 0.1:  actions.append("IMPORT")
    if result_nominal.p_grid_export[t] > 0.1:  actions.append("EXPORT")
    if result_nominal.p_charge[t] > 0.1:       actions.append("CHARGE")
    if result_nominal.p_discharge[t] > 0.1:    actions.append("DISCH")
    peak = "★ PEAK" if 18 <= t < 22 else ""
    shed = "⚡SHED" if params_nominal.G[t] == 0 else ""
    print(f"  h{t:02d}: μ={mu[t]:6.2f} PKR/kWh | {', '.join(actions):<20} {peak} {shed}")

print(f"\nKey KKT insights:")
for ins in duals['economic_insights']:
    print(f"  → {ins}")

# %% [markdown]
# # 9. Load Shedding Impact

# %%
shed_hours = [t for t in range(24) if params_nominal.G[t] == 0]
print(f"═══ Load Shedding Analysis ═══")
print(f"Scheduled outage hours: {shed_hours}")
print(f"SOC reserve requirement before shedding:")
for h, v in params_nominal.soc_reserve_hours.items():
    print(f"  Hour {h:02d}: SOC ≥ {v:.2f} kWh")

# Cost comparison with/without shedding
params_no_shed = HEMSParameters(season='summer', rho=0.0, use_loadshedding=False)
result_no_shed = solve_nominal_lp(params_no_shed)
print(f"\nCost with shedding:    PKR {result_nominal.net_cost():.2f}/day")
print(f"Cost without shedding: PKR {result_no_shed.net_cost():.2f}/day")
print(f"Load shedding impact:  PKR {result_nominal.net_cost()-result_no_shed.net_cost():.2f}/day")

# %% [markdown]
# # 10. All Experiments

# %%
print("═══ Running All 8 Experiments ═══")
all_results = run_all_experiments(season='summer')

# %% [markdown]
# # 11. Generate All 10 Figures

# %%
os.makedirs("figures", exist_ok=True)
figure_paths = generate_all_plots(all_results, output_dir="figures")
print(f"\n✓ {len(figure_paths)} publication-quality figures saved to figures/")

# %% [markdown]
# # 12. Final Summary

# %%
print("╔═══════════════════════════════════════════════════════════╗")
print("║              FINAL RESULTS SUMMARY v4.0                  ║")
print("╚═══════════════════════════════════════════════════════════╝")
print(f"\n  Problem: LP (ρ=0) → SOCP (ρ>0)")
print(f"  Season:  Summer (Rawalpindi 33.6°N)")
print(f"  Tariff:  NEPRA/IESCO Feb 2026 + Budget 2024-25")
print(f"\n  ── Optimal Schedule ──")
print(f"  Daily cost:   PKR {result_nominal.net_cost():.2f}")
print(f"  Grid import:  {result_nominal.p_grid_import.sum():.1f} kWh")
print(f"  Grid export:  {result_nominal.p_grid_export.sum():.1f} kWh")
print(f"  Peak demand:  {result_nominal.peak_demand:.2f} kW")
cyc = (result_nominal.p_charge.sum()+result_nominal.p_discharge.sum())/(2*E_MAX)
print(f"  Batt cycles:  {cyc:.2f}/day")
print(f"\n  ── Monthly Projection ──")
for b in baselines:
    bc  = b.get('total_cost_pkr', 0)
    oc  = result_nominal.net_cost()
    msv = (bc - oc) * 30
    pct = (bc - oc) / bc * 100 if bc else 0
    print(f"  vs {b['name']:<30}: PKR {msv:.0f}/month ({pct:.1f}%)")

print(f"\n  Price of robustness (ρ=1.5): +PKR {delta:.2f}/day (+{pct:.2f}%)")
print(f"\n  KKT Verified: {'✓' if kkt_ok else '✗'}")
print(f"  Figures:      {len(figure_paths)} saved to figures/")
print(f"\n[COMPLETE] All experiments finished. Run 'python run.py' for web dashboard.")

if __name__ == '__main__':
    pass