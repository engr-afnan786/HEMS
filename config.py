"""
HEMS Configuration
Handles all environment variables and Pakistan-specific constants
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG        = os.getenv('DEBUG', 'True') == 'True'
    HOST         = os.getenv('HOST', '0.0.0.0')
    PORT         = int(os.getenv('PORT', 5000))
    SECRET_KEY   = os.getenv('SECRET_KEY', 'hems-dev-key')

    # MQTT Hardware Control
    MQTT_BROKER  = os.getenv('MQTT_BROKER', 'localhost')
    MQTT_PORT    = int(os.getenv('MQTT_PORT', 1883))
    MQTT_TOPIC   = os.getenv('MQTT_TOPIC', 'hems/inverter/control')
    MQTT_ENABLED = os.getenv('MQTT_ENABLED', 'False') == 'True'


class PakistanEnergyPolicy:
    """
    Pakistan Energy Policy Parameters
    Sources:
    - NEPRA IESCO Tariff Schedule Feb 2026
    - Finance Act 2024-25 (Budget)
    - AEDB Net Metering Regulations 2024
    - IMF Article IV Consultation 2024 (policy risks)
    """

    # ── Time-of-Use Base Tariffs ─────────────────────────────────────
    PEAK_TARIFF_BASE     = 46.85   # PKR/kWh, 18:00–22:00
    OFF_PEAK_TARIFF_BASE = 34.53   # PKR/kWh, 22:00–18:00
    PEAK_HOURS           = [18, 19, 20, 21]

    # ── Budget 2024-25 Additional Charges ────────────────────────────
    FUEL_COST_ADJ        = 3.23    # PKR/kWh (FCA, Q1 FY24-25)
    CAPACITY_CHARGE      = 2.89    # PKR/kWh (CPP)
    QTA_RATE             = 1.85    # PKR/kWh (Quarterly Tariff Adj)
    GST_RATE             = 0.18    # 18% GST on >200 units/month
    NJ_SURCHARGE         = 0.10    # Neelum-Jhelum surcharge on fuel

    # ── Net Metering (AEDB 2024) ─────────────────────────────────────
    FEED_IN_TARIFF_NET   = 19.32   # PKR/kWh net metering
    FEED_IN_TARIFF_GROSS = 10.00   # PKR/kWh gross metering (proposed)

    # ── Solar Capacity Tax (IMF pressure, proposed) ──────────────────
    SOLAR_CAPACITY_TAX   = 2000.0  # PKR/kW/month installed solar
    # Toggle: 'net_metering', 'gross_metering', 'capacity_tax'
    DEFAULT_BILLING_MODE = 'net_metering'

    # ── Demand & Fixed Charges ────────────────────────────────────────
    DEMAND_CHARGE        = 400.0   # PKR/kW/month
    FIXED_CHARGE_MONTHLY = 35.0    # PKR/month (TV fee etc)

    # ── Load Shedding Schedule (Rawalpindi 2024) ─────────────────────
    # G_t = 1 → grid available, G_t = 0 → load shedding
    LOADSHEDDING_SUMMER = {
        # hour: probability of outage
        13: 0.7, 14: 0.9, 15: 0.8,   # afternoon
        19: 0.6, 20: 0.5              # evening
    }
    LOADSHEDDING_WINTER = {
        7: 0.5, 8: 0.4,               # morning
        19: 0.7, 20: 0.8              # evening
    }

    # ── Minimum SOC reserve during load shedding ─────────────────────
    SOC_LOADSHED_RESERVE = 0.40    # keep 40% SOC before shedding hours

    # ── Battery Parameters (Tesla Powerwall equivalent) ──────────────
    E_MAX_DEFAULT        = 13.5    # kWh
    E_MIN_RATIO          = 0.20    # 20% DoD protection
    PC_MAX               = 5.0     # kW max charge
    PD_MAX               = 5.0     # kW max discharge
    ETA_C                = 0.95    # charge efficiency
    ETA_D                = 0.95    # discharge efficiency
    P_EXPORT_MAX         = 5.0     # kW IESCO export limit
    DEGRADATION_COST     = 2.0     # PKR/kWh throughput

    # ── Solar Parameters ─────────────────────────────────────────────
    PV_RATED_DEFAULT     = 10.0    # kW
    LATITUDE_RAWALPINDI  = 33.6    # degrees N
    PEAK_SUN_HOURS       = 5.5     # hours/day

    @classmethod
    def effective_peak(cls, use_gst=True, use_fca=True):
        base = cls.PEAK_TARIFF_BASE
        if use_fca:
            base += cls.FUEL_COST_ADJ + cls.CAPACITY_CHARGE + cls.QTA_RATE
        if use_gst:
            base *= (1 + cls.GST_RATE)
        return round(base, 4)

    @classmethod
    def effective_offpeak(cls, use_gst=True, use_fca=True):
        base = cls.OFF_PEAK_TARIFF_BASE
        if use_fca:
            base += cls.FUEL_COST_ADJ + cls.CAPACITY_CHARGE + cls.QTA_RATE
        if use_gst:
            base *= (1 + cls.GST_RATE)
        return round(base, 4)