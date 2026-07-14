import streamlit as st
import plotly.graph_objects as go

from carbon_calc import TRANSPORT_EF, compute_single_patient, DEFAULTS
from ophthalmology_calc import compute_all, DEFAULT_PARAMS

st.set_page_config(page_title="Combined Patient Journey", page_icon="🔗", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #F6F9F6; }

.page-title { font-family: 'DM Serif Display', serif; font-size: 2rem; color: #1A3A1A; margin-bottom: 0.2rem; }
.page-sub { font-size: 0.9rem; color: #5A7A5A; margin-bottom: 1.5rem; }

.step-header {
    background: #1A3A1A;
    color: white;
    border-radius: 10px;
    padding: 0.7rem 1.2rem;
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}

.result-card {
    background: white;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    text-align: center;
    height: 100%;
}
.result-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.09em; color: #8A9E8A; margin-bottom: 0.4rem; }
.result-value { font-size: 2.2rem; font-weight: 700; line-height: 1; margin-bottom: 0.3rem; }
.result-unit { font-size: 0.85rem; color: #8A9E8A; }
.result-sub { font-size: 0.8rem; color: #5A7A5A; margin-top: 0.5rem; }

.green-val { color: #2D6A2D; }
.red-val { color: #C0392B; }
.blue-val { color: #1A4D7A; }

.net-card {
    background: linear-gradient(135deg, #1A3A1A, #2D6A2D);
    border-radius: 14px;
    padding: 2rem;
    color: white;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.net-label { font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #A8D5A8; margin-bottom: 0.5rem; }
.net-value { font-size: 3rem; font-weight: 700; color: white; line-height: 1; }
.net-unit { font-size: 1rem; color: #C5E8C5; margin-top: 0.4rem; }
.net-sub { font-size: 0.85rem; color: #A8D5A8; margin-top: 0.8rem; line-height: 1.5; }

.equiv-row {
    background: white;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 0.5rem;
}
.equiv-label { font-size: 0.88rem; color: #5A7A5A; }
.equiv-value { font-size: 1rem; font-weight: 600; color: #1A3A1A; }

.caveat-box {
    background: #FFF8E1;
    border: 1px solid #FFE082;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    font-size: 0.85rem;
    color: #6D4C00;
    margin-top: 1.5rem;
    line-height: 1.65;
}
.info-box {
    background: #EEF6EE;
    border: 1px solid #C5DCC5;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    font-size: 0.85rem;
    color: #2D4A2D;
    margin-bottom: 1rem;
    line-height: 1.65;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">🔗 Combined Patient Journey</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">One patient · Teleconsultation screening → Diagnosis → Treatment · Full carbon story end to end</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
<strong>How this works:</strong> The two calculators measure different things —
<strong>Tele-ophthalmology</strong> measures CO₂ <em>avoided</em> by screening via teleconsultation instead of travelling to a city hospital,
while <strong>Ophthalmology</strong> measures CO₂ <em>emitted</em> during the actual treatment at KAR Campus.
This page combines both into a single patient journey: <strong>Net footprint = Treatment emissions − Screening savings</strong>.
A positive net number is expected and normal — treatment is the larger of the two. The savings from teleconsultation are credited against it.
</div>
""", unsafe_allow_html=True)

st.divider()

# ── STEP 1: PATIENT SCENARIO ──────────────────────────────────────────────────
st.markdown('<div class="step-header">📋 Step 1 — Define the patient scenario</div>', unsafe_allow_html=True)

col_left, col_right = st.columns([1, 2])

with col_left:
    pathway = st.radio(
        "Care pathway",
        [
            "Cataract (one-time episode)",
            "Diabetic Retinopathy / IVI (annual)",
            "Glaucoma monitoring (annual)",
            "General eye checkup (OPD only, no surgery)",
            "Teleconsultation only (no in-person follow-up)",
        ],
        key="journey_pathway",
    )
    is_cataract = pathway.startswith("Cataract")
    is_dr = pathway.startswith("Diabetic")
    is_glaucoma = pathway.startswith("Glaucoma")
    is_checkup = pathway.startswith("General eye checkup")
    is_tele_only = pathway.startswith("Teleconsultation")

with col_right:
    t1, t2 = st.columns(2)
    with t1:
        transport_mode = st.selectbox(
            "Transport mode to Vision Centre",
            list(TRANSPORT_EF.keys()),
            key="journey_transport_mode",
        )
        accompanying_persons = st.number_input(
            "Accompanying persons",
            min_value=0, value=0, step=1,
            key="journey_accompanying",
        )
    with t2:
        distance_to_vc_km = st.number_input(
            "Distance to Vision Centre (km)",
            min_value=0.0, value=float(DEFAULTS["distance_to_vc_km"]), step=1.0,
            key="journey_dist_vc",
            help="One-way distance from patient's village to GPR Vision Centre",
        )
        distance_to_alternative_km = st.number_input(
            "Distance to nearest alternative hospital (km)",
            min_value=0.0, value=float(DEFAULTS["distance_to_alternative_km"]), step=1.0,
            key="journey_dist_alt",
            help="One-way distance to the hospital the patient would have visited without telemedicine",
        )

st.divider()

# ── CALCULATIONS ──────────────────────────────────────────────────────────────
screening = compute_single_patient(
    transport_mode, accompanying_persons, distance_to_vc_km, distance_to_alternative_km
)
screening_saved = screening["CO2_saved_kg"]

oph_params = {k: st.session_state.get(f"oph_{k}", v) for k, v in DEFAULT_PARAMS.items()}
oph_results = compute_all(oph_params)

if is_cataract:
    treatment_emissions = oph_results["cataract_episode"]
    treatment_label = "cataract surgery episode (5 visits)"
elif is_dr:
    treatment_emissions = oph_results["dr_episode_year"]
    treatment_label = f'DR/IVI care ({oph_params["ivi_visits_yr"]:.0f} visits/year)'
elif is_glaucoma:
    treatment_emissions = oph_results["glaucoma_episode_year"]
    treatment_label = f'glaucoma monitoring ({oph_params["glaucoma_visits_yr"]:.0f} visits/year + topical medication)'
elif is_checkup:
    treatment_emissions = oph_results["opd_only_episode"]
    treatment_label = "general OPD checkup (slit lamp + autorefractor + NCT, no surgery)"
else:  # is_tele_only
    treatment_emissions = 0.0
    treatment_label = "no in-person visit — screening only"

net = treatment_emissions - screening_saved

# ── STEP 2: RESULTS ───────────────────────────────────────────────────────────
st.markdown('<div class="step-header">📊 Step 2 — Carbon results</div>', unsafe_allow_html=True)

r1, r2, r3 = st.columns([1, 1, 1])

with r1:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">🚗 Teleconsultation Screening</div>
        <div class="result-value green-val">{screening_saved:+.2f}</div>
        <div class="result-unit">kg CO₂e</div>
        <div class="result-sub">CO₂ <strong>saved</strong> vs. patient travelling to<br>the alternative hospital ({distance_to_alternative_km:.0f} km away)</div>
    </div>
    """, unsafe_allow_html=True)

with r2:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">🏥 Treatment at LVPEI</div>
        <div class="result-value red-val">{treatment_emissions:.2f}</div>
        <div class="result-unit">kg CO₂e</div>
        <div class="result-sub">CO₂ <strong>emitted</strong> by {treatment_label}</div>
    </div>
    """, unsafe_allow_html=True)

with r3:
    net_label = "Net carbon cost" if net > 0 else "Net carbon saving"
    net_color = "red-val" if net > 0 else "green-val"
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">🔗 Full Journey Net</div>
        <div class="result-value {net_color}">{net:+.2f}</div>
        <div class="result-unit">kg CO₂e</div>
        <div class="result-sub">{net_label}<br>Treatment − Screening savings</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── WATERFALL CHART ───────────────────────────────────────────────────────────
st.markdown("**Full journey breakdown**")

screening_travel_counterfactual = screening["E_counterfactual_kg"]
screening_travel_vc = screening["E_travel_to_vc_kg"]
from carbon_calc import E_DEVICE_KGCO2, E_DIGITAL_KGCO2

fig = go.Figure(go.Waterfall(
    name="Carbon journey",
    orientation="v",
    measure=["absolute", "relative", "relative", "relative", "total", "relative", "total"],
    x=[
        "Counterfactual<br>travel",
        "Avoided: travel<br>to VC",
        "Scope 2:<br>device electricity",
        "Scope 3:<br>DICOM overhead",
        "Net screening<br>saving",
        "Treatment<br>emissions",
        "Full journey<br>net footprint",
    ],
    y=[
        screening_travel_counterfactual,
        -(screening_travel_vc + E_DEVICE_KGCO2 + E_DIGITAL_KGCO2),
        0, 0,
        0,
        treatment_emissions,
        0,
    ],
    text=[
        f"{screening_travel_counterfactual:.2f}",
        f"−{(screening_travel_vc + E_DEVICE_KGCO2 + E_DIGITAL_KGCO2):.2f}",
        f"{E_DEVICE_KGCO2:.3f}",
        f"{E_DIGITAL_KGCO2:.4f}",
        f"{screening_saved:.2f}",
        f"+{treatment_emissions:.2f}",
        f"{net:.2f}",
    ],
    textposition="outside",
    connector={"line": {"color": "#C5DCC5", "width": 1}},
    increasing={"marker": {"color": "#C0392B"}},
    decreasing={"marker": {"color": "#2D6A2D"}},
    totals={"marker": {"color": "#1A4D7A"}},
))

fig.update_layout(
    plot_bgcolor="white", paper_bgcolor="white",
    font_family="Inter", font_size=12,
    margin=dict(t=20, b=20, l=0, r=0),
    yaxis_title="kgCO₂e", yaxis=dict(gridcolor="#F0F4F0"),
    showlegend=False, height=420,
)
st.plotly_chart(fig, use_container_width=True)

# ── RELATIVE SCALE BARS ───────────────────────────────────────────────────────
st.markdown("**Relative scale: screening savings vs. treatment emissions**")
max_val = max(abs(screening_saved), treatment_emissions, 0.001)

b1, b2 = st.columns(2)
with b1:
    pct = min(abs(screening_saved) / max_val, 1.0)
    st.caption(f"🟢 CO₂ saved via teleconsultation — **{screening_saved:.2f} kg**")
    st.progress(pct)
with b2:
    pct2 = min(treatment_emissions / max_val, 1.0)
    st.caption(f"🔴 CO₂ emitted during treatment — **{treatment_emissions:.2f} kg**")
    st.progress(pct2)

if treatment_emissions == 0:
    if screening_saved > 0:
        st.info(f"No in-person treatment in this scenario — the full **{screening_saved:.2f} kg CO₂e** is a pure saving from teleconsultation, nothing to offset it against.")
    else:
        st.warning("Screening savings are zero or negative — the patient lives closer to the alternative hospital than to the Vision Centre. Adjust the distances above.")
elif screening_saved > 0:
    ratio = treatment_emissions / screening_saved
    st.info(f"Treatment emissions are **{ratio:.1f}×** the teleconsultation screening savings for this scenario. The net journey still has a carbon cost, but teleconsultation screening reduced it by **{(screening_saved / treatment_emissions * 100):.1f}%**.")
else:
    st.warning("Screening savings are zero or negative — the patient lives closer to the alternative hospital than to the Vision Centre. Adjust the distances above.")

st.markdown("<br>", unsafe_allow_html=True)

# ── NET SUMMARY CARD ──────────────────────────────────────────────────────────
TREE_KG = 21.0
CAR_KM_KG = 0.17
FLIGHT_KG = 130.0

ec1, ec2 = st.columns([1, 2])
with ec1:
    st.markdown(f"""
    <div class="net-card">
        <div class="net-label">Full Patient Journey · Net Carbon Footprint</div>
        <div class="net-value">{net:.2f}</div>
        <div class="net-unit">kg CO₂e</div>
        <div class="net-sub">
            {treatment_label.capitalize()}<br>
            after crediting teleconsultation screening savings
        </div>
    </div>
    """, unsafe_allow_html=True)

with ec2:
    st.markdown("**The net footprint in context**")
    savings_trees = abs(screening_saved) / TREE_KG
    savings_km = abs(screening_saved) / CAR_KM_KG
    net_trees = abs(net) / TREE_KG
    net_km = abs(net) / CAR_KM_KG
    net_flights = abs(net) / FLIGHT_KG

    st.markdown(f"""
    <div class="equiv-row">
        <span class="equiv-label">🌿 Screening saved the equivalent of</span>
        <span class="equiv-value">{savings_trees:.2f} trees/year &nbsp;|&nbsp; {savings_km:.0f} car km</span>
    </div>
    <div class="equiv-row">
        <span class="equiv-label">🏥 Net journey footprint equals</span>
        <span class="equiv-value">{net_trees:.2f} trees/year &nbsp;|&nbsp; {net_km:.0f} car km &nbsp;|&nbsp; {net_flights:.2f} flights</span>
    </div>
    <div class="equiv-row">
        <span class="equiv-label">📉 Teleconsultation reduced the treatment footprint by</span>
        <span class="equiv-value">{(f"{(screening_saved / treatment_emissions * 100):.1f}%" if treatment_emissions > 0 else "n/a — no treatment visit in this scenario")}</span>
    </div>
    """, unsafe_allow_html=True)

# ── CAVEAT ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="caveat-box">
<strong>⚠️ Accounting note:</strong> In standard GHG Protocol reporting, avoided emissions (Scope 3 teleconsultation savings)
and actual facility emissions (Scope 1/2/3 treatment) are reported separately — not netted against each other.
The combined number on this page is a <em>patient journey framing</em> built for presentation and communication purposes,
not a substitute for the separate Scope 1/2/3 inventory. Both calculators individually remain GHG Protocol compliant.
The ophthalmology parameters (phaco duration, CSSD load, etc.) can be adjusted on the <strong>Ophthalmology Calculator</strong>
page — this page picks them up automatically.
</div>
""", unsafe_allow_html=True)

st.divider()
st.caption(
    "Combined Patient Journey · Tele-ophthalmology: Daiwik Singh (2024B1A41063H) · "
    "Ophthalmology: Shlok Marda (2024B1A40944H) · "
    "Joint PS-I project, LVPEI, under Dr. Padmaja Kumari Rani · BITS Pilani Hyderabad 2025–26"
)