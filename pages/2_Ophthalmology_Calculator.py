import streamlit as st
import pandas as pd

from ophthalmology_calc import compute_all, EF

st.set_page_config(page_title="Ophthalmology Calculator", page_icon="🏥", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #F6F9F6; }
.page-title { font-family: 'DM Serif Display', serif; font-size: 2rem; color: #1A3A1A; margin-bottom:0.2rem; }
.page-sub { font-size: 0.9rem; color: #5A7A5A; margin-bottom: 1.5rem; }
</style>
""", unsafe_allow_html=True)


def row(label, value, unit="kg CO₂e", note=None, highlight=False, decimals=4):
    c1, c2 = st.columns([3, 1])
    with c1:
        txt = f"{label}"
        st.markdown(txt)
        if note:
            st.caption(note)
    with c2:
        val_str = f"{value:,.{decimals}f} {unit}" if isinstance(value, (int, float)) else f"{value} {unit}"
        color = "#2563eb" if highlight else "inherit"
        weight = 700 if highlight else 400
        st.markdown(
            f"<div style='text-align:right;font-weight:{weight};color:{color};padding-top:4px'>{val_str}</div>",
            unsafe_allow_html=True,
        )


def bar(label, value, max_val):
    pct = min(value / max_val, 1.0) if max_val > 0 else 0
    st.caption(f"{label} — **{value:.3f} kg**")
    st.progress(pct)


def section(title):
    st.markdown(f"##### {title}")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown('<div class="page-title">🏥 Ophthalmology Carbon Calculator</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Facility-based emissions for cataract surgery and diabetic retinopathy / IVI care pathways at LVPEI, KAR Campus, Hyderabad · GHG Protocol · CEA v21.0 · Benchmark: Thiel et al. 2017, JCRS 43(11):1391-1398</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Adjustable parameters (single shared panel — feeds every tab below)
# ---------------------------------------------------------------------------

with st.expander("⚙️ Adjustable Parameters", expanded=False):
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("**Surgery**")
        phaco_min = st.number_input("Phaco duration (min)", min_value=1.0, value=15.0, step=1.0, key="oph_phaco_min")
        phaco_cases_day = st.number_input("Phaco cases / day", min_value=1.0, value=40.0, step=1.0, key="oph_phaco_cases_day")
        surg_cases_day = st.number_input("Total surgical cases / day", min_value=1.0, value=60.0, step=1.0, key="oph_surg_cases_day")
        ot_hours = st.number_input("OT operating hours", min_value=1.0, value=8.0, step=1.0, key="oph_ot_hours")
    with p2:
        st.markdown("**Consumables, CSSD & Visit Frequency**")
        glove_pairs = st.number_input("Glove pairs / case", min_value=0.0, value=4.0, step=1.0, key="oph_glove_pairs")
        cssd_kwh_day = st.number_input("CSSD kWh / day", min_value=0.0, value=128.0, step=1.0, key="oph_cssd_kwh_day")
        ivi_visits_yr = st.number_input("IVI visits / year (DR pathway)", min_value=0.0, value=8.0, step=1.0, key="oph_ivi_visits_yr")
        glaucoma_visits_yr = st.number_input("Monitoring visits / year (Glaucoma)", min_value=0.0, value=3.0, step=1.0, key="oph_glaucoma_visits_yr")

st.caption("Pharmaceutical emissions (phaco, IVI, glaucoma medication) use fixed kgCO₂e assumptions — see the Reference tab.")

# ---------------------------------------------------------------------------
# Calculations (delegated to ophthalmology_calc.py — the single source of truth)
# ---------------------------------------------------------------------------

results = compute_all({
    "phaco_min": phaco_min,
    "phaco_cases_day": phaco_cases_day,
    "surg_cases_day": surg_cases_day,
    "ot_hours": ot_hours,
    "glove_pairs": glove_pairs,
    "cssd_kwh_day": cssd_kwh_day,
    "ivi_visits_yr": ivi_visits_yr,
    "glaucoma_visits_yr": glaucoma_visits_yr,
})

opd_total = results["opd"]["total"]
diag_oct = results["diag"]["oct"]
diag_clarus = results["diag"]["clarus"]
diag_bscan = results["diag"]["bscan"]
glaucoma_perimetry = results["glaucoma_diag"]["perimetry"]
surgery_total = results["surgery"]["total"]
surg_centurion = results["surgery"]["centurion"]
surg_lumera = results["surgery"]["lumera"]
surg_chair = results["surgery"]["chair"]
surg_anaesth = results["surgery"]["anaesth"]
ot_light_per_case = results["surgery"]["lighting"]
cssd_per_case = results["cssd_per_case"]
consumable_items = results["consumables"]["items"]
consumables_total = results["consumables"]["total"]
ivi_items = results["ivi_consumables"]["items"]
ivi_consumables_total = results["ivi_consumables"]["total"]
pharma_phaco = results["pharma"]["phaco"]
pharma_ivi = results["pharma"]["ivi"]
pharma_glaucoma = results["pharma"]["glaucoma"]
waste_yellow = results["waste"]["yellow"]
waste_red = results["waste"]["red"]
waste_green = results["waste"]["green"]
waste_sharps = results["waste"]["sharps"]
waste_total = results["waste"]["total"]
phaco_grand = results["phaco_grand"]
cataract_episode = results["cataract_episode"]
dr_episode_year = results["dr_episode_year"]
per_glaucoma_visit = results["per_glaucoma_visit"]
glaucoma_episode_year = results["glaucoma_episode_year"]

# ---------------------------------------------------------------------------
# Top summary cards
# ---------------------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
m1.metric("Per phaco case", f"{phaco_grand:.3f} kg CO₂e", f"Aravind benchmark: 5.89 kg")
m2.metric("Cataract episode", f"{cataract_episode:.3f} kg CO₂e", "OPD → surgery → follow-up (5 visits)")
m3.metric("DR / IVI episode", f"{dr_episode_year:.3f} kg CO₂e", f"{ivi_visits_yr:.0f} visits/year")
m4.metric("Glaucoma monitoring", f"{glaucoma_episode_year:.3f} kg CO₂e", f"{glaucoma_visits_yr:.0f} visits/year")


# ---------------------------------------------------------------------------
# Tabs (mirrors the original React tab bar)
# ---------------------------------------------------------------------------

tabs = st.tabs([
    "Per-Patient Summary", "OPD Encounter", "Diagnostics", "Phaco Surgery",
    "CSSD", "Consumables", "Pharma & Waste", "Condition Pathways", "Reference",
])

# ---- Summary ----
with tabs[0]:
    section("Per-Phaco Emission Breakdown")
    bar("CSSD sterilisation", cssd_per_case, phaco_grand)
    bar("Consumables", consumables_total, phaco_grand)
    bar("Surgery devices", surgery_total, phaco_grand)
    bar("Pharmaceuticals", pharma_phaco, phaco_grand)
    bar("Waste disposal", waste_total, phaco_grand)
    bar("OPD encounter", opd_total, phaco_grand)
    bar("OCT scan", diag_oct, phaco_grand)

    st.markdown("---")
    section("Benchmark Comparison (per surgical case)")
    bar("LVPEI KAR (this study)", phaco_grand, 130)
    bar("Aravind (Thiel et al. 2017)", 5.89, 130)
    bar("UK NHS (Morris et al. 2013)", 130, 130)
    st.caption(
        f"LVPEI is {phaco_grand / 5.89 * 100:.0f}% of Aravind and {phaco_grand / 130 * 100:.1f}% of UK NHS."
    )

    st.markdown("---")
    section("Key Differences from Aravind")
    row("Single-use gloves (vs reused)", 0.025 * glove_pairs * EF["nitrile"], "kg", "Aravind: ~0.011 kg")
    row("Single-use BSS bottle", 0.5 * EF["glass"], "kg", "Aravind: multi-patient")
    row("Single-use drug bottles", 0.05 * EF["glass"], "kg", "Aravind: multi-patient until empty")
    row("2 eye drapes (vs 1 at Aravind)", 0.110 * EF["pe"], "kg", "Aravind: 1 drape")

    st.info(
        "All values use LVPEI-specific data from the facility interview. Adjust parameters in the "
        "panel above. Patient travel is excluded here — see the Tele-ophthalmology pages."
    )

# ---- OPD ----
with tabs[1]:
    section("OPD Consultation — per patient")
    row("Zeiss BM900 slit-lamp (halogen)", results["opd"]["slit"], note="30W × 5 min")
    row("Autorefractometer", results["opd"]["auto"], note="50W × 3 min")
    row("NCT tonometer", results["opd"]["nct"], note="75W × 1 min")
    row("TOTAL per OPD consultation", opd_total, highlight=True)
    st.info(
        "This is device electricity only. HVAC/lighting overhead for the OPD waiting area would be "
        f"added via facility-level allocation. OPD device emissions are very small — "
        f"{(opd_total / phaco_grand * 100 if phaco_grand else 0):.1f}% of the total per-case footprint."
    )

# ---- Diagnostics ----
with tabs[2]:
    section("Diagnostics — per session (only if the patient receives this test)")
    row("Topcon DRI OCT Triton", diag_oct, note="~180W × 5 min, 12 patients/day")
    row("Zeiss Clarus 700 fundus camera", diag_clarus, note="~250W × 5 min, 12 patients/day")
    row("Accutome B-scan", diag_bscan, note="~40W × 5 min, 30 patients/day")
    row("Visual field perimeter (glaucoma pathway)", glaucoma_perimetry, note="~150W × 8 min, est.")
    st.markdown("---")
    section("Diagnostic combinations by condition pathway")
    row("Cataract patient: OCT only", diag_oct)
    row("DR patient: OCT + Clarus (FFA)", diag_oct + diag_clarus, note="+ FFA consumables (Scope 3)")
    row("VR patient: OCT + B-scan", diag_oct + diag_bscan)
    row("Glaucoma patient: OCT + perimetry (per monitoring visit)", diag_oct + glaucoma_perimetry, note="OCT is annual baseline; perimetry is per-visit")

# ---- Phaco Surgery ----
with tabs[3]:
    section("OT Device Electricity — per phaco case")
    row("Alcon Centurion (phaco + VR + cautery)", surg_centurion, note=f"400W × {phaco_min:.0f} min")
    row("Zeiss OPMI Lumera T microscope", surg_lumera, note=f"250W × {phaco_min:.0f} min")
    row("OT ceiling lighting (allocated)", ot_light_per_case, note=f"350W × {ot_hours:.0f}h ÷ cases/OT")
    row("Surgline SESK chair", surg_chair, note=f"50W avg × {phaco_min:.0f} min")
    row("GE Carestation 620 (standby)", surg_anaesth, note="20W standby (GA not used for phaco)")
    row("TOTAL surgery devices", surgery_total, highlight=True)
    st.info(
        "14 OTs at KAR Campus. Lighting is allocated per OT per case. Change the phaco duration in "
        "the Adjustable Parameters panel above and every value here updates automatically."
    )

# ---- CSSD ----
with tabs[4]:
    section("CSSD Sterilisation — allocated per surgical case")
    row("CSSD kWh per case", cssd_kwh_day / surg_cases_day if surg_cases_day else 0, "kWh")
    row("CSSD CO₂e per case", cssd_per_case, highlight=True)
    row("Share of total per-case footprint", (cssd_per_case / phaco_grand * 100) if phaco_grand else 0, "%")
    st.warning(
        "**Largest single component.** Consistent with Thiel et al.'s finding that sterilisation "
        "comprised over 50% of lifecycle emissions at Aravind. LVPEI uses reusable gowns → more CSSD "
        "energy but less consumable waste. This is the intended trade-off."
    )

# ---- Consumables ----
with tabs[5]:
    section("Consumables per phaco case (Scope 3, Category 1)")
    cons_df = pd.DataFrame(
        [{"Item": i["name"], "Mass (g)": round(i["mass"] * 1000, 1), "EF (kg/kg)": i["ef"], "CO₂e (kg)": round(i["co2"], 4)} for i in consumable_items]
    )
    st.dataframe(cons_df, use_container_width=True, hide_index=True)
    row("TOTAL consumables", consumables_total, highlight=True)

    st.markdown("---")
    section("IVI procedure consumables (for DR pathway)")
    ivi_df = pd.DataFrame(
        [{"Item": i["name"], "Mass (g)": round(i["mass"] * 1000, 1), "CO₂e (kg)": round(i["co2"], 4)} for i in ivi_items]
    )
    st.dataframe(ivi_df, use_container_width=True, hide_index=True)
    row("TOTAL IVI consumables", ivi_consumables_total, highlight=True)

# ---- Pharma & Waste ----
with tabs[6]:
    section("Pharmaceuticals (EIO-LCA proxy)")
    row("Phaco pharma emissions", pharma_phaco, highlight=True)
    row("IVI pharma emissions", pharma_ivi, highlight=True)
    st.caption(
        "Fixed kgCO₂e assumptions derived from an economic input-output LCA proxy (Carnegie Mellon, "
        "NAICS 325411) — no Indian pharma LCI exists. IVI is dramatically higher because the "
        "bevacizumab vial is not split across patients."
    )

    st.markdown("---")
    section("Waste per phaco case (estimated from consumables)")
    row("Yellow bin → incineration", waste_yellow, note="170g soiled drapes, swabs, gloves")
    row("Red bin → autoclave + landfill", waste_red, note="230g syringes, cassette, cannulas")
    row("Green bin → recycling", waste_green, note="130g packaging (net offset)")
    row("Sharps → encapsulation", waste_sharps, note="24g needles, blades")
    row("TOTAL waste", waste_total, highlight=True)
    row("Total waste mass", 0.554, "kg/case", note="Aravind benchmark: 0.250 kg")

# ---- Condition Pathways ----
with tabs[7]:
    section("Cataract Episode (OPD → surgery → follow-up)")
    row("OPD consultations × 4 (initial + pre-op + 2 follow-ups)", opd_total * 4)
    row("OCT scan × 1", diag_oct)
    row("Surgery (devices)", surgery_total)
    row("CSSD sterilisation", cssd_per_case)
    row("Surgical consumables", consumables_total)
    row("Pharmaceuticals (phaco)", pharma_phaco)
    row("Waste disposal", waste_total)
    row("TOTAL cataract episode", cataract_episode, highlight=True)

    st.markdown("---")
    section(f"DR / IVI Episode ({ivi_visits_yr:.0f} visits/year)")
    row(f"OPD + OCT + IVI consumables + pharma × {ivi_visits_yr:.0f} visits", dr_episode_year - diag_clarus)
    row("FFA imaging × 1 (baseline)", diag_clarus)
    row("TOTAL DR episode (per year)", dr_episode_year, highlight=True)
    row("Per IVI visit", dr_episode_year / ivi_visits_yr if ivi_visits_yr else 0)

    st.markdown("---")
    section(f"Glaucoma Monitoring Episode ({glaucoma_visits_yr:.0f} visits/year)")
    row(f"OPD + visual field test + minor waste × {glaucoma_visits_yr:.0f} visits", per_glaucoma_visit * glaucoma_visits_yr)
    row("OCT (optic nerve/RNFL) × 1 (baseline)", diag_oct)
    row("Topical medication (annual, EIO-LCA proxy)", pharma_glaucoma)
    row("TOTAL glaucoma monitoring (per year)", glaucoma_episode_year, highlight=True)
    row("Per monitoring visit", per_glaucoma_visit)
    st.caption(
        "No surgery, CSSD, or single-use surgical consumables — glaucoma is managed medically here, "
        "not surgically. Footprint is dominated by ongoing topical medication, not clinic energy use. "
        "Visit frequency is adjustable above; the medication emissions figure is a fixed assumption — "
        "confirm against LVPEI glaucoma clinic data."
    )

    st.markdown("---")
    section("Pathway Comparison")
    max_ep = max(cataract_episode, dr_episode_year, glaucoma_episode_year)
    bar("Cataract (one-time episode)", cataract_episode, max_ep)
    bar(f"DR / IVI (annual, {ivi_visits_yr:.0f} visits)", dr_episode_year, max_ep)
    bar(f"Glaucoma (annual, {glaucoma_visits_yr:.0f} visits)", glaucoma_episode_year, max_ep)
    ratio = (dr_episode_year / cataract_episode) if cataract_episode else 0
    driver = "pharma emissions (single-use bevacizumab vials)" if pharma_ivi > (opd_total * ivi_visits_yr) else "repeat visit volume"
    st.caption(f"DR/IVI is {ratio:.1f}× the cataract episode. The dominant driver is {driver}.")

# ---- Reference ----
with tabs[8]:
    section("Grid Emission Factor")
    row("All-India Unified Grid (CEA v21.0, FY 2024-25)", EF["grid"], "kg CO₂/kWh", note="cea.nic.in")

    st.markdown("---")
    section("Fuel EF (IPCC 2006)")
    row("Diesel", EF["diesel"], "kg CO₂e/L")

    st.markdown("---")
    section("Material EFs (Ecoinvent v3.9 proxy)")
    material_df = pd.DataFrame(
        [
            {"Material": "Polypropylene", "kgCO₂e/kg": EF["pp"]},
            {"Material": "Polyethylene", "kgCO₂e/kg": EF["pe"]},
            {"Material": "PVC", "kgCO₂e/kg": EF["pvc"]},
            {"Material": "Nitrile rubber", "kgCO₂e/kg": EF["nitrile"]},
            {"Material": "Cotton", "kgCO₂e/kg": EF["cotton"]},
            {"Material": "Stainless steel", "kgCO₂e/kg": EF["steel"]},
            {"Material": "Glass", "kgCO₂e/kg": EF["glass"]},
            {"Material": "Paper", "kgCO₂e/kg": EF["paper"]},
        ]
    )
    st.dataframe(material_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("Waste EFs (IPCC 2006, Vol. 5)")
    waste_df = pd.DataFrame(
        [
            {"Stream": "Yellow (incineration)", "kgCO₂e/kg": EF["waste_yellow"]},
            {"Stream": "Red (landfill)", "kgCO₂e/kg": EF["waste_red"]},
            {"Stream": "Green (recycling)", "kgCO₂e/kg": EF["waste_green"]},
        ]
    )
    st.dataframe(waste_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("Transport EFs (for reference — used in the Tele-ophthalmology pages)")
    transport_df = pd.DataFrame(
        [
            {"Mode": "Bus (TSRTC)", "kgCO₂e/p-km": 0.064, "Source": "TERI"},
            {"Mode": "Auto (CNG)", "kgCO₂e/p-km": 0.105, "Source": "IPCC + MoRTH"},
            {"Mode": "Two-wheeler", "kgCO₂e/p-km": 0.043, "Source": "India-specific"},
            {"Mode": "Car (petrol)", "kgCO₂e/p-km": 0.161, "Source": "MoRTH"},
        ]
    )
    st.dataframe(transport_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("LVPEI Equipment (from facility interview)")
    equip_df = pd.DataFrame(
        [
            {"Equipment": "Slit-lamp: Zeiss BM900", "Wattage (W)": 30, "Note": "halogen, 60 units"},
            {"Equipment": "OCT: Topcon DRI Triton", "Wattage (W)": 180, "Note": "est., 12 pts/day"},
            {"Equipment": "Fundus: Zeiss Clarus 700", "Wattage (W)": 250, "Note": "est., 12 pts/day"},
            {"Equipment": "B-scan: Accutome", "Wattage (W)": 40, "Note": "est., 30 pts/day"},
            {"Equipment": "Phaco: Alcon Centurion", "Wattage (W)": 400, "Note": "active; 90W standby"},
            {"Equipment": "Microscope: Zeiss Lumera T", "Wattage (W)": 250, "Note": "est."},
            {"Equipment": "Chair: Surgline SESK", "Wattage (W)": 50, "Note": "avg."},
            {"Equipment": "Anaesthesia: GE Carestation 620", "Wattage (W)": 250, "Note": "active; 20W standby"},
            {"Equipment": "OT lighting (per room)", "Wattage (W)": 350, "Note": "fluorescent panel + LEDs"},
            {"Equipment": "CSSD: V-PKO 60 × 4", "Wattage (W)": 5000, "Note": "5kW each"},
            {"Equipment": "CSSD: PSI 6060 × 4", "Wattage (W)": 4000, "Note": "4kW each"},
        ]
    )
    st.dataframe(equip_df, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Ophthalmology (facility-based) calculator — Shlok Marda (2024B1A40944H). "
    "Tele-ophthalmology (patient travel) calculator — Daiwik Singh (2024B1A41063H). "
    "Joint PS-I project, LVPEI, under Dr. Padmaja Kumari Rani. "
    "Reference: Thiel CL et al., JCRS 2017; 43(11):1391-1398."
)