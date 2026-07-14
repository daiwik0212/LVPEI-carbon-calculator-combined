"""
Ophthalmology (facility-based) carbon calculation engine.
Pure functions only — no Streamlit calls — so this can be imported by both
the Ophthalmology Calculator page and the Combined Patient Journey page.

Ported from Shlok Marda's React calculator (v2.0, 6-pathway edition):
Cataract, LASIK, Glaucoma, Vitreoretinal, DR/IVI, Custom.
"""

# ═══ EMISSION FACTORS (List A — CEA v21, IPCC, Ecoinvent) ═══
EF = {
    "grid": 0.7117,        # CEA v21.0 All-India Unified Grid FY2024-25
    "diesel": 2.68,         # IPCC 2006
    "pp": 3.4, "pe": 2.0, "pvc": 3.1, "nitrile": 4.2, "cotton": 5.0,
    "steel": 2.9, "glass": 0.8, "paper": 0.9, "silicone": 6.0, "pmma": 3.8,
    "waste_yellow": 0.679, "waste_red": 0.467, "waste_green": -0.1,
    "pharma_usd": 0.43,     # EIO-LCA proxy, kgCO2e per USD of pharma spend
    "n2o_gwp": 265, "sevo_gwp": 130,
}

# LVPEI equipment wattages / durations (facility interview)
DEV = {
    "slit": 30, "slit_min": 5, "auto": 50, "auto_min": 3, "nct": 75, "nct_min": 1,
    "oct": 180, "oct_min": 5, "clarus": 250, "clarus_min": 5, "bscan": 40, "bscan_min": 5,
    "centurion": 400, "lumera": 250, "ot_light": 350, "chair": 50,
    "anaesth_standby": 20, "anaesth_active": 250,
    "ot_count": 14,
}

# Fixed kgCO2e pharma assumptions (legacy method — locked EIO-LCA figures,
# same category as every other "locked assumption" in this file).
PHARMA_KGCO2 = {
    "phaco": 2.5749,          # per cataract surgery case
    "ivi_bevacizumab": 15.4491,   # per anti-VEGF injection visit (unsplit vial)
    "glaucoma_yr": 6.1796,     # per year of topical IOP-lowering medication
    "lasik": 1.2,              # per LASIK case (drops course)
    "vitreoretinal": 4.5,      # per VR case (drops + intra-op agents)
}

PATHWAYS = [
    {"id": "cataract", "label": "Cataract", "icon": "🔵"},
    {"id": "lasik", "label": "LASIK", "icon": "✨"},
    {"id": "glaucoma", "label": "Glaucoma", "icon": "🟢"},
    {"id": "vitreoretinal", "label": "Vitreoretinal", "icon": "🟣"},
    {"id": "dr_ivi", "label": "DR / IVI", "icon": "🟠"},
    {"id": "custom", "label": "Custom", "icon": "⚙️"},
]

# Default parameter values for every pathway (used when the person hasn't
# adjusted anything). Prefixed exactly as in the React version so it's easy
# to keep the two in sync.
DEFAULT_PARAMS = {
    "pharma_method": "fixed",   # "fixed" (locked kgCO2e) or "cost" (₹ / exchange rate × EF)
    "exchange_rate": 83.5,

    # Cataract
    "c_phaco_min": 15.0, "c_phaco_cases_day": 40.0, "c_surg_cases_day": 60.0,
    "c_ot_hours": 8.0, "c_glove_pairs": 4.0, "c_cssd_kwh_day": 128.0, "c_cssd_weight": 1.0,
    "c_eye_drapes": 2, "c_syringes": 5, "c_needles": 8,
    "c_bss_single_use": True, "c_drugs_single_use": True,
    "c_pharma_cost": 500.0, "c_total_visits": 5,
    "c_has_oct": True, "c_has_biometry": True,

    # LASIK
    "l_laser_min": 5.0, "l_excimer_w": 800.0, "l_femto": True, "l_femto_w": 500.0,
    "l_femto_min": 3.0, "l_glove_pairs": 2.0, "l_cases_day": 15.0,
    "l_pharma_cost": 800.0, "l_total_visits": 5, "l_eye_drapes": 1, "l_suction_rings": 1,
    "l_microscope_min": 8.0,

    # Glaucoma
    "g_is_surgical": False, "g_surg_min": 30.0, "g_glove_pairs": 3.0,
    "g_monitor_visits_yr": 4.0, "g_years_followup": 5.0,
    "g_has_oct": True, "g_has_perimetry": True, "g_perimeter_min": 15.0, "g_perimeter_w": 40.0,
    "g_drops_cost_month": 300.0, "g_laser_slt": False, "g_slt_min": 10.0, "g_slt_w": 200.0,
    "g_mitomycin": False, "g_cssd_weight": 1.2, "g_cssd_kwh_day": 128.0, "g_surg_cases_day": 60.0,

    # Vitreoretinal
    "v_surg_min": 60.0, "v_vr_cases_day": 8.0, "v_surg_cases_day": 60.0, "v_glove_pairs": 4.0,
    "v_use_ga": True, "v_ga_min": 90.0, "v_sevo_ml": 15.0,
    "v_has_tamponade": True, "v_tamponade_type": "gas",
    "v_has_endolaser": True, "v_endolaser_min": 10.0, "v_endolaser_w": 300.0,
    "v_pharma_cost": 2000.0, "v_total_visits": 8, "v_has_oct": True, "v_has_bscan": True,
    "v_cssd_weight": 1.5, "v_cssd_kwh_day": 128.0, "v_eye_drapes": 2, "v_syringes": 8, "v_needles": 10,

    # DR / IVI
    "d_drug": "bevacizumab", "d_drug_cost": 3000.0, "d_split_vial": False, "d_patients_per_vial": 1,
    "d_visits_yr": 8.0, "d_years_treatment": 2.0, "d_glove_pairs": 1.0,
    "d_has_oct": True, "d_has_ffa": True, "d_ffa_freq": 1, "d_ivi_min": 5.0,
    "d_pharma_cost_drops": 200.0,

    # Custom
    "x_opd_visits": 1, "x_has_oct": False, "x_has_ffa": False, "x_has_bscan": False,
    "x_has_surgery": False, "x_surg_min": 15.0, "x_surg_w": 400.0, "x_glove_pairs": 2.0,
    "x_syringes": 2, "x_needles": 2, "x_drapes": 1, "x_pharma_cost": 500.0,
    "x_cssd_weight": 0.5, "x_cssd_kwh_day": 128.0, "x_surg_cases_day": 60.0,
    "x_waste_kg": 0.3, "x_total_visits": 3,

    # Legacy / cross-pathway (still used by the Combined Patient Journey page)
    "ivi_visits_yr": 8.0,
    "glaucoma_visits_yr": 3.0,
}


# ─────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────

def kwh(w, minutes):
    return (w * minutes) / 60000


def co2(w, minutes):
    return kwh(w, minutes) * EF["grid"]


def pharma_from_cost(cost_inr, exchange_rate):
    """EIO-LCA proxy: convert INR spend to USD, apply kgCO2e/USD factor."""
    if not exchange_rate:
        return 0.0
    return (cost_inr / exchange_rate) * EF["pharma_usd"]


def pharma_emissions(method, cost_inr, exchange_rate, fixed_value):
    """Dispatches between the two pharma-accounting methods."""
    if method == "cost":
        return pharma_from_cost(cost_inr, exchange_rate)
    return fixed_value


# ─────────────────────────────────────────────────────────────────────────
# Shared building blocks (used across pathways)
# ─────────────────────────────────────────────────────────────────────────

def compute_opd():
    slit = co2(DEV["slit"], DEV["slit_min"])
    auto = co2(DEV["auto"], DEV["auto_min"])
    nct = co2(DEV["nct"], DEV["nct_min"])
    return {"slit": slit, "auto": auto, "nct": nct, "total": slit + auto + nct}


def compute_diag():
    oct_ = co2(DEV["oct"], DEV["oct_min"])
    clarus = co2(DEV["clarus"], DEV["clarus_min"])
    bscan = co2(DEV["bscan"], DEV["bscan_min"])
    return {"oct": oct_, "clarus": clarus, "bscan": bscan}


def ot_lighting_per_case(cases_day, ot_hours):
    cases_per_ot = cases_day / DEV["ot_count"] if DEV["ot_count"] else 0
    total_light_kwh = (DEV["ot_light"] * ot_hours) / 1000
    return ((total_light_kwh / cases_per_ot) if cases_per_ot > 0 else 0) * EF["grid"]


def cssd_per_case(cssd_kwh_day, weight, surg_cases_day):
    denom = surg_cases_day if surg_cases_day > 0 else 1
    return (cssd_kwh_day * weight / denom) * EF["grid"]


# ─────────────────────────────────────────────────────────────────────────
# Pathway: Cataract
# ─────────────────────────────────────────────────────────────────────────

def compute_cataract(p):
    opd = compute_opd()
    diag = compute_diag()

    surg_devices = (
        co2(DEV["centurion"], p["c_phaco_min"]) + co2(DEV["lumera"], p["c_phaco_min"])
        + co2(DEV["chair"], p["c_phaco_min"]) + co2(DEV["anaesth_standby"], p["c_phaco_min"])
    )
    ot_light = ot_lighting_per_case(p["c_phaco_cases_day"], p["c_ot_hours"])
    cssd = cssd_per_case(p["c_cssd_kwh_day"], p["c_cssd_weight"], p["c_surg_cases_day"])

    cons = (
        p["c_eye_drapes"] * 0.055 * EF["pe"]
        + p["c_glove_pairs"] * 0.025 * EF["nitrile"]
        + 0.120 * EF["pvc"]
        + (0.5 * EF["glass"] if p["c_bss_single_use"] else 0.5 * EF["glass"] / 10)
        + p["c_syringes"] * 0.012 * EF["pp"]
        + p["c_needles"] * 0.003 * EF["steel"]
        + 0.035 * EF["pp"] + 0.015 * EF["pp"] + 0.010 * EF["cotton"] + 0.014 * EF["pp"]
    )
    drug_bottles = (4 * 0.015 * EF["glass"]) if p["c_drugs_single_use"] else (4 * 0.015 * EF["glass"] / 20)

    pharma = pharma_emissions(p["pharma_method"], p["c_pharma_cost"], p["exchange_rate"], PHARMA_KGCO2["phaco"])

    waste_total = (
        0.170 * EF["waste_yellow"] + 0.230 * EF["waste_red"]
        + 0.130 * EF["waste_green"] + 0.024 * EF["waste_red"]
    )
    diag_elec = (diag["oct"] if p["c_has_oct"] else 0) + (co2(50, 3) if p["c_has_biometry"] else 0)

    components = {
        "OPD consultations": opd["total"] * max(p["c_total_visits"] - 1, 0),
        "Diagnostics": diag_elec,
        "Surgery devices": surg_devices,
        "OT lighting": ot_light,
        "CSSD sterilisation": cssd,
        "Consumables": cons + drug_bottles,
        "Pharmaceuticals": pharma,
        "Waste disposal": waste_total,
    }
    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd, "diag": diag,
            "surgery": {"centurion": co2(DEV["centurion"], p["c_phaco_min"]),
                        "lumera": co2(DEV["lumera"], p["c_phaco_min"]),
                        "chair": co2(DEV["chair"], p["c_phaco_min"]),
                        "anaesth": co2(DEV["anaesth_standby"], p["c_phaco_min"]),
                        "lighting": ot_light, "total": surg_devices + ot_light},
            "cssd_per_case": cssd, "consumables_total": cons + drug_bottles,
            "pharma": pharma, "waste_total": waste_total}


# ─────────────────────────────────────────────────────────────────────────
# Pathway: LASIK
# ─────────────────────────────────────────────────────────────────────────

def compute_lasik(p):
    opd = compute_opd()

    excimer = co2(p["l_excimer_w"], p["l_laser_min"])
    femto = co2(p["l_femto_w"], p["l_femto_min"]) if p["l_femto"] else 0
    microscope = co2(DEV["lumera"], p["l_microscope_min"])
    cases_per_ot = p["l_cases_day"] / DEV["ot_count"] if DEV["ot_count"] else 0
    ot_light = ((DEV["ot_light"] * 6 / 1000) / cases_per_ot) * EF["grid"] if cases_per_ot > 0 else 0

    cons = (
        p["l_eye_drapes"] * 0.055 * EF["pe"]
        + p["l_glove_pairs"] * 0.025 * EF["nitrile"]
        + p["l_suction_rings"] * 0.015 * EF["pp"]
        + (0.030 * EF["pp"] if p["l_femto"] else 0.010 * EF["steel"])
        + 0.008 * EF["pp"] + 0.010 * EF["pp"] + 0.014 * EF["pp"]
    )
    pharma = pharma_emissions(p["pharma_method"], p["l_pharma_cost"], p["exchange_rate"], PHARMA_KGCO2["lasik"])
    waste = 0.080 * EF["waste_yellow"] + 0.100 * EF["waste_red"] + 0.050 * EF["waste_green"]

    components = {
        "OPD consultations": opd["total"] * max(p["l_total_visits"] - 1, 0),
        "Diagnostics (topography + pachymetry)": co2(60, 5) + co2(30, 3),
        "Excimer laser": excimer,
        "Femtosecond laser": femto,
        "Operating microscope": microscope,
        "OT lighting": ot_light,
        "Consumables": cons,
        "Pharmaceuticals": pharma,
        "Waste disposal": waste,
    }
    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd}


# ─────────────────────────────────────────────────────────────────────────
# Pathway: Glaucoma
# ─────────────────────────────────────────────────────────────────────────

def compute_glaucoma(p):
    opd = compute_opd()
    diag = compute_diag()

    per_monitor_visit = (
        opd["total"]
        + (diag["oct"] if p["g_has_oct"] else 0)
        + (co2(p["g_perimeter_w"], p["g_perimeter_min"]) if p["g_has_perimetry"] else 0)
    )
    total_monitor = per_monitor_visit * p["g_monitor_visits_yr"] * p["g_years_followup"]

    chronic_drops = pharma_emissions(
        p["pharma_method"],
        p["g_drops_cost_month"] * 12 * p["g_years_followup"],
        p["exchange_rate"],
        PHARMA_KGCO2["glaucoma_yr"] * p["g_years_followup"],
    )

    slt_total = co2(p["g_slt_w"], p["g_slt_min"]) if p["g_laser_slt"] else 0

    surg_total = cssd = surg_cons = surg_pharma = surg_waste = 0
    if p["g_is_surgical"]:
        surg_total = (
            co2(DEV["centurion"], p["g_surg_min"]) + co2(DEV["lumera"], p["g_surg_min"])
            + co2(DEV["chair"], p["g_surg_min"]) + co2(DEV["anaesth_standby"], p["g_surg_min"])
        )
        cssd = cssd_per_case(p["g_cssd_kwh_day"], p["g_cssd_weight"], p["g_surg_cases_day"])
        surg_cons = (
            2 * 0.055 * EF["pe"] + p["g_glove_pairs"] * 0.025 * EF["nitrile"]
            + 4 * 0.012 * EF["pp"] + 6 * 0.003 * EF["steel"] + 0.010 * EF["cotton"] * 4
            + (0.005 * EF["glass"] if p["g_mitomycin"] else 0)
        )
        surg_pharma = pharma_emissions(p["pharma_method"], 800.0, p["exchange_rate"], 1.5)
        surg_waste = 0.150 * EF["waste_yellow"] + 0.180 * EF["waste_red"] + 0.024 * EF["waste_red"]

    components = {"Monitoring visits": total_monitor, "Chronic medication": chronic_drops}
    if p["g_laser_slt"]:
        components["SLT laser"] = slt_total
    if p["g_is_surgical"]:
        components["Trabeculectomy devices"] = surg_total
        components["CSSD (surgical)"] = cssd
        components["Surgical consumables"] = surg_cons
        components["Surgical pharma"] = surg_pharma
        components["Surgical waste"] = surg_waste

    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd, "diag": diag,
            "per_monitor_visit": per_monitor_visit}


# ─────────────────────────────────────────────────────────────────────────
# Pathway: Vitreoretinal
# ─────────────────────────────────────────────────────────────────────────

def compute_vitreoretinal(p):
    opd = compute_opd()
    diag = compute_diag()

    surg_devices = co2(DEV["centurion"], p["v_surg_min"]) + co2(DEV["lumera"], p["v_surg_min"]) + co2(DEV["chair"], p["v_surg_min"])
    if p["v_use_ga"]:
        ga = co2(DEV["anaesth_active"], p["v_ga_min"]) + ((p["v_sevo_ml"] * 1.52 / 1000) * EF["sevo_gwp"])
    else:
        ga = co2(DEV["anaesth_standby"], p["v_surg_min"])
    endolaser = co2(p["v_endolaser_w"], p["v_endolaser_min"]) if p["v_has_endolaser"] else 0

    cases_per_ot = p["v_vr_cases_day"] / DEV["ot_count"] if DEV["ot_count"] else 0
    ot_light = ((DEV["ot_light"] * 8 / 1000) / cases_per_ot) * EF["grid"] if cases_per_ot > 0 else 0
    cssd = cssd_per_case(p["v_cssd_kwh_day"], p["v_cssd_weight"], p["v_surg_cases_day"])

    if p["v_has_tamponade"]:
        tamponade = 0.010 * EF["silicone"] if p["v_tamponade_type"] == "silicone" else 0.002 * EF["pp"]
    else:
        tamponade = 0

    cons = (
        p["v_eye_drapes"] * 0.055 * EF["pe"] + p["v_glove_pairs"] * 0.025 * EF["nitrile"]
        + 0.120 * EF["pvc"] + 0.5 * EF["glass"] + p["v_syringes"] * 0.012 * EF["pp"]
        + p["v_needles"] * 0.003 * EF["steel"] + 0.010 * EF["cotton"] * 4 + 0.014 * EF["pp"] + tamponade
    )
    pharma = pharma_emissions(p["pharma_method"], p["v_pharma_cost"], p["exchange_rate"], PHARMA_KGCO2["vitreoretinal"])
    waste = 0.250 * EF["waste_yellow"] + 0.350 * EF["waste_red"] + 0.150 * EF["waste_green"] + 0.030 * EF["waste_red"]
    diag_elec = (diag["oct"] if p["v_has_oct"] else 0) + (diag["bscan"] if p["v_has_bscan"] else 0)

    components = {
        "OPD consultations": opd["total"] * max(p["v_total_visits"] - 1, 0),
        "Diagnostics": diag_elec,
        "Surgery devices": surg_devices,
        "Endolaser": endolaser,
        "Anaesthesia (GA)": ga,
        "OT lighting": ot_light,
        "CSSD sterilisation": cssd,
        "Consumables": cons,
        "Pharmaceuticals": pharma,
        "Waste disposal": waste,
    }
    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd, "diag": diag}


# ─────────────────────────────────────────────────────────────────────────
# Pathway: DR / IVI
# ─────────────────────────────────────────────────────────────────────────

def compute_dr_ivi(p):
    opd = compute_opd()
    diag = compute_diag()

    drug_cost_per_inj = p["d_drug_cost"] / p["d_patients_per_vial"] if p["d_split_vial"] and p["d_patients_per_vial"] else p["d_drug_cost"]
    total_injections = p["d_visits_yr"] * p["d_years_treatment"]

    per_ivi_device = co2(DEV["slit"], p["d_ivi_min"])
    per_ivi_cons = (
        1 * 0.055 * EF["pe"] + p["d_glove_pairs"] * 0.025 * EF["nitrile"]
        + 0.008 * EF["pp"] + 0.003 * EF["steel"] + 0.015 * EF["cotton"] + 0.005 * EF["pp"]
    )
    fixed_ivi_pharma = PHARMA_KGCO2["ivi_bevacizumab"] * (drug_cost_per_inj / 3000.0)
    per_ivi_pharma = pharma_emissions(
        p["pharma_method"], drug_cost_per_inj + p["d_pharma_cost_drops"], p["exchange_rate"], fixed_ivi_pharma
    )
    per_ivi_waste = 0.060 * EF["waste_yellow"] + 0.040 * EF["waste_red"] + 0.003 * EF["waste_red"]

    diag_per_visit = diag["oct"] if p["d_has_oct"] else 0
    ffa_cons = 0.012 * EF["pp"] + 0.015 * EF["pp"] + 0.025 * EF["nitrile"] + 0.008 * EF["glass"]
    ffa_total = (diag["clarus"] * p["d_ffa_freq"] + p["d_ffa_freq"] * ffa_cons) if p["d_has_ffa"] else 0

    components = {
        "OPD consultations": opd["total"] * total_injections,
        "OCT monitoring": diag_per_visit * total_injections,
        "FFA imaging": ffa_total,
        f"IVI procedures (×{total_injections:.0f})": (per_ivi_device + per_ivi_cons) * total_injections,
        f"IVI pharmaceuticals (×{total_injections:.0f})": per_ivi_pharma * total_injections,
        "IVI waste": per_ivi_waste * total_injections,
    }
    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd, "diag": diag,
            "total_injections": total_injections, "per_ivi_visit": per_ivi_device + per_ivi_cons + per_ivi_pharma + per_ivi_waste}


# ─────────────────────────────────────────────────────────────────────────
# Pathway: Custom
# ─────────────────────────────────────────────────────────────────────────

def compute_custom(p):
    opd = compute_opd()
    diag = compute_diag()

    opd_total = opd["total"] * p["x_opd_visits"]
    diag_total = (
        (diag["oct"] if p["x_has_oct"] else 0)
        + (diag["clarus"] if p["x_has_ffa"] else 0)
        + (diag["bscan"] if p["x_has_bscan"] else 0)
    )

    surg_total = cssd = surg_cons = waste = 0
    if p["x_has_surgery"]:
        surg_total = co2(p["x_surg_w"], p["x_surg_min"]) + co2(DEV["lumera"], p["x_surg_min"]) + co2(DEV["chair"], p["x_surg_min"])
        cssd = cssd_per_case(p["x_cssd_kwh_day"], p["x_cssd_weight"], p["x_surg_cases_day"])
        surg_cons = (
            p["x_drapes"] * 0.055 * EF["pe"] + p["x_glove_pairs"] * 0.025 * EF["nitrile"]
            + p["x_syringes"] * 0.012 * EF["pp"] + p["x_needles"] * 0.003 * EF["steel"] + 0.014 * EF["pp"]
        )
        waste = p["x_waste_kg"] * 0.4 * EF["waste_yellow"] + p["x_waste_kg"] * 0.5 * EF["waste_red"] + p["x_waste_kg"] * 0.1 * EF["waste_green"]

    pharma = pharma_emissions(p["pharma_method"], p["x_pharma_cost"], p["exchange_rate"], 1.0)

    components = {
        "OPD consultations": opd_total * p["x_total_visits"],
        "Diagnostics": diag_total,
    }
    if p["x_has_surgery"]:
        components["Surgery devices"] = surg_total
        components["CSSD"] = cssd
        components["Consumables"] = surg_cons
        components["Waste"] = waste
    components["Pharmaceuticals"] = pharma

    total = sum(components.values())
    return {"components": components, "total": total, "opd": opd, "diag": diag}


# ─────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────

PATHWAY_FUNCS = {
    "cataract": compute_cataract,
    "lasik": compute_lasik,
    "glaucoma": compute_glaucoma,
    "vitreoretinal": compute_vitreoretinal,
    "dr_ivi": compute_dr_ivi,
    "custom": compute_custom,
}


def compute_pathway(pathway_id: str, params: dict = None):
    """
    Runs the calculation for a single pathway given a dict of adjustable
    parameters (falls back to DEFAULT_PARAMS for anything not supplied).
    Returns {"components": {...}, "total": float, ...pathway-specific extras}.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    func = PATHWAY_FUNCS.get(pathway_id)
    if func is None:
        raise ValueError(f"Unknown pathway: {pathway_id}")
    return func(p)


def compute_all(params: dict = None):
    """
    Runs every pathway and also returns the legacy top-level keys
    (phaco_grand, cataract_episode, dr_episode_year, glaucoma_episode_year,
    opd_only_episode, per_glaucoma_visit) that the Combined Patient Journey
    page and the older Ophthalmology Calculator page rely on, so both
    keep working unmodified against this new engine.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    cataract = compute_cataract(p)
    lasik = compute_lasik(p)
    glaucoma = compute_glaucoma(p)
    vitreoretinal = compute_vitreoretinal(p)
    dr_ivi = compute_dr_ivi(p)
    custom = compute_custom(p)

    opd = compute_opd()
    diag = compute_diag()

    # Legacy aliases (episode length driven by the legacy ivi_visits_yr /
    # glaucoma_visits_yr knobs, so the Combined Patient Journey page's
    # existing sliders keep behaving the same way).
    dr_ivi_legacy_params = {**p, "d_visits_yr": p["ivi_visits_yr"], "d_years_treatment": 1.0}
    dr_ivi_year = compute_dr_ivi(dr_ivi_legacy_params)

    glaucoma_legacy_params = {**p, "g_monitor_visits_yr": p["glaucoma_visits_yr"], "g_years_followup": 1.0}
    glaucoma_year = compute_glaucoma(glaucoma_legacy_params)

    opd_only_episode = opd["total"]

    phaco_grand = (
        cataract["surgery"]["total"] + cataract["cssd_per_case"]
        + cataract["consumables_total"] + cataract["pharma"] + cataract["waste_total"]
        + diag["oct"] + opd["total"]
    )

    return {
        "params": p,
        "pathways": {
            "cataract": cataract, "lasik": lasik, "glaucoma": glaucoma,
            "vitreoretinal": vitreoretinal, "dr_ivi": dr_ivi, "custom": custom,
        },
        "opd": opd,
        "diag": diag,

        "phaco_grand": phaco_grand,
        "cataract_episode": cataract["total"],
        "dr_episode_year": dr_ivi_year["total"],
        "glaucoma_episode_year": glaucoma_year["total"],
        "opd_only_episode": opd_only_episode,
        "per_glaucoma_visit": glaucoma_year["per_monitor_visit"],
        "per_ivi_visit": dr_ivi_year["per_ivi_visit"],
    }