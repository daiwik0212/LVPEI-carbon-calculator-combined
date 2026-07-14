import streamlit as st
import pandas as pd

from ophthalmology_calc import (
    compute_all, compute_pathway, EF, DEV, DEFAULT_PARAMS, PATHWAYS,
)

st.set_page_config(page_title="Ophthalmology Calculator", page_icon="🏥", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #F6F9F6; }
.page-title { font-family: 'DM Serif Display', serif; font-size: 2rem; color: #1A3A1A; margin-bottom:0.2rem; }
.page-sub { font-size: 0.9rem; color: #5A7A5A; margin-bottom: 1.5rem; }
.total-card {
    border-radius: 12px; padding: 1.2rem 1.6rem; margin-bottom: 1rem;
    background: #EEF6EE; border: 1px solid #C5DCC5;
}
.total-value { font-size: 2.4rem; font-weight: 800; color: #1A3A1A; line-height: 1; }
.total-label { font-size: 0.78rem; color: #5A7A5A; text-transform: uppercase; letter-spacing: 0.08em; }
</style>
""", unsafe_allow_html=True)


def row(label, value, unit="kg CO₂e", note=None, highlight=False, decimals=4):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(label)
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
st.markdown(
    '<div class="page-sub">Facility-based emissions across 6 care pathways at LVPEI, KAR Campus, Hyderabad · '
    'GHG Protocol · CEA v21.0 · Benchmark: Thiel et al. 2017, JCRS 43(11):1391-1398</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Pathway selector
# ---------------------------------------------------------------------------

pathway_labels = [f'{pw["icon"]} {pw["label"]}' for pw in PATHWAYS]
pathway_ids = [pw["id"] for pw in PATHWAYS]
selected_label = st.radio("Care pathway", pathway_labels, horizontal=True, key="oph_pathway_select")
pathway_id = pathway_ids[pathway_labels.index(selected_label)]
pw_meta = PATHWAYS[pathway_ids.index(pathway_id)]

# ---------------------------------------------------------------------------
# Global settings (pharma method + exchange rate)
# ---------------------------------------------------------------------------

with st.expander("⚙️ Global Settings — Pharmaceutical Accounting Method", expanded=False):
    gs1, gs2 = st.columns(2)
    with gs1:
        pharma_method_label = st.radio(
            "Pharma emissions method",
            ["Fixed kgCO₂e assumptions (legacy)", "Cost-based EIO-LCA (₹ ÷ exchange rate)"],
            key="oph_pharma_method_label",
            help="Fixed: locked kgCO₂e figures per procedure. Cost-based: converts pharma spend "
                 "(₹) to USD and applies a kgCO₂e/USD proxy factor — lets you flex pharma cost per case.",
        )
        pharma_method = "fixed" if pharma_method_label.startswith("Fixed") else "cost"
    with gs2:
        exchange_rate = st.number_input(
            "Exchange rate (₹/USD)", min_value=1.0, value=83.5, step=0.5,
            key="oph_exchange_rate", disabled=(pharma_method == "fixed"),
            help="Only used when the cost-based pharma method is selected.",
        )

st.caption("Adjust pathway-specific parameters in the panel below. Every result updates live.")
st.divider()

# ---------------------------------------------------------------------------
# Pathway-specific parameter panel
# ---------------------------------------------------------------------------

col_vars, col_results = st.columns([1, 1])

params = {"pharma_method": pharma_method, "exchange_rate": exchange_rate}

with col_vars:
    st.markdown(f"##### Adjustable Variables — {pw_meta['icon']} {pw_meta['label']}")

    if pathway_id == "cataract":
        st.markdown("**Surgery**")
        params["c_phaco_min"] = st.number_input("Phaco duration (min)", min_value=1.0, value=15.0, step=1.0, key="c_phaco_min", help="Patient in → out. Aravind: 9 min")
        params["c_phaco_cases_day"] = st.number_input("Phaco cases / day", min_value=1.0, value=40.0, step=1.0, key="c_phaco_cases_day")
        params["c_surg_cases_day"] = st.number_input("Total surgical cases / day", min_value=1.0, value=60.0, step=1.0, key="c_surg_cases_day", help="CSSD allocation denominator")
        params["c_ot_hours"] = st.number_input("OT operating hours", min_value=1.0, value=8.0, step=1.0, key="c_ot_hours")
        params["c_cssd_weight"] = st.number_input("CSSD weight factor (×)", min_value=0.1, value=1.0, step=0.1, key="c_cssd_weight", help="1.0 = equal share; higher = more complex sterilisation load")
        params["c_cssd_kwh_day"] = st.number_input("CSSD total kWh / day", min_value=0.0, value=128.0, step=1.0, key="c_cssd_kwh_day")

        st.markdown("**Consumables**")
        params["c_eye_drapes"] = st.number_input("Eye drapes / case", min_value=0, value=2, step=1, key="c_eye_drapes")
        params["c_glove_pairs"] = st.number_input("Glove pairs / case", min_value=0.0, value=4.0, step=1.0, key="c_glove_pairs", help="Aravind: reused ~10 cases")
        params["c_syringes"] = st.number_input("Syringes / case", min_value=0, value=5, step=1, key="c_syringes")
        params["c_needles"] = st.number_input("Needles / case", min_value=0, value=8, step=1, key="c_needles")
        params["c_bss_single_use"] = st.toggle("BSS single-use per patient", value=True, key="c_bss_single_use", help="Aravind: shared until empty")
        params["c_drugs_single_use"] = st.toggle("Drug bottles single-use", value=True, key="c_drugs_single_use", help="Aravind: multi-patient")

        st.markdown("**Diagnostics & Visits**")
        params["c_has_oct"] = st.toggle("OCT scan included", value=True, key="c_has_oct")
        params["c_has_biometry"] = st.toggle("Biometry included", value=True, key="c_has_biometry")
        params["c_total_visits"] = st.number_input("Total visits in episode", min_value=1, value=5, step=1, key="c_total_visits", help="OPD + pre-op + surgery + follow-ups")

        st.markdown("**Pharmaceuticals**")
        params["c_pharma_cost"] = st.number_input("Pharma cost per case (₹)", min_value=0.0, value=500.0, step=50.0, key="c_pharma_cost", help="Pre-op + intra-op + post-op drops. Only used if cost-based method selected above.")

    elif pathway_id == "lasik":
        st.markdown("**Laser**")
        params["l_excimer_w"] = st.number_input("Excimer laser wattage (W)", min_value=1.0, value=800.0, step=10.0, key="l_excimer_w")
        params["l_laser_min"] = st.number_input("Excimer ablation duration (min)", min_value=0.1, value=5.0, step=0.5, key="l_laser_min")
        params["l_femto"] = st.toggle("Femtosecond laser (flap)", value=True, key="l_femto", help="vs microkeratome blade")
        if params["l_femto"]:
            params["l_femto_w"] = st.number_input("Femto laser wattage (W)", min_value=1.0, value=500.0, step=10.0, key="l_femto_w")
            params["l_femto_min"] = st.number_input("Femto flap duration (min)", min_value=0.1, value=3.0, step=0.5, key="l_femto_min")
        else:
            params["l_femto_w"], params["l_femto_min"] = 500.0, 3.0
        params["l_microscope_min"] = st.number_input("Microscope duration (min)", min_value=0.1, value=8.0, step=0.5, key="l_microscope_min")
        params["l_cases_day"] = st.number_input("LASIK cases / day", min_value=1.0, value=15.0, step=1.0, key="l_cases_day")

        st.markdown("**Consumables**")
        params["l_eye_drapes"] = st.number_input("Eye drapes / case", min_value=0, value=1, step=1, key="l_eye_drapes")
        params["l_suction_rings"] = st.number_input("Suction rings / case", min_value=0, value=1, step=1, key="l_suction_rings")
        params["l_glove_pairs"] = st.number_input("Glove pairs / case", min_value=0.0, value=2.0, step=1.0, key="l_glove_pairs")

        st.markdown("**Pharma & Visits**")
        params["l_pharma_cost"] = st.number_input("Pharma cost per case (₹)", min_value=0.0, value=800.0, step=50.0, key="l_pharma_cost")
        params["l_total_visits"] = st.number_input("Total visits in episode", min_value=1, value=5, step=1, key="l_total_visits")

    elif pathway_id == "glaucoma":
        st.markdown("**Monitoring**")
        params["g_monitor_visits_yr"] = st.number_input("Monitoring visits / year", min_value=0.0, value=4.0, step=1.0, key="g_monitor_visits_yr")
        params["g_years_followup"] = st.number_input("Years of follow-up", min_value=0.0, value=5.0, step=1.0, key="g_years_followup", help="Chronic condition; cumulative emissions")
        params["g_has_oct"] = st.toggle("OCT each visit", value=True, key="g_has_oct")
        params["g_has_perimetry"] = st.toggle("Perimetry (visual fields)", value=True, key="g_has_perimetry")
        if params["g_has_perimetry"]:
            params["g_perimeter_w"] = st.number_input("Perimeter wattage (W)", min_value=1.0, value=40.0, step=5.0, key="g_perimeter_w")
            params["g_perimeter_min"] = st.number_input("Perimetry duration (min)", min_value=0.1, value=15.0, step=1.0, key="g_perimeter_min")
        else:
            params["g_perimeter_w"], params["g_perimeter_min"] = 40.0, 15.0

        st.markdown("**Medication**")
        params["g_drops_cost_month"] = st.number_input("Eye drops cost / month (₹)", min_value=0.0, value=300.0, step=25.0, key="g_drops_cost_month", help="Timolol / brimonidine / latanoprost")

        st.markdown("**Intervention**")
        params["g_laser_slt"] = st.toggle("SLT laser performed", value=False, key="g_laser_slt")
        if params["g_laser_slt"]:
            params["g_slt_w"] = st.number_input("SLT laser wattage (W)", min_value=1.0, value=200.0, step=10.0, key="g_slt_w")
            params["g_slt_min"] = st.number_input("SLT duration (min)", min_value=0.1, value=10.0, step=1.0, key="g_slt_min")
        else:
            params["g_slt_w"], params["g_slt_min"] = 200.0, 10.0
        params["g_is_surgical"] = st.toggle("Trabeculectomy surgery", value=False, key="g_is_surgical")
        if params["g_is_surgical"]:
            params["g_surg_min"] = st.number_input("Surgery duration (min)", min_value=1.0, value=30.0, step=5.0, key="g_surg_min")
            params["g_glove_pairs"] = st.number_input("Glove pairs (surgical)", min_value=0.0, value=3.0, step=1.0, key="g_glove_pairs")
            params["g_mitomycin"] = st.toggle("Mitomycin-C used", value=False, key="g_mitomycin")
            params["g_cssd_weight"] = st.number_input("CSSD weight factor (×)", min_value=0.1, value=1.2, step=0.1, key="g_cssd_weight")
            params["g_cssd_kwh_day"] = st.number_input("CSSD kWh / day", min_value=0.0, value=128.0, step=1.0, key="g_cssd_kwh_day_glauc")
            params["g_surg_cases_day"] = st.number_input("Total surgical cases / day", min_value=1.0, value=60.0, step=1.0, key="g_surg_cases_day")
        else:
            params.update(g_surg_min=30.0, g_glove_pairs=3.0, g_mitomycin=False, g_cssd_weight=1.2, g_cssd_kwh_day=128.0, g_surg_cases_day=60.0)

    elif pathway_id == "vitreoretinal":
        st.markdown("**Surgery**")
        params["v_surg_min"] = st.number_input("Vitrectomy duration (min)", min_value=1.0, value=60.0, step=5.0, key="v_surg_min", help="Typically 45–90 min")
        params["v_vr_cases_day"] = st.number_input("VR cases / day", min_value=1.0, value=8.0, step=1.0, key="v_vr_cases_day")
        params["v_surg_cases_day"] = st.number_input("Total surgical cases / day", min_value=1.0, value=60.0, step=1.0, key="v_surg_cases_day")
        params["v_use_ga"] = st.toggle("General anaesthesia", value=True, key="v_use_ga", help="Most VR cases require GA")
        if params["v_use_ga"]:
            params["v_ga_min"] = st.number_input("GA duration (min)", min_value=1.0, value=90.0, step=5.0, key="v_ga_min")
            params["v_sevo_ml"] = st.number_input("Sevoflurane consumed (mL)", min_value=0.0, value=15.0, step=1.0, key="v_sevo_ml", help="GWP₁₀₀ = 130")
        else:
            params["v_ga_min"], params["v_sevo_ml"] = 90.0, 15.0
        params["v_has_endolaser"] = st.toggle("Endolaser used", value=True, key="v_has_endolaser")
        if params["v_has_endolaser"]:
            params["v_endolaser_w"] = st.number_input("Endolaser wattage (W)", min_value=1.0, value=300.0, step=10.0, key="v_endolaser_w")
            params["v_endolaser_min"] = st.number_input("Endolaser duration (min)", min_value=0.1, value=10.0, step=1.0, key="v_endolaser_min")
        else:
            params["v_endolaser_w"], params["v_endolaser_min"] = 300.0, 10.0
        params["v_has_tamponade"] = st.toggle("Tamponade used", value=True, key="v_has_tamponade")
        if params["v_has_tamponade"]:
            params["v_tamponade_type"] = st.radio("Tamponade type", ["gas", "silicone"], horizontal=True, key="v_tamponade_type", format_func=lambda t: "Gas (C₃F₈/SF₆)" if t == "gas" else "Silicone oil")
        else:
            params["v_tamponade_type"] = "gas"

        st.markdown("**Consumables & CSSD**")
        params["v_eye_drapes"] = st.number_input("Eye drapes / case", min_value=0, value=2, step=1, key="v_eye_drapes")
        params["v_glove_pairs"] = st.number_input("Glove pairs / case", min_value=0.0, value=4.0, step=1.0, key="v_glove_pairs")
        params["v_syringes"] = st.number_input("Syringes / case", min_value=0, value=8, step=1, key="v_syringes")
        params["v_needles"] = st.number_input("Needles / case", min_value=0, value=10, step=1, key="v_needles")
        params["v_cssd_weight"] = st.number_input("CSSD weight factor (×)", min_value=0.1, value=1.5, step=0.1, key="v_cssd_weight", help="VR uses more trays; 1.5× typical")
        params["v_cssd_kwh_day"] = st.number_input("CSSD kWh / day", min_value=0.0, value=128.0, step=1.0, key="v_cssd_kwh_day")

        st.markdown("**Diagnostics & Visits**")
        params["v_has_oct"] = st.toggle("OCT included", value=True, key="v_has_oct")
        params["v_has_bscan"] = st.toggle("B-scan included", value=True, key="v_has_bscan")
        params["v_total_visits"] = st.number_input("Total visits in episode", min_value=1, value=8, step=1, key="v_total_visits")
        params["v_pharma_cost"] = st.number_input("Pharma cost per case (₹)", min_value=0.0, value=2000.0, step=100.0, key="v_pharma_cost")

    elif pathway_id == "dr_ivi":
        st.markdown("**Anti-VEGF drug**")
        drug_options = {"bevacizumab": ("Bevacizumab", 3000.0), "ranibizumab": ("Ranibizumab", 18000.0), "aflibercept": ("Aflibercept", 32000.0)}
        drug_choice = st.radio("Drug used", list(drug_options.keys()), horizontal=True, format_func=lambda k: drug_options[k][0], key="d_drug")
        params["d_drug"] = drug_choice
        default_cost = drug_options[drug_choice][1]
        params["d_drug_cost"] = st.number_input("Drug cost per vial (₹)", min_value=0.0, value=default_cost, step=500.0, key=f"d_drug_cost_{drug_choice}")
        params["d_split_vial"] = st.toggle("Vial split across patients", value=False, key="d_split_vial", help="LVPEI: currently not split")
        if params["d_split_vial"]:
            params["d_patients_per_vial"] = st.number_input("Patients per vial", min_value=1, value=1, step=1, key="d_patients_per_vial")
        else:
            params["d_patients_per_vial"] = 1

        st.markdown("**Treatment schedule**")
        params["d_visits_yr"] = st.number_input("IVI visits / year", min_value=0.0, value=8.0, step=1.0, key="d_visits_yr", help="Typically 6–12 for treatment-naïve")
        params["d_years_treatment"] = st.number_input("Years of treatment", min_value=0.0, value=2.0, step=1.0, key="d_years_treatment")
        params["d_ivi_min"] = st.number_input("IVI procedure duration (min)", min_value=0.1, value=5.0, step=1.0, key="d_ivi_min")

        st.markdown("**Consumables & diagnostics**")
        params["d_glove_pairs"] = st.number_input("Glove pairs / IVI", min_value=0.0, value=1.0, step=1.0, key="d_glove_pairs")
        params["d_pharma_cost_drops"] = st.number_input("Ancillary drops cost / visit (₹)", min_value=0.0, value=200.0, step=25.0, key="d_pharma_cost_drops")
        params["d_has_oct"] = st.toggle("OCT each visit", value=True, key="d_has_oct")
        params["d_has_ffa"] = st.toggle("FFA performed", value=True, key="d_has_ffa")
        if params["d_has_ffa"]:
            params["d_ffa_freq"] = st.number_input("FFA sessions in episode", min_value=0, value=1, step=1, key="d_ffa_freq")
        else:
            params["d_ffa_freq"] = 0

    elif pathway_id == "custom":
        st.markdown("**Encounters**")
        params["x_opd_visits"] = st.number_input("OPD visits", min_value=0, value=1, step=1, key="x_opd_visits")
        params["x_total_visits"] = st.number_input("Total visits in episode", min_value=1, value=3, step=1, key="x_total_visits")
        params["x_has_oct"] = st.toggle("OCT scan", value=False, key="x_has_oct")
        params["x_has_ffa"] = st.toggle("FFA imaging", value=False, key="x_has_ffa")
        params["x_has_bscan"] = st.toggle("B-scan", value=False, key="x_has_bscan")

        st.markdown("**Surgery (optional)**")
        params["x_has_surgery"] = st.toggle("Includes surgery", value=False, key="x_has_surgery")
        if params["x_has_surgery"]:
            params["x_surg_w"] = st.number_input("Primary device wattage (W)", min_value=1.0, value=400.0, step=10.0, key="x_surg_w")
            params["x_surg_min"] = st.number_input("Surgery duration (min)", min_value=0.1, value=15.0, step=1.0, key="x_surg_min")
            params["x_drapes"] = st.number_input("Drapes / case", min_value=0, value=1, step=1, key="x_drapes")
            params["x_glove_pairs"] = st.number_input("Glove pairs / case", min_value=0.0, value=2.0, step=1.0, key="x_glove_pairs")
            params["x_syringes"] = st.number_input("Syringes / case", min_value=0, value=2, step=1, key="x_syringes")
            params["x_needles"] = st.number_input("Needles / case", min_value=0, value=2, step=1, key="x_needles")
            params["x_waste_kg"] = st.number_input("Waste mass (kg)", min_value=0.0, value=0.3, step=0.05, key="x_waste_kg")
            params["x_cssd_weight"] = st.number_input("CSSD weight (×)", min_value=0.0, value=0.5, step=0.1, key="x_cssd_weight")
            params["x_cssd_kwh_day"] = st.number_input("CSSD kWh / day", min_value=0.0, value=128.0, step=1.0, key="x_cssd_kwh_day")
            params["x_surg_cases_day"] = st.number_input("Surgical cases / day", min_value=1.0, value=60.0, step=1.0, key="x_surg_cases_day")
        else:
            params.update(x_surg_w=400.0, x_surg_min=15.0, x_drapes=1, x_glove_pairs=2.0, x_syringes=2, x_needles=2,
                           x_waste_kg=0.3, x_cssd_weight=0.5, x_cssd_kwh_day=128.0, x_surg_cases_day=60.0)

        st.markdown("**Pharma**")
        params["x_pharma_cost"] = st.number_input("Pharma cost (₹)", min_value=0.0, value=500.0, step=50.0, key="x_pharma_cost")

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

result = compute_pathway(pathway_id, params)
components = result["components"]
total = result["total"]

with col_results:
    st.markdown(f"##### Emission Breakdown — {pw_meta['icon']} {pw_meta['label']}")
    st.markdown(f"""
    <div class="total-card">
        <div class="total-label">Total per patient / episode</div>
        <div class="total-value">{total:.3f} <span style="font-size:1.1rem;font-weight:500;">kg CO₂e</span></div>
    </div>
    """, unsafe_allow_html=True)

    max_comp = max([v for v in components.values() if v], default=0.001)
    for label, value in sorted(components.items(), key=lambda kv: -kv[1]):
        if value != 0:
            bar(label, value, max_comp)

    if components:
        top_label, top_val = max(components.items(), key=lambda kv: kv[1])
        pct = (top_val / total * 100) if total else 0
        st.info(f"**Largest contributor:** {top_label} ({pct:.1f}% of total)")

    if pathway_id == "cataract" and total > 0:
        st.caption(f"{'✅' if total < 5.89 else '⚠️'} {total/5.89*100:.0f}% of Aravind benchmark (5.89 kg) · {total/130*100:.1f}% of UK NHS (~130 kg)")
    elif pathway_id == "dr_ivi":
        st.caption("DR/IVI is typically the highest-emission pathway due to repeat visits and anti-VEGF drug cost. Splitting bevacizumab vials would reduce pharma emissions substantially.")
    elif pathway_id == "vitreoretinal":
        st.caption("VR surgery has the highest per-case device electricity due to long duration + GA. Sevoflurane GWP (130×) adds significant Scope 1 emissions.")
    elif pathway_id == "glaucoma":
        yrs = params.get("g_years_followup", 5)
        vis = params.get("g_monitor_visits_yr", 4)
        st.caption(f"Glaucoma has low per-visit emissions but high cumulative burden. {yrs:.0f} years × {vis:.0f} visits = {yrs*vis:.0f} total encounters.")
    elif pathway_id == "lasik":
        femto_note = "Femtosecond laser adds significant device electricity." if params.get("l_femto") else "Microkeratome is lower-energy than femto."
        st.caption(f"LASIK is typically lower-emission than phaco: no CSSD, no BSS, shorter procedure. {femto_note}")

st.divider()

# ---------------------------------------------------------------------------
# Cross-pathway comparison
# ---------------------------------------------------------------------------

section("Pathway Comparison (default parameters, current pharma method)")
compare_rows = []
for pw in PATHWAYS:
    r = compute_pathway(pw["id"], {"pharma_method": pharma_method, "exchange_rate": exchange_rate})
    compare_rows.append({"Pathway": f'{pw["icon"]} {pw["label"]}', "Total (kg CO₂e)": round(r["total"], 3)})
compare_df = pd.DataFrame(compare_rows).sort_values("Total (kg CO₂e)", ascending=False)
st.dataframe(compare_df, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Reference tab (kept from the old page)
# ---------------------------------------------------------------------------

with st.expander("📚 Reference — Emission Factors & Equipment", expanded=False):
    section("Grid Emission Factor")
    row("All-India Unified Grid (CEA v21.0, FY 2024-25)", EF["grid"], "kg CO₂/kWh", note="cea.nic.in")

    st.markdown("---")
    section("Fuel EF (IPCC 2006)")
    row("Diesel", EF["diesel"], "kg CO₂e/L")

    st.markdown("---")
    section("Material EFs (Ecoinvent v3.9 proxy)")
    material_df = pd.DataFrame([
        {"Material": "Polypropylene", "kgCO₂e/kg": EF["pp"]},
        {"Material": "Polyethylene", "kgCO₂e/kg": EF["pe"]},
        {"Material": "PVC", "kgCO₂e/kg": EF["pvc"]},
        {"Material": "Nitrile rubber", "kgCO₂e/kg": EF["nitrile"]},
        {"Material": "Cotton", "kgCO₂e/kg": EF["cotton"]},
        {"Material": "Stainless steel", "kgCO₂e/kg": EF["steel"]},
        {"Material": "Glass", "kgCO₂e/kg": EF["glass"]},
        {"Material": "Paper", "kgCO₂e/kg": EF["paper"]},
        {"Material": "Silicone", "kgCO₂e/kg": EF["silicone"]},
        {"Material": "PMMA", "kgCO₂e/kg": EF["pmma"]},
    ])
    st.dataframe(material_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("Waste EFs (IPCC 2006, Vol. 5)")
    waste_df = pd.DataFrame([
        {"Stream": "Yellow (incineration)", "kgCO₂e/kg": EF["waste_yellow"]},
        {"Stream": "Red (landfill)", "kgCO₂e/kg": EF["waste_red"]},
        {"Stream": "Green (recycling)", "kgCO₂e/kg": EF["waste_green"]},
    ])
    st.dataframe(waste_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("Pharmaceutical Accounting")
    st.caption(
        "**Fixed method:** locked kgCO₂e figures derived once from an economic input-output LCA proxy "
        "(Carnegie Mellon, NAICS 325411) and hardcoded per procedure — same category as the grid EF and "
        "material EFs above. **Cost-based method:** converts a per-case pharma spend (₹) to USD using the "
        f"exchange rate, then applies {EF['pharma_usd']} kgCO₂e/USD."
    )

    st.markdown("---")
    section("LVPEI Equipment (from facility interview)")
    equip_df = pd.DataFrame([
        {"Equipment": "Slit-lamp: Zeiss BM900", "Wattage (W)": DEV["slit"], "Note": "halogen, 60 units"},
        {"Equipment": "OCT: Topcon DRI Triton", "Wattage (W)": DEV["oct"], "Note": "est., 12 pts/day"},
        {"Equipment": "Fundus: Zeiss Clarus 700", "Wattage (W)": DEV["clarus"], "Note": "est., 12 pts/day"},
        {"Equipment": "B-scan: Accutome", "Wattage (W)": DEV["bscan"], "Note": "est., 30 pts/day"},
        {"Equipment": "Phaco: Alcon Centurion", "Wattage (W)": DEV["centurion"], "Note": "active; 90W standby"},
        {"Equipment": "Microscope: Zeiss Lumera T", "Wattage (W)": DEV["lumera"], "Note": "est."},
        {"Equipment": "Chair: Surgline SESK", "Wattage (W)": DEV["chair"], "Note": "avg."},
        {"Equipment": "Anaesthesia: GE Carestation 620", "Wattage (W)": DEV["anaesth_active"], "Note": "active; 20W standby"},
        {"Equipment": "OT lighting (per room)", "Wattage (W)": DEV["ot_light"], "Note": "fluorescent panel + LEDs"},
    ])
    st.dataframe(equip_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    section("Transport EFs (for reference — used in the Tele-ophthalmology pages)")
    transport_df = pd.DataFrame([
        {"Mode": "Bus (TSRTC)", "kgCO₂e/p-km": 0.064, "Source": "TERI"},
        {"Mode": "Auto (CNG)", "kgCO₂e/p-km": 0.105, "Source": "IPCC + MoRTH"},
        {"Mode": "Two-wheeler", "kgCO₂e/p-km": 0.043, "Source": "India-specific"},
        {"Mode": "Car (petrol)", "kgCO₂e/p-km": 0.161, "Source": "MoRTH"},
    ])
    st.dataframe(transport_df, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Ophthalmology (facility-based) calculator — Shlok Marda (2024B1A40944H). "
    "Tele-ophthalmology (patient travel) calculator — Daiwik Singh (2024B1A41063H). "
    "Joint PS-I project, LVPEI, under Dr. Padmaja Kumari Rani. "
    "Reference: Thiel CL et al., JCRS 2017; 43(11):1391-1398."
)