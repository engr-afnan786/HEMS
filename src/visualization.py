"""
HEMS Visualization v4.0
Generates 10 publication-quality matplotlib figures (from Doc3).
Used by main.py for academic output.
Web dashboard uses Plotly in frontend.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')   # non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import os

plt.rcParams.update({
    'figure.figsize': (12, 6), 'figure.dpi': 150,
    'font.size': 11, 'font.family': 'serif',
    'axes.grid': True, 'grid.alpha': 0.3,
    'axes.spines.top': False, 'axes.spines.right': False,
})

COLORS = {
    'solar':      '#F4A300', 'battery_ch': '#2196F3',
    'battery_dis':'#4CAF50', 'grid_imp':   '#E53935',
    'grid_exp':   '#7B1FA2', 'load':       '#37474F',
    'soc':        '#00897B', 'peak':       '#FF6F00',
    'offpeak':    '#1565C0', 'tariff':     '#D32F2F',
    'dual':       '#6A1B9A',
}
HOURS      = np.arange(24)
HOUR_LABELS= [f"{h:02d}" for h in range(24)]


def save_fig(fig, name, output_dir="figures"):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}.png")
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  [saved] {path}")
    return path


def plot_optimal_schedule(result, p_load, p_pv, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.fill_between(HOURS, 0, p_pv, alpha=0.4, color=COLORS['solar'], label='Solar PV')
    ax.fill_between(HOURS, p_pv, p_pv + result.p_grid_import, alpha=0.4,
                    color=COLORS['grid_imp'], label='Grid Import')
    total_load = (p_load + 1.5*result.x_wash + 3.0*result.x_heater
                  + 1.2*result.x_dishwasher)
    ax.plot(HOURS, total_load, 'k-', linewidth=2.5, label='Total Load', zorder=5)
    ax.plot(HOURS, p_load,    'k--', linewidth=1.5, alpha=0.5, label='Fixed Load')
    ax.fill_between(HOURS, 0, -result.p_charge, alpha=0.4,
                    color=COLORS['battery_ch'], label='Battery Charge')
    ax.fill_between(HOURS, -result.p_charge,
                    -result.p_charge - result.p_grid_export, alpha=0.4,
                    color=COLORS['grid_exp'], label='Grid Export')
    ax.axvspan(18, 22, alpha=0.08, color='red', label='Peak (18-22h)')
    # Load shedding shading
    G = getattr(result, 'G', np.ones(24))
    for t in range(24):
        if G[t] == 0:
            ax.axvspan(t, t+1, alpha=0.12, color='black')
    ax.set_xlabel('Hour of Day', fontsize=13)
    ax.set_ylabel('Power (kW)', fontsize=13)
    ax.set_title('Optimal 24-Hour Energy Schedule — HEMS Pakistan v4.0',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(HOURS)
    ax.set_xticklabels(HOUR_LABELS, fontsize=8)
    ax.legend(loc='upper left', fontsize=8, ncol=2)
    ax.axhline(0, color='k', linewidth=0.8)
    plt.tight_layout()
    return save_fig(fig, "01_optimal_schedule", output_dir)


def plot_soc_trajectory(result, E_max=13.5, E_min=2.7, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(12, 5))
    h25 = np.arange(25)
    ax.plot(h25, result.soc, '-o', color=COLORS['soc'], linewidth=2.5,
            markersize=5, label='SOC', zorder=5)
    ax.axhline(E_max, color='red', linestyle='--', linewidth=1.5, alpha=0.7,
               label=f'E_max = {E_max} kWh')
    ax.axhline(E_min, color='orange', linestyle='--', linewidth=1.5, alpha=0.7,
               label=f'E_min = {E_min} kWh (20% DoD)')
    ax.fill_between(h25, E_min, result.soc, alpha=0.15, color=COLORS['soc'])
    ax.axvspan(18, 22, alpha=0.08, color='red')
    ax.set_xlabel('Hour', fontsize=13)
    ax.set_ylabel('SOC (kWh)', fontsize=13)
    ax.set_title('Battery State of Charge Trajectory', fontsize=14, fontweight='bold')
    ax.set_xticks(h25)
    ax.set_xticklabels([f"{h%24:02d}" for h in h25], fontsize=8)
    ax.set_ylim(0, E_max * 1.1)
    ax.legend(fontsize=10)
    plt.tight_layout()
    return save_fig(fig, "02_soc_trajectory", output_dir)


def plot_grid_profile(result, tariff, output_dir="figures"):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                   gridspec_kw={'height_ratios': [3, 1]})
    colors_imp = [COLORS['peak'] if 18 <= h < 22 else COLORS['offpeak']
                  for h in range(24)]
    ax1.bar(HOURS, result.p_grid_import, color=colors_imp, alpha=0.7, label='Grid Import')
    ax1.bar(HOURS, -result.p_grid_export, color=COLORS['grid_exp'], alpha=0.7,
            label='Grid Export')
    ax1.axhline(0, color='k', linewidth=0.8)
    ax1.set_ylabel('Power (kW)')
    ax1.set_title('Grid Power Exchange Profile', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.set_xticks(HOURS)
    ax1.set_xticklabels(HOUR_LABELS, fontsize=8)
    ax2.step(HOURS, tariff, where='mid', color=COLORS['tariff'], linewidth=2)
    ax2.fill_between(HOURS, tariff, step='mid', alpha=0.15, color=COLORS['tariff'])
    ax2.set_xlabel('Hour')
    ax2.set_ylabel('PKR/kWh')
    ax2.set_title('Effective TOU Tariff (with GST + FCA + QTA)')
    ax2.set_xticks(HOURS)
    ax2.set_xticklabels(HOUR_LABELS, fontsize=8)
    plt.tight_layout()
    return save_fig(fig, "03_grid_profile", output_dir)


def plot_dual_variables(result, tariff, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(12, 6))
    mu = np.abs(result.energy_balance_duals)
    ax.plot(HOURS, mu, '-s', color=COLORS['dual'], linewidth=2.5,
            markersize=6, label='Shadow Price |μ_t| (dual)', zorder=5)
    ax.step(HOURS, tariff, where='mid', color=COLORS['tariff'],
            linewidth=2, alpha=0.7, label='TOU Tariff c_t')
    ax.axvspan(18, 22, alpha=0.08, color='red')
    peak_mu = np.mean(mu[18:22])
    ax.annotate(f'Peak avg: {peak_mu:.1f}', xy=(20, peak_mu),
                fontsize=9, color=COLORS['dual'])
    ax.set_xlabel('Hour', fontsize=13)
    ax.set_ylabel('PKR/kWh', fontsize=13)
    ax.set_title('Dual Variables (Shadow Prices) vs TOU Tariff — KKT Verification',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(HOURS)
    ax.set_xticklabels(HOUR_LABELS, fontsize=8)
    ax.legend(fontsize=11)
    plt.tight_layout()
    return save_fig(fig, "04_dual_variables", output_dir)


def plot_cost_comparison(optimal_result, baselines, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(11, 6))
    strategies  = ['Convex\nOptimal']
    costs       = [optimal_result.net_cost()]
    colors_list = ['#2E7D32']

    for b in baselines:
        strategies.append(b.get('name', '?').replace(' ', '\n'))
        costs.append(b.get('total_cost_pkr', 0))
        colors_list.append('#757575')

    y_pos = np.arange(len(strategies))
    bars  = ax.barh(y_pos, costs, color=colors_list, alpha=0.8, height=0.6)

    opt = costs[0]
    for i, (bar, cost) in enumerate(zip(bars, costs)):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height()/2,
                f'PKR {cost:.0f}', va='center', fontsize=9, fontweight='bold')
        if i > 0 and cost > 0:
            pct = (cost - opt) / cost * 100
            ax.text(cost * 0.5, y_pos[i],
                    f'−{pct:.1f}%', va='center', ha='center',
                    fontsize=8, color='white', fontweight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(strategies, fontsize=9)
    ax.set_xlabel('Daily Cost (PKR)', fontsize=12)
    ax.set_title('Cost Comparison: Convex Optimization vs All Baselines',
                 fontsize=13, fontweight='bold')
    ax.invert_yaxis()
    plt.tight_layout()
    return save_fig(fig, "05_cost_comparison", output_dir)


def plot_pareto_frontier(rho_results, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(10, 6))
    rhos  = [r['rho'] for r in rho_results if r['feasible']]
    costs = [r['cost'] for r in rho_results if r['feasible']]

    ax.plot(rhos, costs, '-o', color='#1565C0', linewidth=2.5, markersize=8, zorder=5)
    ax.fill_between(rhos, costs, alpha=0.1, color='#1565C0')
    if rhos:
        ax.scatter([rhos[0]], [costs[0]], color='#2E7D32', s=120, zorder=6,
                   label='Nominal LP (ρ=0)')
    for i, (r, c) in enumerate(zip(rhos, costs)):
        off = (5, 10) if i % 2 == 0 else (5, -15)
        ax.annotate(f'PKR {c:.0f}', xy=(r, c), xytext=off,
                    textcoords='offset points', fontsize=9, color='#1565C0')

    ax.set_xlabel('Uncertainty Radius ρ (kWh)', fontsize=13)
    ax.set_ylabel('Total Daily Cost (PKR)', fontsize=13)
    ax.set_title('Pareto Frontier: Cost vs. Robustness', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    plt.tight_layout()
    return save_fig(fig, "06_pareto_frontier", output_dir)


def plot_battery_value(battery_results, ref_cost, output_dir="figures"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    sizes   = [r['E_max'] for r in battery_results if r['feasible']]
    costs   = [r['cost']  for r in battery_results if r['feasible']]
    savings = [ref_cost - c for c in costs]

    ax1.plot(sizes, costs, '-o', color='#E53935', linewidth=2.5, markersize=7)
    ax1.set_xlabel('Battery Capacity (kWh)')
    ax1.set_ylabel('Daily Cost (PKR)')
    ax1.set_title('Daily Cost vs Battery Capacity', fontweight='bold')

    ax2.plot(sizes, savings, '-o', color='#2E7D32', linewidth=2.5, markersize=7)
    if 13.5 in sizes:
        idx = sizes.index(13.5)
        ax2.axvline(x=13.5, color='gray', linestyle=':', alpha=0.5)
        ax2.annotate('13.5 kWh\n(Powerwall)', xy=(13.5, savings[idx]),
                     fontsize=9, ha='center')
    ax2.set_xlabel('Battery Capacity (kWh)')
    ax2.set_ylabel('Daily Savings vs No-Battery (PKR)')
    ax2.set_title('Marginal Value of Battery Storage', fontweight='bold')
    plt.tight_layout()
    return save_fig(fig, "07_battery_value", output_dir)


def plot_shiftable_schedule(result, output_dir="figures"):
    fig, ax = plt.subplots(figsize=(12, 4))
    apps = [
        ('Washing Machine', result.x_wash,      '#2196F3', 1.5),
        ('Water Heater',    result.x_heater,     '#FF9800', 3.0),
        ('Dishwasher',      result.x_dishwasher, '#9C27B0', 1.2),
    ]
    for i, (name, sched, color, power) in enumerate(apps):
        for t in range(24):
            if sched[t] > 0.1:
                ax.barh(i, sched[t], left=t, height=0.6, color=color, alpha=0.8)
                ax.text(t + 0.5, i, f'{power}kW', ha='center', va='center',
                        fontsize=8, color='white', fontweight='bold')
    ax.set_yticks(range(len(apps)))
    ax.set_yticklabels([a[0] for a in apps])
    ax.set_xlabel('Hour')
    ax.set_title('Optimized Shiftable Load Schedule (Shifted to Solar/Off-Peak Hours)',
                 fontsize=13, fontweight='bold')
    ax.set_xticks(HOURS)
    ax.set_xticklabels(HOUR_LABELS, fontsize=8)
    ax.set_xlim(0, 24)
    ax.axvspan(18, 22, alpha=0.08, color='red', label='Peak Hours')
    ax.legend(fontsize=9)
    plt.tight_layout()
    return save_fig(fig, "08_shiftable_schedule", output_dir)


def plot_seasonal_comparison(seasonal_results, output_dir="figures"):
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for col, season in enumerate(['summer', 'winter']):
        data = seasonal_results[season]
        r    = data.get('result')
        if r is None or not r.feasible:
            continue

        ax = axes[0, col]
        load  = data['load']
        solar = data['solar']
        ax.fill_between(HOURS, 0, solar, alpha=0.4, color=COLORS['solar'], label='Solar')
        ax.fill_between(HOURS, solar, solar + r.p_grid_import, alpha=0.4,
                        color=COLORS['grid_imp'], label='Grid Import')
        ax.plot(HOURS, load, 'k-', linewidth=2, label='Load')
        ax.set_title(f'{season.title()} — Energy Schedule', fontweight='bold')
        ax.set_ylabel('Power (kW)')
        ax.legend(fontsize=8)

        ax = axes[1, col]
        ax.plot(np.arange(25), r.soc, '-o', color=COLORS['soc'],
                linewidth=2, markersize=4)
        ax.axhline(13.5, color='red', linestyle='--', alpha=0.5)
        ax.axhline(2.7,  color='orange', linestyle='--', alpha=0.5)
        ax.set_title(f'{season.title()} — Battery SOC', fontweight='bold')
        ax.set_ylabel('SOC (kWh)')
        ax.set_xlabel('Hour')
        ax.set_ylim(0, 15)

    fig.suptitle('Seasonal Comparison: Summer vs Winter Strategies',
                 fontsize=16, fontweight='bold')
    plt.tight_layout()
    return save_fig(fig, "09_seasonal_comparison", output_dir)


def plot_billing_comparison(billing_results, output_dir="figures"):
    """NEW: Policy analysis plot (Doc2 + Doc3)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    modes  = list(billing_results.keys())
    costs  = [billing_results[m].get('cost', 0) or 0 for m in modes]
    labels = {'net_metering': 'Net Metering\nPKR 19.32/kWh',
              'gross_metering': 'Gross Metering\nPKR 10.00/kWh',
              'capacity_tax': 'Capacity Tax\nPKR 2000/kW/mo'}
    xlabels = [labels.get(m, m) for m in modes]
    colors  = ['#2E7D32', '#F57F17', '#C62828']

    bars = ax.bar(xlabels, costs, color=colors, alpha=0.85, width=0.5)
    for bar, cost in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                f'PKR {cost:.0f}', ha='center', fontsize=11, fontweight='bold')

    ax.set_ylabel('Daily Cost (PKR)', fontsize=12)
    ax.set_title('Policy Comparison: Net vs Gross Metering vs Capacity Tax\n'
                 '(Pakistan AEDB 2024 + IMF pressure scenarios)',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    return save_fig(fig, "10_billing_comparison", output_dir)


def generate_all_plots(all_results, output_dir="figures"):
    """Generate all 10 publication-quality figures."""
    print("\n╔══════════════════════════════╗")
    print("║  Generating All Figures     ║")
    print("╚══════════════════════════════╝\n")

    opt      = all_results.get('optimal')
    blines   = all_results.get('baselines', [])
    seasonal = all_results.get('exp5_seasonal', {})

    # Get load/solar from the optimal params
    from .parameters import generate_load_profile, generate_solar_profile, get_tariff_vector
    p_load = generate_load_profile("summer")
    p_pv   = generate_solar_profile("summer")
    tariff = get_tariff_vector()

    paths = []
    if opt and opt.feasible:
        paths.append(plot_optimal_schedule(opt, p_load, p_pv, output_dir))
        paths.append(plot_soc_trajectory(opt, output_dir=output_dir))
        paths.append(plot_grid_profile(opt, tariff, output_dir))
        paths.append(plot_dual_variables(opt, tariff, output_dir))
    if blines and opt and opt.feasible:
        paths.append(plot_cost_comparison(opt, blines, output_dir))

    rob = all_results.get('exp1_robustness', [])
    if rob:
        paths.append(plot_pareto_frontier(rob, output_dir))

    batt, ref_cost = all_results.get('exp2_battery', ([], 0))
    if batt:
        paths.append(plot_battery_value(batt, ref_cost, output_dir))

    if opt and opt.feasible:
        paths.append(plot_shiftable_schedule(opt, output_dir))

    if seasonal:
        paths.append(plot_seasonal_comparison(seasonal, output_dir))

    billing = all_results.get('exp8_billing', {})
    if billing:
        paths.append(plot_billing_comparison(billing, output_dir))

    print(f"\n✓ {len(paths)} figures saved to {output_dir}/")
    return paths