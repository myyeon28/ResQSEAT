# -*- coding: utf-8 -*-
#seat_status.py

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Any

try:
    import get_arduino_data
except ImportError:
    print("Error: Could not import get_arduino_data.py.")
    def get_latest_seat_data(): return {}

WEIGHT_THRESHOLD_KG = 5.0
SEATS = ["S1", "S2", "S3", "S4"]

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def normalize_age_code(x):
    try:
        if x is None:
            return 2
        xi = int(x)
        if xi in (0, 1, 2):
            return xi
        return 2
    except Exception:
        return 2

def get_seat_status(age_tuple: Tuple[int, int, int, int],
                      seats_data_dict: Dict[str, Dict[str, Any]]) -> Tuple[int, int, int, int]:

    age_codes = {
        "S1": normalize_age_code(age_tuple[0]),
        "S2": normalize_age_code(age_tuple[1]),
        "S3": normalize_age_code(age_tuple[2]),
        "S4": normalize_age_code(age_tuple[3]),
    }

    sit_status_map = {}
    for seat in SEATS:
        weight = 0.0
        try:
            weight = safe_float(seats_data_dict.get(seat, {}).get("Weight", 0.0), default=0.0)
        except Exception:
            weight = 0.0

        age_code = age_codes.get(seat, 2)

        sit_status = 0

        if (weight > WEIGHT_THRESHOLD_KG) and (age_code == 0 or age_code == 1):
            sit_status = 1

        sit_status_map[seat] = sit_status

    return (
        sit_status_map.get("S1", 0),
        sit_status_map.get("S2", 0),
        sit_status_map.get("S3", 0),
        sit_status_map.get("S4", 0)
    )

if __name__ == "__main__":
    print("Running seat_status.py directly (Test Mode)")

    mock_ages = (1, 0, 2, 2)

    mock_weights = {
        "S1": {"Weight": 15.0, "mpu_g": 0.1},
        "S2": {"Weight": 60.0, "mpu_g": 0.1},
        "S3": {"Weight": 1.0, "mpu_g": 0.1},
        "S4": {"Weight": 20.0, "mpu_g": 0.1},
    }

    print(f"Mock Ages (S1-S4): {mock_ages}")
    print(f"Mock Weights (S1-S4): {[mock_weights.get(s, {}).get('Weight') for s in SEATS]}")

    s1_sit, s2_sit, s3_sit, s4_sit = get_seat_status(mock_ages, mock_weights)

    print("\n--- Final Sit Status Results (0=Empty, 1=Sit) ---")
    print(f"S1_sit: {s1_sit} (Expected: 1)")
    print(f"S2_sit: {s2_sit} (Expected: 1)")
    print(f"S3_sit: {s3_sit} (Expected: 0)")
    print(f"S4_sit: {s4_sit} (Expected: 0)")
