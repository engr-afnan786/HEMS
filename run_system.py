"""
HEMS Master Controller — Real-Time MQTT Control Loop
Runs optimization every hour and publishes to ESP32 inverter.
Usage: python run_system.py
"""

import time
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from src.parameters import HEMSParameters
from src.solver import run_optimization
from src.baselines import baseline_greedy

# Optional MQTT
mqtt_available = False
if Config.MQTT_ENABLED:
    try:
        import paho.mqtt.client as mqtt
        mqtt_available = True
    except ImportError:
        print("[WARN] paho-mqtt not installed. Running without hardware control.")

client = None
if mqtt_available:
    client = mqtt.Client("HEMS_Brain")
    try:
        client.connect(Config.MQTT_BROKER, Config.MQTT_PORT, keepalive=60)
        client.loop_start()
        print(f"[MQTT] Connected to {Config.MQTT_BROKER}:{Config.MQTT_PORT}")
    except Exception as e:
        print(f"[MQTT] Connection failed: {e}. Running in simulation mode.")
        client = None


def get_season():
    import time as t
    month = t.localtime().tm_mon
    return 'summer' if month in [5, 6, 7, 8, 9] else 'winter'


def control_loop():
    print("[HEMS] Starting control loop. Press Ctrl+C to stop.")
    cycle = 0
    while True:
        cycle += 1
        print(f"\n[HEMS] Optimization cycle #{cycle}")

        try:
            season = get_season()
            params = HEMSParameters(
                season=season,
                use_loadshedding=True,
                billing_mode='net_metering'
            )
            state = params.get_current_state()
            print(f"[HEMS] State: {state}")

            # Run convex optimization
            schedule = run_optimization(params)

            if schedule.get('feasible'):
                current_h = state['current_hour']
                charge_kw    = schedule['p_charge'][current_h]
                discharge_kw = schedule['p_discharge'][current_h]
                soc_now      = schedule['soc'][current_h]
                cost_today   = schedule['total_cost_pkr']
                solver_used  = schedule['solver']

                print(f"[HEMS] Hour {current_h:02d}:00 | "
                      f"Charge: {charge_kw:.2f}kW | "
                      f"Discharge: {discharge_kw:.2f}kW | "
                      f"SOC: {soc_now:.2f}kWh | "
                      f"Cost: PKR {cost_today:.0f}/day | "
                      f"Solver: {solver_used}")

                # Publish to ESP32 via MQTT
                payload = {
                    'timestamp':    time.time(),
                    'hour':         current_h,
                    'charge_kw':    round(float(charge_kw), 2),
                    'discharge_kw': round(float(discharge_kw), 2),
                    'soc_kwh':      round(float(soc_now), 2),
                    'grid_ok':      int(state['grid_available']),
                    'solver':       solver_used
                }

                if client:
                    client.publish(Config.MQTT_TOPIC, json.dumps(payload))
                    print(f"[MQTT] Published: {payload}")
                else:
                    print(f"[SIM]  Would publish: {payload}")

            else:
                print("[WARN] Optimization failed — greedy fallback active.")
                fb = baseline_greedy(params)
                current_h = state['current_hour']
                print(f"[FB]  Charge: {fb['p_charge'][current_h]:.2f}kW | "
                      f"Discharge: {fb['p_discharge'][current_h]:.2f}kW")

        except KeyboardInterrupt:
            print("\n[HEMS] Shutting down control loop.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

        print(f"[HEMS] Sleeping 3600s until next cycle...")
        try:
            time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[HEMS] Shutting down.")
            break


if __name__ == '__main__':
    control_loop()