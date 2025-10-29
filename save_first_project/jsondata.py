# -*- coding: utf-8 -*-
# jsondata.py

import json
from typing import Tuple

def _format_seat_data(age_val: int, uc_val: int, impact_val: float, sit_val: int):

    if sit_val == 0:
        return {
            "is_child": "empty",
            "is_conscious": "empty",
            "impact": "empty",
            "score": 0,
            "status": "empty"
        }

    age_points = 10 if age_val == 1 else 0
    uc_points = 50 if (uc_val == 1 or uc_val == 2) else 0
    impact_points = impact_val
    Sx_score = (age_points + uc_points + impact_points) * sit_val

    is_child = (age_val == 1)
    is_conscious = (uc_val == 0)

    final_data = {
        "is_child": is_child,
        "is_conscious": is_conscious,
        "impact": round(impact_points, 2),
        "score": round(Sx_score, 2),
        "status": "occupied"
    }
    return final_data

def get_all_seats_dict(s1_data: Tuple, s2_data: Tuple, s3_data: Tuple, s4_data: Tuple) -> dict:
    all_seats_data = {
        "seat1": _format_seat_data(*s1_data),
        "seat2": _format_seat_data(*s2_data),
        "seat3": _format_seat_data(*s3_data),
        "seat4": _format_seat_data(*s4_data)
    }
    return all_seats_data

if __name__ == "__main__":
    s1_test = (1, 1, 50, 1)
    s2_test = (0, 0, 20, 1)
    s3_test = (0, 0, 15, 0)
    s4_test = (0, 2, 30, 1)

    combined_dict = get_all_seats_dict(s1_test, s2_test, s3_test, s4_test)

    print("--- Combined Dictionary Output (Server Format) ---")
    print(json.dumps(combined_dict, indent=4))
