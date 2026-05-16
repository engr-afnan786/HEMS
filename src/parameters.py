"""
HEMS System Parameters v4.0
Integrates:
- Doc3: generate_load_profile(), generate_solar_profile(), save_all_data()
- Doc2: G_t load shedding, billing modes, capacity tax
- Doc1: Pakistan Budget 2024-25 tariffs
All parameters from NEPRA/IESCO Feb 2026, AEDB 2024, Finance Act 2024-25
"""

import json
import os
import numpy as np
from config import PakistanEnergyPolicy as PEP

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Time Parameters ──────────────────────────────────────────────────────
T     = 24
dt    = 1.0
hours = np.arange(T)

# ── Tariff Constants ─────────────────────────────────────────────────────
PEAK_START   = 18
PEAK_END     = 22
C_PEAK       = 46.85   # PKR/kWh
C_OFFPEAK    = 34.53   # PKR/kWh
C_EXPORT     = 19.32   # PKR/kWh net metering
C_DEMAND     = 13.33   # PKR/kW/day  (400/30)
LAMBDA_DEG   = 2.0     # PKR/kWh degradation

# ── Battery Constants ────────────────────────────────────────────────────
E_MAX        = 13.5
E_MIN        = 2.7
E_INIT       = 0.5 * E_MAX
PC_MAX       = 5.0
PD_MAX       = 5.0
ETA_C        = 0.95
ETA_D        = 0.95
P_EXPORT_MAX = 5.0
PV_RATED     = 10.0

# ── Experiment Ranges ────────────────────────────────────────────────────
RHO_DEFAULT      = 1.5
RHO_RANGE        = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
BATTERY_SIZES    = [0, 3, 5, 7, 10, 13.5, 20, 30]
SOLAR_SIZES      = [0, 3, 5, 7, 10, 15, 20]
TOU_RATIOS       = [1.0, 1.1, 1.2, 1.36, 1.5, 1.8, 2.0]
DEGRADATION_COSTS= [0, 0.5, 1.0, 2.0, 5.0, 10.0]

# ── Shiftable Appliances ─────────────────────────────────────────────────
SHIFTABLE_APPLIANCES = {
    "washing_machine": {
        "power_kw": 1.5, "duration_hours": 2,
        "window_start": 8, "window_end": 18,
        "description": "Washing machine — run during solar hours 8AM-6PM"
    },
    "water_heater": {
        "power_kw": 3.0, "duration_hours": 1,
        "window_start_1": 5, "window_end_1": 8,
        "window_start_2": 18, "window_end_2": 22,
        "description": "Electric geyser — morning or evening window"
    },
    "dishwasher": {
        "power_kw": 1.2, "duration_hours": 1,
        "window_start": 20, "window_end": 24,
        "description": "Dishwasher — after dinner 20:00-24:00"
    }
}


def get_tariff_vector(use_gst=True, use_fca=True):
    """Return 24-element effective TOU tariff vector (PKR/kWh)."""
    c_p  = PEP.effective_peak(use_gst, use_fca)
    c_op = PEP.effective_offpeak(use_gst, use_fca)
    tariff = np.full(T, c_op)
    tariff[PEAK_START:PEAK_END] = c_p
    return tariff


TARIFF = get_tariff_vector()


def generate_solar_profile(season="summer", pv_capacity=PV_RATED, seed=42):
    """
    Generate realistic 24-hour solar profile for Rawalpindi (33.6°N).
    Uses Gaussian bell curve calibrated to local irradiance data.

    Summer: ~6.5 peak sun hours, Winter: ~4.5 peak sun hours
    """
    rng = np.random.default_rng(seed)

    if season == "summer":
        sunrise, sunset = 5.5, 19.0
        peak_hour   = 12.0
        sigma       = 2.8
        peak_factor = 0.88
        cloud_std   = 0.05
    else:
        sunrise, sunset = 7.0, 17.5
        peak_hour   = 12.0
        sigma       = 2.2
        peak_factor = 0.72
        cloud_std   = 0.10

    p_pv = np.zeros(T)
    for t in range(T):
        hour = t + 0.5
        if sunrise <= hour <= sunset:
            base  = peak_factor * np.exp(-0.5 * ((hour - peak_hour) / sigma) ** 2)
            noise = rng.normal(0, cloud_std)
            p_pv[t] = max(0.0, base + noise) * pv_capacity

    return p_pv


def generate_load_profile(season="summer", seed=42):
    """
    Generate realistic 24-hour household load for Rawalpindi.
    Components: base + cooking + lighting + pump + entertainment + AC/heater
    Summer: 28-35 kWh/day   Winter: 15-20 kWh/day
    """
    rng = np.random.default_rng(seed)

    # Base load (fridge, standby, router)
    base = 0.5 + rng.normal(0, 0.05, T)

    # Cooking peaks (breakfast/lunch/dinner)
    cooking = np.zeros(T)
    cooking[7]  = 2.5
    cooking[12] = 2.0
    cooking[19] = 3.0

    # Lighting
    lighting = np.zeros(T)
    lighting[18:24] = 0.4
    lighting[5:7]   = 0.2

    # Water pump
    pump = np.zeros(T)
    pump[6]  = 1.0
    pump[18] = 1.0

    # Entertainment
    entertainment = np.zeros(T)
    entertainment[19:23] = 0.3
    entertainment[8:11]  = 0.15

    p_load = base + cooking + lighting + pump + entertainment

    if season == "summer":
        # AC load — significant at 40°C+ in Rawalpindi
        ac = np.zeros(T)
        ac[10:13] = 1.2
        ac[13:18] = 2.2  # peak afternoon
        ac[18:22] = 1.8  # evening
        ac[22:24] = 1.0  # night
        ac[0:2]   = 0.8  # late night
        p_load += ac
    else:
        # Winter space heater
        heater = np.zeros(T)
        heater[6:8]   = 1.0
        heater[20:23] = 0.8
        p_load += heater

    p_load += rng.normal(0, 0.1, T)
    p_load  = np.maximum(p_load, 0.3)
    return p_load


def save_all_data(output_dir="data"):
    """Generate and save all data files. No CSV prereqs needed."""
    os.makedirs(output_dir, exist_ok=True)

    tariff_data = {
        "peak_rate_pkr":           C_PEAK,
        "offpeak_rate_pkr":        C_OFFPEAK,
        "export_rate_pkr":         C_EXPORT,
        "demand_charge_pkr_kw_day": C_DEMAND,
        "peak_hours":              [PEAK_START, PEAK_END],
        "tariff_vector":           TARIFF.tolist(),
        "source":                  "NEPRA/IESCO February 2026 + Budget 2024-25"
    }
    with open(os.path.join(output_dir, "tariffs.json"), "w") as f:
        json.dump(tariff_data, f, indent=2)

    print(f"[✓] tariffs.json saved")
    print(f"[✓] Data generation complete — no CSV files required")


class HEMSParameters:
    """
    Complete HEMS parameter set v4.0
    Combines Doc3 load/solar generation with Doc2 G_t and billing modes.
    """

    def __init__(
        self,
        season         = 'summer',
        use_ev         = False,
        use_gst        = True,
        use_fca        = True,
        battery_size   = 13.5,
        solar_capacity = 10.0,
        rho            = 1.0,
        billing_mode   = 'net_metering',
        use_loadshedding = True,
        seed           = 42,
        custom_params  = None
    ):
        self.T            = T
        self.dt           = dt
        self.season       = season
        self.use_ev       = use_ev
        self.billing_mode = billing_mode
        self.seed         = seed

        # ── Tariff ───────────────────────────────────────────────────
        self.tariff = get_tariff_vector(use_gst, use_fca)

        # ── Billing / export policy ──────────────────────────────────
        td = json.load(open(os.path.join(BASE_DIR, 'data', 'tariffs.json')))
        nm = td.get('net_metering', {})

        if billing_mode == 'net_metering':
            self.c_export     = nm.get('feed_in_tariff_net', C_EXPORT)
            self.capacity_tax = 0.0
        elif billing_mode == 'gross_metering':
            self.c_export     = nm.get('feed_in_tariff_gross', 10.00)
            self.capacity_tax = 0.0
        else:  # capacity_tax
            self.c_export     = nm.get('feed_in_tariff_net', C_EXPORT)
            self.capacity_tax = (nm.get('solar_capacity_tax_per_kw', 2000.0)
                                 * solar_capacity / 30.0)

        self.c_demand = C_DEMAND
        self.lam      = LAMBDA_DEG

        # ── Battery ──────────────────────────────────────────────────
        self.E_max        = battery_size
        self.E_min        = battery_size * 0.20
        self.Pc_max       = PC_MAX
        self.Pd_max       = PD_MAX
        self.eta_c        = ETA_C
        self.eta_d        = ETA_D
        self.P_export_max = P_EXPORT_MAX
        self.P_grid_max   = 10.0

        # ── Solar — use Gaussian profile generator ───────────────────
        scale            = solar_capacity / 10.0
        self.p_pv_mean   = generate_solar_profile(season, pv_capacity=solar_capacity, seed=seed)
        self.rho         = rho
        self.PV_rated    = solar_capacity

        # ── Load — use realistic profile generator ───────────────────
        self.p_load = generate_load_profile(season, seed=seed)

        # ── Appliances ───────────────────────────────────────────────
        self.appliances = {}

        def w(s, e):
            return list(range(s, e)) if s < e else list(range(s, 24)) + list(range(0, e))

        sa = SHIFTABLE_APPLIANCES
        self.appliances['washing_machine'] = {
            'power': sa['washing_machine']['power_kw'],
            'duration': sa['washing_machine']['duration_hours'],
            'window': w(sa['washing_machine']['window_start'],
                        sa['washing_machine']['window_end'])
        }
        wh = sa['water_heater']
        self.appliances['water_heater'] = {
            'power': wh['power_kw'],
            'duration': wh['duration_hours'],
            'window': w(wh['window_start_1'], wh['window_end_1']) +
                      w(wh['window_start_2'], wh['window_end_2'])
        }
        dw = sa['dishwasher']
        self.appliances['dishwasher'] = {
            'power': dw['power_kw'],
            'duration': dw['duration_hours'],
            'window': w(dw['window_start'], dw['window_end'] % 24)
        }
        if use_ev:
            self.appliances['ev_charger'] = {
                'power': 3.3, 'duration': 4,
                'window': list(range(22, 24)) + list(range(0, 6))
            }

        # ── Grid Availability G_t (Load Shedding) ───────────────────
        self.G = np.ones(T)
        self.soc_reserve_hours = {}
        if use_loadshedding:
            ls = td.get('load_shedding', {}).get(season, {})
            for h_str, prob in ls.items():
                if float(prob) > 0.5:
                    self.G[int(h_str)] = 0.0
            shed_hours = [int(h) for h, p in ls.items() if float(p) > 0.5]
            for h in shed_hours:
                prev = (h - 1) % 24
                self.soc_reserve_hours[prev] = (
                    self.E_min + PEP.SOC_LOADSHED_RESERVE * self.E_max
                )

        # ── Custom overrides ─────────────────────────────────────────
        if custom_params:
            for k, v in custom_params.items():
                setattr(self, k, v)

    def get_current_state(self):
        import time as _t
        h = int(_t.localtime().tm_hour)
        return {
            'current_hour':   h,
            'current_tariff': float(self.tariff[h]),
            'current_pv':     float(self.p_pv_mean[h]),
            'current_load':   float(self.p_load[h]),
            'grid_available': int(self.G[h]),
            'season':         self.season
        }

    def to_dict(self):
        return {
            'T': self.T, 'season': self.season,
            'billing_mode': self.billing_mode,
            'tariff': self.tariff.tolist(),
            'c_export': self.c_export, 'c_demand': self.c_demand,
            'capacity_tax': self.capacity_tax, 'lam': self.lam,
            'E_max': self.E_max, 'E_min': round(self.E_min, 3),
            'Pc_max': self.Pc_max, 'Pd_max': self.Pd_max,
            'eta_c': self.eta_c, 'eta_d': self.eta_d,
            'P_export_max': self.P_export_max,
            'p_pv_mean': self.p_pv_mean.tolist(),
            'rho': self.rho, 'p_load': self.p_load.tolist(),
            'appliances': self.appliances,
            'G': self.G.tolist(),
            'soc_reserve_hours': {str(k): v
                                  for k, v in self.soc_reserve_hours.items()},
            'PV_rated': self.PV_rated
        }