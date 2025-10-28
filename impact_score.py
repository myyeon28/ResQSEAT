# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# impact_score.py
# Description: Calculates a weighted impact score (0-50) for each seat
# based on the G-force data from all 4 sensors.

import json, time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

SEATS = ("S1", "S2", "S3", "S4")

# Corner proximity weights
# W[Seat_to_Calculate][Sensor_Location]
W = {
    "S1": [1.00, 0.60, 0.40, 0.20], # S1_calc = 1.0*S1_g + 0.6*S2_g + ...
    "S2": [0.60, 1.00, 0.20, 0.40],
    "S3": [0.40, 0.20, 1.00, 0.60],
    "S4": [0.20, 0.40, 0.60, 1.00],
}

def impact_score_0_50(I_seat_g: float) -> float:
    """
    Scales the raw weighted G-force to a score from 0-50.
    - 1.5g or less = 0 points
    - 5.0g or more = 50 points
    - Linear scaling between 1.5g and 5.0g
    """
    I_eff = max(0.0, I_seat_g - 1.5) # Effective G-force (ignore below 1.5)
    # Scale: (I_eff / (5.0_max - 1.5_min))
    # We use (5.0 - 1.5) = 3.5 as the scaling range
    scale_range = 5.0 - 1.5
    if scale_range <= 0: return 0.0 # Avoid division by zero

    scaled_score = 50.0 * (I_eff / scale_range)
    return min(scaled_score, 50.0) # Cap at 50

def _compute_impacts_from_sg_list(Sg: list) -> Tuple[float, float, float, float]:
    """Helper function: Computes scores from a simple list of 4 G-values."""
    # Sg: [g_S1, g_S2, g_S3, g_S4]
    impacts = []
    for i, seat in enumerate(SEATS): # "S1", "S2", ...
        # Get the weights for this seat
        weights = W[seat] # e.g., [1.00, 0.60, 0.40, 0.20] for S1

        # Calculate weighted sum
        I_g = sum(weights[j] * Sg[j] for j in range(4))

        # Convert to 0-50 score
        impacts.append(impact_score_0_50(I_g))

    return tuple(impacts)  # (S1_score, S2_score, S3_score, S4_score)

# --- [NEW] Main Function (to be imported by main.py) ---
def calculate_impact_scores(seat_data_dict: Dict[str, Dict[str, Any]]) -> Tuple[float, float, float, float]:
    """
    Calculates the weighted impact score for all seats given the raw
    seat data dictionary from the moment of impact.

    Args:
        seat_data_dict (Dict): The dictionary from get_arduino_data,
                               e.g., {"S1": {"mpu_g": 5.2, ...}, ...}

    Returns:
        Tuple[float, float, float, float]: (S1_impact, S2_impact, S3_impact, S4_impact)
                                           scores, each 0-50.
    """

    # 1. Extract the G-values into a list in the correct order [S1, S2, S3, S4]
    Sg = []
    try:
        for seat in SEATS:
            g_val = float(seat_data_dict.get(seat, {}).get("mpu_g", 0.0))
            Sg.append(g_val)
    except Exception as e:
        print(f"[impact_score] Error extracting G-values: {e}")
        # Return (0,0,0,0) on failure
        return (0.0, 0.0, 0.0, 0.0)

    # 2. Compute and return the scores
    return _compute_impacts_from_sg_list(Sg)


# --- [MODIFIED] Test block ---
if __name__ == "__main__":
    print("Running impact_score.py directly (Test Mode)")

    # 1. Mock trigger data (e.g., heavy front-left impact, near S2/S4)
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

    # 2. Calculate scores
    s1_imp, s2_imp, s3_imp, s4_imp = calculate_impact_scores(mock_trigger_data)

    # 3. Show results (scores 0-50)
    print("\n--- Final Impact Scores (0-50) ---")
    print(f"S1_impact: {s1_imp:.2f}") # (1*3.0 + 0.6*6.0 + 0.4*2.0 + 0.2*5.5) = 8.5 -> score 50
    print(f"S2_impact: {s2_imp:.2f}") # (0.6*3.0 + 1*6.0 + 0.2*2.0 + 0.4*5.5) = 10.4 -> score 50
    print(f"S3_impact: {s3_imp:.2f}") # (0.4*3.0 + 0.2*6.0 + 1*2.0 + 0.6*5.5) = 7.7 -> score 50
    print(f"S4_impact: {s4_imp:.2f}") # (0.2*3.0 + 0.4*6.0 + 0.6*2.0 + 1*5.5) = 9.7 -> score 50
    # Note: The raw weighted Gs are high (e.g., 8.5g), which is > 5.0g, so all scores are capped at 50.
