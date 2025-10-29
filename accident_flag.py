# -*- coding: utf-8 -*-
# accident_flag.py

import json, time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import get_arduino_data
except ImportError:
    print("Error: Could not import get_arduino_data.py.")
    def get_latest_seat_data():
        time.sleep(0.1)
        if time.time() % 10 > 5:
             return {"S1":{"mpu_g":0.1}, "S2":{"mpu_g":0.2}, "S3":{"mpu_g":0.1}, "S4":{"mpu_g":0.1}}
        else:
             return {"S1":{"mpu_g":5.0}, "S2":{"mpu_g":0.2}, "S3":{"mpu_g":0.1}, "S4":{"mpu_g":0.1}}

ACCIDENT_G_THRESH = 1.1
SEATS = ("S1", "S2", "S3", "S4")
POLL_INTERVAL = 0.01

def wait_accident_flag(timeout_s: Optional[float] = None,
                       thresh: float = ACCIDENT_G_THRESH) -> Optional[Dict[str, Any]]:

    deadline = (time.time() + timeout_s) if timeout_s is not None else None

    last_data_ts = None

    while True:
        seats_data = get_arduino_data.get_latest_seat_data()

        if not seats_data or len(seats_data) < len(SEATS):
            time.sleep(0.1)
            continue

        try:
            for seat_name in SEATS:
                mpu_g = float(seats_data.get(seat_name, {}).get("mpu_g", 0.0))

                if mpu_g > thresh:
                    return seats_data

        except (ValueError, TypeError):
            pass

        if deadline is not None and time.time() > deadline:
            return None

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print(f"Waiting for accident flag (G > {ACCIDENT_G_THRESH})... (10s timeout)")

    trigger_data = wait_accident_flag(timeout_s=10)

    if trigger_data:
        print("\n--- ACCIDENT DETECTED ---")
        print("Trigger data:")
        print(json.dumps(trigger_data, indent=2))
    else:
        print("\n--- TIMEOUT ---")
        print("No accident detected.")
