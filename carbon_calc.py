"""
Tele-ophthalmology Carbon Footprint Calculator
Core calculation engine + dummy data generator.

Master equation:
    delta_E = E_counterfactual - E_teleconsultation
    E_counterfactual   = d_alt x 2 x modal_EF x (1 + accompanying_persons)
    E_travel_to_VC     = d_vc  x 2 x modal_EF x (1 + accompanying_persons)
    E_teleconsultation = E_travel_to_VC + E_device + E_digital

All emission factors and constants below are LOCKED assumptions from the
project brief (Rani et al. 2024, Kwon/Thiel 2024 JMIR, CEA v21.0).
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

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
# GPR VISION CENTRE CATCHMENT LOOKUP
# ---------------------------------------------------------------------------
# (village_name, approx_distance_to_GPR_VC_km)
# Rajendranagar + Chevella mandals, Ranga Reddy district, Telangana.
# Distances estimated via Google Maps from GPR VC, Kismathpur.
GPR_CATCHMENT_VILLAGES = [
    ("Kismathpur",       1.2), ("Bandlaguda",        3.5),
    ("Attapur",          4.8), ("Rajendranagar",     5.5),
    ("Katedan",          6.2), ("Mailardevpally",    7.1),
    ("Shastripuram",     7.8), ("Suleman Nagar",     8.6),
    ("Hyderguda",        9.4), ("Budvel",           10.3),
    ("Upparpally",      11.5), ("Balapur",          12.7),
    ("Pahadi Shareef",  13.9), ("Aramgarh",         14.5),
    ("Barkas",          15.2), ("Chandrayangutta",  16.4),
    ("Shamshabad",      17.8), ("Kothur",           19.2),
    ("Maheshwaram",     20.5), ("Ibrahimpatnam",    21.8),
    ("Chevella",        23.1), ("Manchal",          24.6),
    ("Yacharam",        25.9), ("Kandukur",         18.7),
    ("Moinabad",        16.9), ("Shabad",           22.4),
    ("Farooqnagar",     24.0), ("Nagarkurnool Rd",  12.1),
    ("Injapur",          9.8), ("Adibatla",         15.6),
]

# ---------------------------------------------------------------------------
# DUMMY DATA GENERATOR  (realistic, respects 84/8/8 triage)
# ---------------------------------------------------------------------------

def generate_dummy_data(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Generate a realistic dummy eyeSmart-style CSV export for GPR Vision Centre.

    Realism controls:
      • Triage split exactly 84% Green / 8% Yellow / 8% Red (Rani et al. 2024).
      • Villages drawn from the actual GPR catchment lookup.
      • Distance to VC follows the village-lookup distances (with small jitter).
      • Counterfactual distance depends on triage:
            Green  -> LVPEI Secondary (KAR, Banjara Hills)  ~22-32 km
            Yellow -> Secondary / low-tertiary Hub          ~28-45 km
            Red    -> Tertiary Centre (KAR / KVC)           ~35-120 km
      • Transport mode weighted for rural Telangana (Two-wheeler + Bus
        dominant); Walk/cycle only for very short trips; Red patients
        biased toward Bus/Car/Train for long referral journeys.
      • Accompanying persons biased upward for Yellow/Red patients.
      • Consultation dates spread across the last 60 days.
    """
    rng = np.random.default_rng(seed)

    # ---- Triage: exact 84/8/8 for n=50 -> 42 Green, 4 Yellow, 4 Red ----
    n_green  = int(round(TRIAGE_BENCHMARK["Green"]  * n))
    n_yellow = int(round(TRIAGE_BENCHMARK["Yellow"] * n))
    n_red    = n - n_green - n_yellow            # absorbs any rounding gap
    triage = np.array(["Green"] * n_green
                      + ["Yellow"] * n_yellow
                      + ["Red"] * n_red)
    rng.shuffle(triage)

    # ---- Village of origin (weight nearer villages higher) ------------
    village_names = np.array([v[0] for v in GPR_CATCHMENT_VILLAGES])
    village_dists = np.array([v[1] for v in GPR_CATCHMENT_VILLAGES])
    weights = 1.0 / (village_dists + 2.0)
    weights = weights / weights.sum()
    idx = rng.choice(len(GPR_CATCHMENT_VILLAGES), size=n, p=weights)
    village_of_origin = village_names[idx]
    distance_to_vc_km = village_dists[idx] + rng.normal(0, 0.6, n)
    distance_to_vc_km = np.clip(distance_to_vc_km, 0.5, None).round(1)

    # ---- Counterfactual distance depends on triage --------------------
    dist_alt = np.zeros(n)
    for i, t in enumerate(triage):
        if t == "Green":
            dist_alt[i] = rng.normal(loc=26, scale=3.0)
        elif t == "Yellow":
            dist_alt[i] = rng.normal(loc=34, scale=4.5)
        else:  # Red — long-tail referral distances
            dist_alt[i] = rng.normal(loc=65, scale=25.0)
    # Ensure alternative distance is always at least 5 km longer than VC
    dist_alt = np.maximum(dist_alt, distance_to_vc_km + 5)
    dist_alt = np.clip(dist_alt, 8.0, 150.0).round(1)

    # ---- Transport mode (rural Telangana weighting) -------------------
    transport_choices = list(TRANSPORT_EF.keys())
    base_weights = {
        "Two-wheeler":   0.36,
        "Car":           0.06,
        "Bus":           0.28,
        "Auto-rickshaw": 0.18,
        "Train":         0.01,
        "Air":           0.00,
        "Walk/cycle":    0.11,
    }
    transport_mode = []
    for i in range(n):
        w = base_weights.copy()
        d = distance_to_vc_km[i]
        # Walk/cycle realistic only for very short trips
        if d > 3:
            w["Walk/cycle"] = 0.01
        if d > 8:
            w["Walk/cycle"] = 0.0
        # For long referral trips (Red), Bus / Car / Train become likelier
        if triage[i] == "Red":
            w["Bus"]         *= 1.4
            w["Car"]         *= 2.0
            w["Train"]       *= 3.0
            w["Two-wheeler"] *= 0.6
            w["Walk/cycle"]  = 0.0
        vals = np.array([w[m] for m in transport_choices])
        vals = vals / vals.sum()
        transport_mode.append(rng.choice(transport_choices, p=vals))
    transport_mode = np.array(transport_mode)

    # ---- Accompanying persons -----------------------------------------
    accompanying = np.zeros(n, dtype=int)
    for i, t in enumerate(triage):
        if t == "Green":
            accompanying[i] = rng.choice([0, 1, 2], p=[0.55, 0.35, 0.10])
        elif t == "Yellow":
            accompanying[i] = rng.choice([0, 1, 2, 3], p=[0.10, 0.50, 0.30, 0.10])
        else:  # Red
            accompanying[i] = rng.choice([1, 2, 3], p=[0.35, 0.45, 0.20])

    # ---- Consultation dates (last 60 days) ----------------------------
    today = date.today()
    days_back = rng.integers(0, 60, size=n)
    consultation_date = [
        (today - timedelta(days=int(d))).isoformat() for d in days_back
    ]

    # ---- Patient IDs ---------------------------------------------------
    patient_ids = [f"GPR-2026-{1000 + i:04d}" for i in range(n)]

    # ---- Assemble DataFrame -------------------------------------------
    df = pd.DataFrame({
        "patient_id":                 patient_ids,
        "consultation_date":          consultation_date,
        "village_of_origin":          village_of_origin,
        "triage_outcome":             triage,
        "transport_mode":             transport_mode,
        "accompanying_persons":       accompanying,
        "distance_to_vc_km":          distance_to_vc_km,
        "distance_to_alternative_km": dist_alt,
    })

    # Sort by date so the demo table reads naturally
    df = df.sort_values("consultation_date").reset_index(drop=True)
    return df

# ---------------------------------------------------------------------------
# VALIDATION + DEFAULT FILLING
# ---------------------------------------------------------------------------

def validate_and_fill_defaults(df: pd.DataFrame):
    """
    Ensures expected columns exist (adding them with defaults if the whole
    column is missing) and fills any missing per-row values with the
    locked default assumptions.

    Returns:
        clean_df       : the corrected DataFrame
        missing_cols   : list of columns that had to be created
        rows_defaulted : number of rows that received at least one fallback
    """
    clean_df = df.copy()
    missing_cols = []

    # Auto-generate identifiers/dates if missing
    if "patient_id" not in clean_df.columns:
        clean_df["patient_id"] = [f"UP-{i:04d}" for i in range(len(clean_df))]
        missing_cols.append("patient_id")
    if "consultation_date" not in clean_df.columns:
        clean_df["consultation_date"] = date.today().isoformat()
        missing_cols.append("consultation_date")
    if "triage_outcome" not in clean_df.columns:
        clean_df["triage_outcome"] = "Green"
        missing_cols.append("triage_outcome")

    # Fill any missing schema columns with defaults
    for col in NEW_PROPOSED_COLUMNS:
        if col not in clean_df.columns:
            clean_df[col] = DEFAULTS.get(col, np.nan)
            missing_cols.append(col)

    # Track which rows will need at least one fallback
    before = clean_df[EXPECTED_COLUMNS].isna().any(axis=1)
    for col, val in DEFAULTS.items():
        if col in clean_df.columns:
            clean_df[col] = clean_df[col].fillna(val)
    rows_defaulted = int(before.sum())

    # Normalise triage capitalisation and reject unknown values
    clean_df["triage_outcome"] = (
        clean_df["triage_outcome"].astype(str).str.strip().str.title()
    )
    clean_df.loc[
        ~clean_df["triage_outcome"].isin(["Green", "Yellow", "Red"]),
        "triage_outcome"
    ] = "Green"

    # Coerce numerics
    for c in ["distance_to_vc_km", "distance_to_alternative_km",
              "accompanying_persons"]:
        clean_df[c] = pd.to_numeric(clean_df[c], errors="coerce").fillna(
            DEFAULTS[c]
        )
    clean_df["accompanying_persons"] = clean_df["accompanying_persons"].astype(int)

    return clean_df, missing_cols, rows_defaulted

# ---------------------------------------------------------------------------
# PER-PATIENT CALCULATION
# ---------------------------------------------------------------------------

def compute_per_patient(df: pd.DataFrame) -> pd.DataFrame:
    """Adds E_counterfactual, E_teleconsultation, CO2_saved_kg, trees_equivalent, etc."""
    df = df.copy()

    modal_ef = df["transport_mode"].map(TRANSPORT_EF).fillna(
        TRANSPORT_EF[DEFAULTS["transport_mode"]]
    )
    multiplier = 1 + df["accompanying_persons"].astype(float)

    df["E_counterfactual_kg"]    = df["distance_to_alternative_km"] * 2 * modal_ef * multiplier
    df["E_travel_to_vc_kg"]      = df["distance_to_vc_km"]          * 2 * modal_ef * multiplier
    df["E_device_kg"]            = E_DEVICE_KGCO2
    df["E_digital_kg"]           = E_DIGITAL_KGCO2
    df["E_teleconsultation_kg"]  = df["E_travel_to_vc_kg"] + E_DEVICE_KGCO2 + E_DIGITAL_KGCO2
    df["CO2_saved_kg"]           = df["E_counterfactual_kg"] - df["E_teleconsultation_kg"]
    df["trees_equivalent"]       = df["CO2_saved_kg"] / TREE_ABSORPTION_KGCO2_PER_YEAR
    df["is_negative"]            = df["CO2_saved_kg"] < 0
    return df


def compute_single_patient(transport_mode, accompanying_persons,
                           distance_to_vc_km, distance_to_alternative_km):
    """
    Same math as compute_per_patient, but for a single ad-hoc scenario rather
    than a dataframe of rows. Used by the Combined Patient Journey page.
    """
    modal_ef = TRANSPORT_EF.get(transport_mode, TRANSPORT_EF[DEFAULTS["transport_mode"]])
    multiplier = 1 + float(accompanying_persons)

    e_counterfactual   = distance_to_alternative_km * 2 * modal_ef * multiplier
    e_travel_to_vc     = distance_to_vc_km          * 2 * modal_ef * multiplier
    e_teleconsultation = e_travel_to_vc + E_DEVICE_KGCO2 + E_DIGITAL_KGCO2
    co2_saved          = e_counterfactual - e_teleconsultation

    return {
        "E_counterfactual_kg":    e_counterfactual,
        "E_travel_to_vc_kg":      e_travel_to_vc,
        "E_device_kg":            E_DEVICE_KGCO2,
        "E_digital_kg":           E_DIGITAL_KGCO2,
        "E_teleconsultation_kg":  e_teleconsultation,
        "CO2_saved_kg":           co2_saved,
        "trees_equivalent":       co2_saved / TREE_ABSORPTION_KGCO2_PER_YEAR,
        "is_negative":            co2_saved < 0,
    }

# ---------------------------------------------------------------------------
# AGGREGATES
# ---------------------------------------------------------------------------

def compute_aggregates(df: pd.DataFrame) -> dict:
    """Aggregate KPIs across all patients in the (already-computed) DataFrame."""
    total_co2_kg  = df["CO2_saved_kg"].sum()
    total_co2_t   = total_co2_kg / 1000
    total_trees   = total_co2_kg / TREE_ABSORPTION_KGCO2_PER_YEAR
    total_car_km  = total_co2_kg / CAR_KM_EQUIV_KGCO2_PER_KM
    total_flights = total_co2_kg / FLIGHT_EQUIV_KGCO2

    avg_co2 = df["CO2_saved_kg"].mean() if len(df) else 0.0
    negative_count = int(df["is_negative"].sum()) if "is_negative" in df.columns else 0
    total_consults = len(df)

    triage_summary = (
        df.groupby("triage_outcome")
          .agg(patients=("CO2_saved_kg", "count"),
               co2_saved_kg=("CO2_saved_kg", "sum"))
          .reindex(["Green", "Yellow", "Red"])
          .fillna(0)
          .reset_index()
    )

    return {
        "total_co2_kg":   total_co2_kg,
        "total_co2_t":    total_co2_t,
        "total_trees":    total_trees,
        "total_car_km":   total_car_km,
        "total_flights":  total_flights,
        "avg_co2":        avg_co2,
        "negative_count": negative_count,
        "total_consults": total_consults,
        "triage_summary": triage_summary,
    }


# ---------------------------------------------------------------------------
# QUICK SELF-TEST (run: python carbon_calc.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo = generate_dummy_data()
    clean, _, _ = validate_and_fill_defaults(demo)
    result = compute_per_patient(clean)
    agg = compute_aggregates(result)

    print(f"Generated {len(demo)} patients.")
    print("Triage share:")
    print(demo["triage_outcome"].value_counts(normalize=True).round(3))
    print("Transport mix:")
    print(demo["transport_mode"].value_counts())
    print(f"Total CO2 saved: {agg['total_co2_kg']:.1f} kg "
          f"({agg['total_co2_t']:.3f} tonnes)")
    print(f"Avg per patient: {agg['avg_co2']:.2f} kg")
    print(f"Trees equiv:     {agg['total_trees']:.0f}")
    print(f"Flights equiv:   {agg['total_flights']:.2f}")