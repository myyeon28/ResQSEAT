# impact_score.py

import json, time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

SEATS = ("S1", "S2", "S3", "S4")

W = {
    "S1": [1.00, 0.60, 0.40, 0.20],
    "S2": [0.60, 1.00, 0.20, 0.40],
    "S3": [0.40, 0.20, 1.00, 0.60],
    "S4": [0.20, 0.40, 0.60, 1.00],
}

def impact_score_0_50(I_seat_g: float) -> float:
    I_eff = max(0.0, I_seat_g - 1.5)
    scale_range = 5.0 - 1.5
    if scale_range <= 0: return 0.0

    scaled_score = 50.0 * (I_eff / scale_range)
    return min(scaled_score, 50.0) # Cap at 50

def _compute_impacts_from_sg_list(Sg: list) -> Tuple[float, float, float, float]:
    impacts = []
    for i, seat in enumerate(SEATS):
        weights = W[seat]

        I_g = sum(weights[j] * Sg[j] for j in range(4))

        impacts.append(impact_score_0_50(I_g))

    return tuple(impacts)

def calculate_impact_scores(seat_data_dict: Dict[str, Dict[str, Any]]) -> Tuple[float, float, float, float]:
    Sg = []
    try:
        for seat in SEATS:
            g_val = float(seat_data_dict.get(seat, {}).get("mpu_g", 0.0))
            Sg.append(g_val)
    except Exception as e:
        print(f"[impact_score] Error extracting G-values: {e}")
        return (0.0, 0.0, 0.0, 0.0)

    return _compute_impacts_from_sg_list(Sg)

if __name__ == "__main__":
    print("Running impact_score.py directly (Test Mode)")

    mock_trigger_data = {
        "S1": {"Weight": 15.0, "mpu_g": 3.0},
        "S2": {"Weight": 60.0, "mpu_g": 6.0},
        "S3": {"Weight": 1.0,  "mpu_g": 2.0},
        "S4": {"Weight": 20.0, "mpu_g": 5.5},
    }

    print("Mock Input (Raw G-force):")
    print(f"S1: {mock_trigger_data['S1']['mpu_g']}g")
    print(f"S2: {mock_trigger_data['S2']['mpu_g']}g")
    print(f"S3: {mock_trigger_data['S3']['mpu_g']}g")
    print(f"S4: {mock_trigger_data['S4']['mpu_g']}g")

    s1_imp, s2_imp, s3_imp, s4_imp = calculate_impact_scores(mock_trigger_data)

    print("\n--- Final Impact Scores (0-50) ---")
    print(f"S1_impact: {s1_imp:.2f}")
    print(f"S2_impact: {s2_imp:.2f}")
    print(f"S3_impact: {s3_imp:.2f}")
    print(f"S4_impact: {s4_imp:.2f}")
