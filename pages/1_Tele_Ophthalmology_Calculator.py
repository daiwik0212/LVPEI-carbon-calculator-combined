# ============================================================
# carbon_calc.py — LVPEI GPR Tele-ophthalmology Carbon Calculator
# Author: Daiwik Singh (2024B1A41063H), BITS Pilani Hyderabad
# PS-I 2025-26, LVPEI GPR Vision Centre, Kismathpur
# ============================================================
"""
Core constants, emission factors, and demo-data generator for the
Tele-ophthalmology Carbon Calculator.

Realistic demo data (generate_dummy_data):
  • Triage split fixed at 84% Green / 8% Yellow / 8% Red (Rani et al. 2024).
  • Villages drawn from the actual GPR VC catchment (Rajendranagar &
    Chevella mandals, Ranga Reddy district, Telangana).
  • Transport modal share weighted for rural Telangana.
  • Distance to VC drawn from village lookup + small jitter.
  • Counterfactual distance depends on triage:
        Green  -> LVPEI Secondary (KAR, Banjara Hills)   ~22-32 km
        Yellow -> Secondary / low-tertiary               ~28-45 km
        Red    -> Tertiary Centre (KAR / KVC)            ~35-120 km
  • Accompanying persons biased upward for Yellow/Red patients.
  • Consultation dates spread across the last 60 days.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

# ============================================================
# 1. EMISSION FACTORS & CONSTANTS
# ============================================================

# Transport modal emission factors (kgCO2 per passenger-km)
# Source: Rani et al. 2024 (Eye/Nature) — India-specific values
TRANSPORT_EF = {
    "Walking":     0.000,
    "Bicycle":     0.000,
    "Motorcycle":  0.061,
    "Auto":        0.107,
    "Bus":         0.089,
    "Car":         0.171,
    "Train":       0.041,
    "Shared Taxi": 0.130,
}

# Grid emission factor — CEA CO2 Baseline Database v21.0, FY 2024-25
GRID_EF_KGCO2_PER_KWH = 0.7117

# Relatable-equivalent constants
TREE_ABSORPTION_KGCO2_PER_YEAR = 21.0      # kgCO2 absorbed per tree per year
CAR_KM_EQUIV_KGCO2_PER_KM      = 0.171     # kgCO2/km for a passenger car
FLIGHT_EQUIV_KGCO2             = 130.0     # kgCO2 per passenger, DEL-HYD one-way

# Triage benchmark distribution (Rani et al. 2024)
TRIAGE_BENCHMARK = {"Green": 0.84, "Yellow": 0.08, "Red": 0.08}

# Expected schema for eyeSmart-style uploads
EXPECTED_COLUMNS = [
    "patient_id",
    "consultation_date",
    "triage_outcome",
    "transport_mode",
    "accompanying_persons",
    "distance_to_vc_km",
    "distance_to_alternative_km",
]

# Fallback defaults when a column is missing / a row is incomplete
DEFAULTS = {
    "triage_outcome":             "Green",
    "transport_mode":             "Bus",
    "accompanying_persons":       1,
    "distance_to_vc_km":          15.0,
    "distance_to_alternative_km": 80.0,
}

# ============================================================
# 2. GPR CATCHMENT VILLAGE LOOKUP
# ============================================================
# (village_name, distance_to_GPR_VC_km) — approximated via Google Maps
# Covers Rajendranagar + Chevella mandals, Ranga Reddy district.
GPR_CATCHMENT_VILLAGES = [
    ("Kismathpur",        1.2), ("Bandlaguda",         3.5),
    ("Attapur",           4.8), ("Rajendranagar",      5.5),
    ("Katedan",           6.2), ("Mailardevpally",     7.1),
    ("Shastripuram",      7.8), ("Suleman Nagar",      8.6),
    ("Hyderguda",         9.4), ("Budvel",            10.3),
    ("Upparpally",       11.5), ("Balapur",           12.7),
    ("Pahadi Shareef",   13.9), ("Aramgarh",          14.5),
    ("Barkas",           15.2), ("Chandrayangutta",   16.4),
    ("Shamshabad",       17.8), ("Kothur",            19.2),
    ("Maheshwaram",      20.5), ("Ibrahimpatnam",     21.8),
    ("Chevella",         23.1), ("Manchal",           24.6),
    ("Yacharam",         25.9), ("Kandukur",          18.7),
    ("Moinabad",         16.9), ("Shabad",            22.4),
    ("Farooqnagar",      24.0), ("Nagarkurnool Rd",   12.1),
    ("Injapur",           9.8), ("Adibatla",          15.6),
]

# ============================================================
# 3. REALISTIC DEMO-DATA GENERATOR
# ============================================================

def generate_dummy_data(n_patients: int = 50, seed: int = 42) -> pd.DataFrame:
    """
    Generate a realistic 50-patient demo dataset for GPR Vision Centre.

    Respects Rani et al. 2024's 84/8/8 triage distribution and uses
    catchment-specific villages, transport mixes, and referral distances.
    """
    rng = np.random.default_rng(seed)

    # ---- Triage: exact 84/8/8 for n=50 -> 42 Green, 4 Yellow, 4 Red ----
    n_green  = int(round(TRIAGE_BENCHMARK["Green"]  * n_patients))
    n_yellow = int(round(TRIAGE_BENCHMARK["Yellow"] * n_patients))
    n_red    = n_patients - n_green - n_yellow            # absorbs rounding
    triage = np.array(["Green"] * n_green
                      + ["Yellow"] * n_yellow
                      + ["Red"] * n_red)
    rng.shuffle(triage)

    # ---- Village of origin (weight nearer villages higher) ------------
    village_names = np.array([v[0] for v in GPR_CATCHMENT_VILLAGES])
    village_dists = np.array([v[1] for v in GPR_CATCHMENT_VILLAGES])
    weights = 1.0 / (village_dists + 2.0)
    weights = weights / weights.sum()
    idx = rng.choice(len(GPR_CATCHMENT_VILLAGES), size=n_patients, p=weights)
    village_of_origin = village_names[idx]
    distance_to_vc_km = village_dists[idx] + rng.normal(0, 0.6, n_patients)
    distance_to_vc_km = np.clip(distance_to_vc_km, 0.5, None).round(1)

    # ---- Counterfactual distance depends on triage --------------------
    dist_alt = np.zeros(n_patients)
    for i, t in enumerate(triage):
        if t == "Green":
            # LVPEI Secondary (KAR, Banjara Hills)
            dist_alt[i] = rng.normal(loc=26, scale=3.0)
        elif t == "Yellow":
            # Secondary / low-tertiary Hub
            dist_alt[i] = rng.normal(loc=34, scale=4.5)
        else:  # Red
            # Tertiary Centre (KAR / KVC) — long-tail referral
            dist_alt[i] = rng.normal(loc=65, scale=25.0)
    # Ensure alternative distance never shorter than distance to VC + 5 km
    dist_alt = np.maximum(dist_alt, distance_to_vc_km + 5)
    dist_alt = np.clip(dist_alt, 8.0, 150.0).round(1)

    # ---- Transport mode (rural Telangana weighting) -------------------
    transport_choices = list(TRANSPORT_EF.keys())
    # Base weights: Motorcycle & Bus dominate, then Auto, then Walking,
    # occasional Shared Taxi/Car, rare Train, rare Bicycle.
    base_weights = {
        "Walking":     0.10,
        "Bicycle":     0.03,
        "Motorcycle":  0.34,
        "Auto":        0.18,
        "Bus":         0.22,
        "Car":         0.06,
        "Train":       0.01,
        "Shared Taxi": 0.06,
    }
    transport_mode = []
    for i in range(n_patients):
        w = base_weights.copy()
        d = distance_to_vc_km[i]
        # Walking only realistic for <3 km; push weight away otherwise
        if d > 3:
            w["Walking"] = 0.01
        if d > 10:
            w["Bicycle"] = 0.005
        # For long referral trips (Red), bus/car/train become more likely
        if triage[i] == "Red":
            w["Bus"]        *= 1.4
            w["Car"]        *= 2.0
            w["Train"]      *= 3.0
            w["Motorcycle"] *= 0.6
        vals = np.array([w[m] for m in transport_choices])
        vals = vals / vals.sum()
        transport_mode.append(rng.choice(transport_choices, p=vals))
    transport_mode = np.array(transport_mode)

    # ---- Accompanying persons -----------------------------------------
    # Green: mostly 0-1, Yellow: 1-2, Red: 1-3 (elderly / referral cases)
    accompanying = np.zeros(n_patients, dtype=int)
    for i, t in enumerate(triage):
        if t == "Green":
            accompanying[i] = rng.choice([0, 1, 2], p=[0.55, 0.35, 0.10])
        elif t == "Yellow":
            accompanying[i] = rng.choice([0, 1, 2, 3], p=[0.10, 0.50, 0.30, 0.10])
        else:  # Red
            accompanying[i] = rng.choice([1, 2, 3], p=[0.35, 0.45, 0.20])

    # ---- Consultation dates (last 60 days) ----------------------------
    today = date.today()
    days_back = rng.integers(0, 60, size=n_patients)
    consultation_date = [
        (today - timedelta(days=int(d))).isoformat() for d in days_back
    ]

    # ---- Patient IDs ---------------------------------------------------
    patient_ids = [f"GPR-2026-{1000 + i:04d}" for i in range(n_patients)]

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

    # Sort by date so the table looks natural
    df = df.sort_values("consultation_date").reset_index(drop=True)
    return df


# ============================================================
# 4. VALIDATION & DEFAULT-FILLING FOR UPLOADED CSVs
# ============================================================

def validate_and_fill_defaults(df: pd.DataFrame):
    """
    Ensure every EXPECTED_COLUMN exists; fill missing columns with DEFAULTS,
    and fill NaN cells in existing columns with the same defaults.

    Returns:
        clean_df       : the corrected DataFrame
        missing_cols   : list of columns that had to be added
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

    # Fill any missing schema columns with defaults
    for col in EXPECTED_COLUMNS:
        if col not in clean_df.columns:
            clean_df[col] = DEFAULTS.get(col, np.nan)
            missing_cols.append(col)

    # Track which rows needed a fallback value
    before = clean_df[EXPECTED_COLUMNS].isna().any(axis=1)
    for col, val in DEFAULTS.items():
        if col in clean_df.columns:
            clean_df[col] = clean_df[col].fillna(val)
    rows_defaulted = int(before.sum())

    # Normalise triage_outcome capitalisation (Green/Yellow/Red)
    clean_df["triage_outcome"] = (
        clean_df["triage_outcome"].astype(str).str.strip().str.title()
    )
    clean_df.loc[
        ~clean_df["triage_outcome"].isin(["Green", "Yellow", "Red"]),
        "triage_outcome"
    ] = DEFAULTS["triage_outcome"]

    # Coerce numeric columns
    for c in ["distance_to_vc_km", "distance_to_alternative_km",
              "accompanying_persons"]:
        clean_df[c] = pd.to_numeric(clean_df[c], errors="coerce").fillna(
            DEFAULTS[c]
        )

    return clean_df, missing_cols, rows_defaulted


# ============================================================
# 5. QUICK SELF-TEST (run: python carbon_calc.py)
# ============================================================
if __name__ == "__main__":
    demo = generate_dummy_data()
    print(f"Generated {len(demo)} patients.")
    print(demo["triage_outcome"].value_counts(normalize=True).round(3))
    print(demo["transport_mode"].value_counts())
    print(demo.head())