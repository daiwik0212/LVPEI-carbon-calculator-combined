    """
Ophthalmology (facility-based) carbon calculation engine.
Pure functions only — no Streamlit calls — so this can be imported by both
the Ophthalmology Calculator page and the Combined Patient Journey page.

Ported from Shlok Marda's React calculator.
"""

EF = {
    "grid": 0.7117,       # CEA v21.0 All-India Unified Grid FY2024-25
    "diesel": 2.68,        # IPCC 2006
    "pp": 3.4, "pe": 2.0, "pvc": 3.1, "nitrile": 4.2, "cotton": 5.0,
    "steel": 2.9, "glass": 0.8, "paper": 0.9,
    "waste_yellow": 0.679, "waste_red": 0.467, "waste_green": -0.1,
}

LVPEI = {
    "slitlamp_w": 30, "slitlamp_min": 5,
    "autoref_w": 50, "autoref_min": 3,
    "nct_w": 75, "nct_min": 1,
    "oct_w": 180, "oct_min": 5,
    "clarus_w": 250, "clarus_min": 5,
    "bscan_w": 40, "bscan_min": 5,
    "perimeter_w": 150, "perimeter_min": 8,   # Humphrey-type visual field analyzer, ~4 min/eye
    "centurion_w": 400,
    "lumera_w": 250,
    "ot_light_w": 350,
    "chair_w": 50,
    "anaesth_standby_w": 20,
    "ot_count": 14,
}

# Default parameter values (used when the person hasn't adjusted anything)
DEFAULT_PARAMS = {
    "phaco_min": 15.0,
    "phaco_cases_day": 40.0,
    "surg_cases_day": 60.0,
    "ot_hours": 8.0,
    "glove_pairs": 4.0,
    "cssd_kwh_day": 128.0,
    "ivi_visits_yr": 8.0,
    "glaucoma_visits_yr": 3.0,          # typical monitoring frequency (IOP not surgically controlled)
}

# Pharmaceutical emissions (Scope 3, EIO-LCA proxy) — fixed kgCO2e assumptions.
# No cost/currency inputs anywhere in this app; these are locked figures derived
# once from an economic input-output LCA proxy and then hardcoded as emissions,
# same as every other "locked assumption" in this file (grid EF, material EFs, etc).
PHARMA_KGCO2 = {
    "phaco": 2.5749,          # per cataract surgery case
    "ivi": 15.4491,           # per anti-VEGF injection visit
    "glaucoma_yr": 6.1796,    # per year of topical IOP-lowering medication
}


def kwh(w, minutes):
    return (w * minutes) / 60000


def co2(w, minutes):
    return kwh(w, minutes) * EF["grid"]


def compute_opd():
    slit = co2(LVPEI["slitlamp_w"], LVPEI["slitlamp_min"])
    auto = co2(LVPEI["autoref_w"], LVPEI["autoref_min"])
    nct = co2(LVPEI["nct_w"], LVPEI["nct_min"])
    return {"slit": slit, "auto": auto, "nct": nct, "total": slit + auto + nct}


def compute_diag():
    oct_ = co2(LVPEI["oct_w"], LVPEI["oct_min"])
    clarus = co2(LVPEI["clarus_w"], LVPEI["clarus_min"])
    bscan = co2(LVPEI["bscan_w"], LVPEI["bscan_min"])
    return {"oct": oct_, "clarus": clarus, "bscan": bscan}


def compute_glaucoma_diag():
    perimetry = co2(LVPEI["perimeter_w"], LVPEI["perimeter_min"])
    return {"perimetry": perimetry}


def compute_surgery(phaco_min, phaco_cases_day, ot_hours):
    cases_per_ot = phaco_cases_day / LVPEI["ot_count"] if LVPEI["ot_count"] else 0
    total_light_kwh = (LVPEI["ot_light_w"] * ot_hours) / 1000
    ot_light_per_case = ((total_light_kwh / cases_per_ot) if cases_per_ot > 0 else 0) * EF["grid"]

    centurion = co2(LVPEI["centurion_w"], phaco_min)
    lumera = co2(LVPEI["lumera_w"], phaco_min)
    chair = co2(LVPEI["chair_w"], phaco_min)
    anaesth = co2(LVPEI["anaesth_standby_w"], phaco_min)
    total = centurion + lumera + chair + anaesth + ot_light_per_case
    return {
        "centurion": centurion, "lumera": lumera, "chair": chair,
        "anaesth": anaesth, "lighting": ot_light_per_case, "total": total,
    }


def compute_cssd(cssd_kwh_day, surg_cases_day):
    return (cssd_kwh_day / surg_cases_day) * EF["grid"] if surg_cases_day > 0 else 0


def compute_consumables(glove_pairs):
    items = [
        {"name": "Eye drapes (PE) × 2", "mass": 0.110, "ef": EF["pe"]},
        {"name": "Surgical gloves (nitrile)", "mass": 0.025 * glove_pairs, "ef": EF["nitrile"]},
        {"name": "Phaco cassette + tubing (PVC)", "mass": 0.120, "ef": EF["pvc"]},
        {"name": "BSS bottle (glass, single-use)", "mass": 0.500, "ef": EF["glass"]},
        {"name": "Syringes × 5 (PP)", "mass": 0.063, "ef": EF["pp"]},
        {"name": "Needles × 8 (steel)", "mass": 0.024, "ef": EF["steel"]},
        {"name": "IOL + packaging (PP + paper)", "mass": 0.035, "ef": EF["pp"]},
        {"name": "Viscoelastic cartridge (PP)", "mass": 0.015, "ef": EF["pp"]},
        {"name": "Cotton swabs × 2", "mass": 0.010, "ef": EF["cotton"]},
        {"name": "Mask + cap + booties (PP)", "mass": 0.014, "ef": EF["pp"]},
    ]
    for i in items:
        i["co2"] = i["mass"] * i["ef"]
    return {"items": items, "total": sum(i["co2"] for i in items)}


def compute_ivi_consumables():
    items = [
        {"name": "Anti-VEGF vial (glass)", "mass": 0.008, "ef": EF["glass"]},
        {"name": "1 mL syringe (PP)", "mass": 0.008, "ef": EF["pp"]},
        {"name": "30G needle (steel)", "mass": 0.003, "ef": EF["steel"]},
        {"name": "Sterile drape (PE)", "mass": 0.055, "ef": EF["pe"]},
        {"name": "Sterile gloves (nitrile)", "mass": 0.025, "ef": EF["nitrile"]},
        {"name": "Cotton swabs × 3", "mass": 0.015, "ef": EF["cotton"]},
        {"name": "Povidone-iodine", "mass": 0.005, "ef": EF["pp"]},
    ]
    for i in items:
        i["co2"] = i["mass"] * i["ef"]
    return {"items": items, "total": sum(i["co2"] for i in items)}


def compute_pharma():
    return {
        "phaco": PHARMA_KGCO2["phaco"],
        "ivi": PHARMA_KGCO2["ivi"],
        "glaucoma": PHARMA_KGCO2["glaucoma_yr"],
    }


def compute_waste():
    yellow = 0.170 * EF["waste_yellow"]
    red = 0.230 * EF["waste_red"]
    green = 0.130 * EF["waste_green"]
    sharps = 0.024 * EF["waste_red"]
    return {"yellow": yellow, "red": red, "green": green, "sharps": sharps,
            "total": yellow + red + green + sharps}


def compute_all(params: dict = None):
    """
    Runs the full ophthalmology calculation given a dict of adjustable
    parameters (falls back to DEFAULT_PARAMS for anything not supplied).
    Returns every intermediate figure plus the headline totals used
    throughout the app: phaco_grand, cataract_episode, dr_episode_year.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    opd = compute_opd()
    diag = compute_diag()
    glaucoma_diag = compute_glaucoma_diag()
    surgery = compute_surgery(p["phaco_min"], p["phaco_cases_day"], p["ot_hours"])
    cssd_per_case = compute_cssd(p["cssd_kwh_day"], p["surg_cases_day"])
    consumables = compute_consumables(p["glove_pairs"])
    ivi_consumables = compute_ivi_consumables()
    pharma = compute_pharma()
    waste = compute_waste()

    phaco_grand = (
        opd["total"] + diag["oct"] + surgery["total"] + cssd_per_case
        + consumables["total"] + pharma["phaco"] + waste["total"]
    )

    cataract_episode = (
        (opd["total"] * 4) + diag["oct"] + surgery["total"] + cssd_per_case
        + consumables["total"] + pharma["phaco"] + waste["total"]
    )

    waste_per_ivi = 0.120 * EF["waste_yellow"] + 0.080 * EF["waste_red"]
    per_ivi_visit = opd["total"] + diag["oct"] + ivi_consumables["total"] + pharma["ivi"] + waste_per_ivi
    dr_episode_year = (per_ivi_visit * p["ivi_visits_yr"]) + diag["clarus"]

    # A normal eye checkup: OPD encounter only (slit lamp + autorefractor + NCT).
    # No OCT, no surgery, no consumables/CSSD/pharma/waste — just the screening visit.
    opd_only_episode = opd["total"]

    # Glaucoma is monitored, not "cured" in one episode — chronic follow-up visits
    # (OPD + IOP check via NCT + visual field test) plus ongoing topical medication.
    # No surgical consumables/CSSD; waste is minimal (cotton, disposable wipes).
    waste_per_glaucoma_visit = 0.015 * EF["waste_yellow"]
    per_glaucoma_visit = opd["total"] + glaucoma_diag["perimetry"] + waste_per_glaucoma_visit
    glaucoma_episode_year = (per_glaucoma_visit * p["glaucoma_visits_yr"]) + diag["oct"] + pharma["glaucoma"]

    return {
        "params": p,
        "opd": opd,
        "diag": diag,
        "glaucoma_diag": glaucoma_diag,
        "surgery": surgery,
        "cssd_per_case": cssd_per_case,
        "consumables": consumables,
        "ivi_consumables": ivi_consumables,
        "pharma": pharma,
        "waste": waste,
        "phaco_grand": phaco_grand,
        "cataract_episode": cataract_episode,
        "dr_episode_year": dr_episode_year,
        "per_ivi_visit": per_ivi_visit,
        "opd_only_episode": opd_only_episode,
        "per_glaucoma_visit": per_glaucoma_visit,
        "glaucoma_episode_year": glaucoma_episode_year,
    }