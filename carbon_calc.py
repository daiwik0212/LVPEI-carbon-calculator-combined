"""
Tele-ophthalmology Carbon Footprint Calculator
Core calculation engine + dummy data generator.

Master equation:
    delta_E = E_counterfactual - E_teleconsultation

E_counterfactual  = d_alt   x 2 x modal_EF x (1 + accompanying_persons)
E_travel_to_VC    = d_vc    x 2 x modal_EF x (1 + accompanying_persons)
E_teleconsultation = E_travel_to_VC + E_device + E_digital

All emission factors and constants below are LOCKED assumptions from the
project brief (Rani et al. 2024, Kwon/Thiel 2024 JMIR, CEA v21.0).
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# LOCKED ASSUMPTIONS
# ---------------------------------------------------------------------------

GRID_EF_KGCO2_PER_KWH = 0.7117          # CEA CO2 Baseline Database v21.0, FY24-25
SESSION_DURATION_MIN = 10                # midpoint of Dr. Rani's 5-15 min range

TREE_ABSORPTION_KGCO2_PER_YEAR = 21.0
CAR_KM_EQUIV_KGCO2_PER_KM = 0.17
FLIGHT_EQUIV_KGCO2 = 130.0               # Delhi-Hyderabad, per passenger

# Transport mode emission factors (kgCO2e per passenger-km), Rani et al. 2024
TRANSPORT_EF = {
    "Two-wheeler":   0.059,
    "Car":           0.171,
    "Bus":           0.030,
    "Auto-rickshaw": 0.059,
    "Train":         0.012,
    "Air":           0.255,
    "Walk/cycle":    0.000,
}

# Device electricity (Scope 2) — default placeholders, replace when GPR
# technician supplies actual wattages
DEVICE_WATTAGE_DEFAULTS = {
    "Fundus camera": 45,
    "Slit lamp": 25,
    "Workstation + monitor": 120,
    "Router/networking": 15,
}
TOTAL_DEVICE_WATTAGE_W = sum(DEVICE_WATTAGE_DEFAULTS.values())  # 205 W
E_DEVICE_KGCO2 = (TOTAL_DEVICE_WATTAGE_W * SESSION_DURATION_MIN / 60000) * GRID_EF_KGCO2_PER_KWH

# Digital overhead (Scope 3) — default placeholder
DICOM_SIZE_MB_DEFAULT = 5
NETWORK_EF_KWH_PER_GB = 0.06
E_DIGITAL_KGCO2 = (DICOM_SIZE_MB_DEFAULT / 1024) * NETWORK_EF_KWH_PER_GB * GRID_EF_KGCO2_PER_KWH

# Default fill values when a row is missing an input
DEFAULTS = {
    "transport_mode": "Bus",
    "accompanying_persons": 0,
    "distance_to_vc_km": 15,
    "distance_to_alternative_km": 80,
}

# Which CSV columns already exist in eyeSmart vs. are newly proposed
EXISTING_EYESMART_COLUMNS = ["patient_id", "consultation_date", "triage_outcome"]
NEW_PROPOSED_COLUMNS = [
    "transport_mode",
    "accompanying_persons",
    "distance_to_vc_km",
    "distance_to_alternative_km",
]
EXPECTED_COLUMNS = EXISTING_EYESMART_COLUMNS + NEW_PROPOSED_COLUMNS

TRIAGE_BENCHMARK = {"Green": 0.84, "Yellow": 0.08, "Red": 0.08}


# ---------------------------------------------------------------------------
# DUMMY DATA GENERATOR
# ---------------------------------------------------------------------------

def generate_dummy_data(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Generate a realistic dummy eyeSmart-style CSV export for GPR Vision Centre."""
    rng = np.random.default_rng(seed)

    patient_ids = [f"GPR-{i:04d}" for i in range(1, n + 1)]

    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="D")
    dates = rng.permutation(dates)

    triage = rng.choice(
        list(TRIAGE_BENCHMARK.keys()),
        size=n,
        p=list(TRIAGE_BENCHMARK.values()),
    )

    transport_modes = rng.choice(
        ["Bus", "Two-wheeler", "Auto-rickshaw", "Car"],
        size=n,
        p=[0.50, 0.30, 0.15, 0.05],
    )

    accompanying = rng.choice([0, 1, 2], size=n, p=[0.6, 0.3, 0.1])

    dist_vc = rng.uniform(10, 80, size=n).round(1)
    dist_alt = rng.uniform(50, 200, size=n).round(1)

    df = pd.DataFrame(
        {
            "patient_id": patient_ids,
            "consultation_date": pd.to_datetime(dates).date,
            "triage_outcome": triage,
            "transport_mode": transport_modes,
            "accompanying_persons": accompanying,
            "distance_to_vc_km": dist_vc,
            "distance_to_alternative_km": dist_alt,
        }
    )

    # Sprinkle in missing values to exercise the default-filling logic
    missing_idx = rng.choice(n, size=max(1, n // 10), replace=False)
    for i in missing_idx:
        col = rng.choice(NEW_PROPOSED_COLUMNS)
        df.loc[i, col] = np.nan

    return df


# ---------------------------------------------------------------------------
# VALIDATION + DEFAULT FILLING
# ---------------------------------------------------------------------------

def validate_and_fill_defaults(df: pd.DataFrame):
    """
    Ensures expected columns exist (adding them with defaults if the whole
    column is missing) and fills any missing per-row values with the
    locked default assumptions.

    Returns (clean_df, missing_columns, rows_defaulted_count)
    """
    df = df.copy()
    missing_columns = [c for c in EXPECTED_COLUMNS if c not in df.columns]

    for col in missing_columns:
        df[col] = np.nan

    rows_defaulted = 0
    for col, default_val in DEFAULTS.items():
        na_mask = df[col].isna()
        if na_mask.any():
            rows_defaulted += int(na_mask.sum())
            df.loc[na_mask, col] = default_val

    # Type cleanup
    df["accompanying_persons"] = df["accompanying_persons"].astype(float)
    df["distance_to_vc_km"] = df["distance_to_vc_km"].astype(float)
    df["distance_to_alternative_km"] = df["distance_to_alternative_km"].astype(float)

    # Guard against unrecognised transport modes -> fall back to Bus
    unknown_mode_mask = ~df["transport_mode"].isin(TRANSPORT_EF.keys())
    if unknown_mode_mask.any():
        rows_defaulted += int(unknown_mode_mask.sum())
        df.loc[unknown_mode_mask, "transport_mode"] = DEFAULTS["transport_mode"]

    return df, missing_columns, rows_defaulted


# ---------------------------------------------------------------------------
# PER-PATIENT CALCULATION
# ---------------------------------------------------------------------------

def compute_per_patient(df: pd.DataFrame) -> pd.DataFrame:
    """Adds E_counterfactual, E_teleconsultation, CO2_saved_kg, trees_equivalent, etc."""
    df = df.copy()

    modal_ef = df["transport_mode"].map(TRANSPORT_EF)

    df["E_counterfactual_kg"] = (
        df["distance_to_alternative_km"] * 2 * modal_ef * (1 + df["accompanying_persons"])
    )
    df["E_travel_to_vc_kg"] = (
        df["distance_to_vc_km"] * 2 * modal_ef * (1 + df["accompanying_persons"])
    )
    df["E_device_kg"] = E_DEVICE_KGCO2
    df["E_digital_kg"] = E_DIGITAL_KGCO2
    df["E_teleconsultation_kg"] = (
        df["E_travel_to_vc_kg"] + df["E_device_kg"] + df["E_digital_kg"]
    )
    df["CO2_saved_kg"] = df["E_counterfactual_kg"] - df["E_teleconsultation_kg"]
    df["trees_equivalent"] = df["CO2_saved_kg"] / TREE_ABSORPTION_KGCO2_PER_YEAR
    df["is_negative"] = df["CO2_saved_kg"] < 0

    return df


def compute_single_patient(transport_mode, accompanying_persons, distance_to_vc_km, distance_to_alternative_km):
    """
    Same math as compute_per_patient, but for a single ad-hoc scenario rather
    than a dataframe of rows. Used by the Combined Patient Journey page.
    """
    modal_ef = TRANSPORT_EF.get(transport_mode, TRANSPORT_EF[DEFAULTS["transport_mode"]])

    e_counterfactual = distance_to_alternative_km * 2 * modal_ef * (1 + accompanying_persons)
    e_travel_to_vc = distance_to_vc_km * 2 * modal_ef * (1 + accompanying_persons)
    e_teleconsultation = e_travel_to_vc + E_DEVICE_KGCO2 + E_DIGITAL_KGCO2
    co2_saved = e_counterfactual - e_teleconsultation

    return {
        "E_counterfactual_kg": e_counterfactual,
        "E_travel_to_vc_kg": e_travel_to_vc,
        "E_teleconsultation_kg": e_teleconsultation,
        "CO2_saved_kg": co2_saved,
    }


# ---------------------------------------------------------------------------
# AGGREGATES
# ---------------------------------------------------------------------------

def compute_aggregates(df: pd.DataFrame) -> dict:
    total_co2_kg = df["CO2_saved_kg"].sum()

    by_triage = (
        df.groupby("triage_outcome")
        .agg(consultations=("patient_id", "count"), co2_saved_kg=("CO2_saved_kg", "sum"))
        .reindex(["Green", "Yellow", "Red"])
        .fillna(0)
        .reset_index()
    )

    return {
        "total_consultations": len(df),
        "total_co2_saved_kg": total_co2_kg,
        "total_co2_saved_tonnes": total_co2_kg / 1000,
        "trees_equivalent": total_co2_kg / TREE_ABSORPTION_KGCO2_PER_YEAR,
        "car_km_equivalent": total_co2_kg / CAR_KM_EQUIV_KGCO2_PER_KM,
        "flights_avoided": total_co2_kg / FLIGHT_EQUIV_KGCO2,
        "avg_co2_saved_per_consultation_kg": df["CO2_saved_kg"].mean(),
        "negative_count": int(df["is_negative"].sum()),
        "by_triage": by_triage,
    }
