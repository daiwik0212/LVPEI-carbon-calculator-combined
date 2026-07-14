import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from carbon_calc import (
    TRANSPORT_EF, TREE_ABSORPTION_KGCO2_PER_YEAR, CAR_KM_EQUIV_KGCO2_PER_KM,
    FLIGHT_EQUIV_KGCO2, GRID_EF_KGCO2_PER_KWH, TRIAGE_BENCHMARK, EXPECTED_COLUMNS,
    DEFAULTS, generate_dummy_data, validate_and_fill_defaults,
)
import numpy as np_

st.set_page_config(page_title="Tele-ophthalmology Calculator", page_icon="📡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.page-title { font-family: 'DM Serif Display', serif; font-size: 2rem; color: #1A3A1A; margin-bottom:0.2rem; }
.page-sub { font-size: 0.9rem; color: #5A7A5A; margin-bottom: 1.5rem; }
.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 1.3rem 1.5rem;
    border-left: 4px solid #2D6A2D;
    box-shadow: 0 1px 5px rgba(0,0,0,0.06);
}
.kpi-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.09em; color: #5A7A5A; margin-bottom: 0.25rem; }
.kpi-value { font-size: 2rem; font-weight: 700; color: #1A3A1A; line-height: 1; }
.kpi-unit { font-size: 0.82rem; color: #8A9E8A; margin-top: 0.2rem; }
.section-title { font-family: 'DM Serif Display', serif; font-size: 1.25rem; color: #1A3A1A; margin: 1.2rem 0 0.4rem; }
.warn-box { background: #FFF8E1; border: 1px solid #FFE082; border-radius: 10px; padding: 0.9rem 1.2rem; font-size: 0.85rem; color: #6D4C00; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">📡 Tele-ophthalmology Carbon Calculator</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Per-patient CO₂ savings from teleconsultation screening at GPR Vision Centre, Kismathpur · GHG Protocol Scope 1/2/3 · Rani et al. 2024</div>', unsafe_allow_html=True)

# ── DATA SOURCE ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Data source")
    use_demo = st.radio("", ["Demo data (50 patients)", "Upload eyeSmart CSV"], index=0, label_visibility="collapsed")

if use_demo == "Upload eyeSmart CSV":
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        raw_df = pd.read_csv(uploaded)
        data_label = f"📄 {uploaded.name}"
    else:
        st.sidebar.info("Awaiting upload — showing demo data.")
        raw_df = generate_dummy_data()
        data_label = "Demo data (50 simulated patients)"
else:
    raw_df = generate_dummy_data()
    data_label = "Demo data (50 simulated patients)"

# ── ADJUSTABLE PARAMETERS ─────────────────────────────────────────────────────
with st.expander("⚙️ Adjustable Parameters", expanded=False):
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("**Session & devices**")
        session_min = st.number_input("Session duration (min)", min_value=1.0, max_value=60.0, value=10.0, step=1.0, key="tele_session_min")
        fundus_w = st.number_input("Fundus camera wattage (W)", min_value=0, value=45, step=5, key="tele_fundus_w")
        slit_w = st.number_input("Slit lamp wattage (W)", min_value=0, value=25, step=5, key="tele_slit_w")
    with p2:
        st.markdown("**Infrastructure**")
        workstation_w = st.number_input("Workstation + monitor (W)", min_value=0, value=120, step=10, key="tele_workstation_w")
        router_w = st.number_input("Router/networking (W)", min_value=0, value=15, step=5, key="tele_router_w")
        dicom_mb = st.number_input("DICOM file size per consult (MB)", min_value=0.1, value=5.0, step=0.5, key="tele_dicom_mb")
    with p3:
        st.markdown("**Grid & data**")
        grid_ef = st.number_input("Grid emission factor (kgCO₂/kWh)", min_value=0.0, value=0.7117, step=0.01, format="%.4f", key="tele_grid_ef",
                                   help="CEA v21.0 FY2024-25: 0.7117. Change to test renewable scenarios.")
        network_ef = st.number_input("Network energy intensity (kWh/GB)", min_value=0.0, value=0.06, step=0.01, format="%.3f", key="tele_network_ef")
        default_dist_vc = st.number_input("Default dist. to VC if missing (km)", min_value=1.0, value=15.0, step=1.0, key="tele_default_vc")
        default_dist_alt = st.number_input("Default dist. to alternative if missing (km)", min_value=1.0, value=80.0, step=5.0, key="tele_default_alt")

# ── DERIVED VALUES FROM PARAMS ────────────────────────────────────────────────
total_device_w = fundus_w + slit_w + workstation_w + router_w
e_device = (total_device_w * session_min / 60_000) * grid_ef
e_digital = (dicom_mb / 1024) * network_ef * grid_ef

# ── COMPUTE (inline, using adjustable params) ─────────────────────────────────
clean_df, missing_cols, rows_defaulted = validate_and_fill_defaults(raw_df)

# Override defaults with adjustable params
clean_df["distance_to_vc_km"] = clean_df["distance_to_vc_km"].fillna(default_dist_vc)
clean_df["distance_to_alternative_km"] = clean_df["distance_to_alternative_km"].fillna(default_dist_alt)

df = clean_df.copy()
modal_ef = df["transport_mode"].map(TRANSPORT_EF).fillna(TRANSPORT_EF["Bus"])
multiplier = 1 + df["accompanying_persons"]

df["E_counterfactual_kg"] = df["distance_to_alternative_km"] * 2 * modal_ef * multiplier
df["E_travel_to_vc_kg"]   = df["distance_to_vc_km"] * 2 * modal_ef * multiplier
df["E_device_kg"]         = e_device
df["E_digital_kg"]        = e_digital
df["E_teleconsultation_kg"] = df["E_travel_to_vc_kg"] + e_device + e_digital
df["CO2_saved_kg"]        = df["E_counterfactual_kg"] - df["E_teleconsultation_kg"]
df["trees_equivalent"]    = df["CO2_saved_kg"] / TREE_ABSORPTION_KGCO2_PER_YEAR
df["is_negative"]         = df["CO2_saved_kg"] < 0

# Aggregates
total_co2_kg     = df["CO2_saved_kg"].sum()
total_co2_t      = total_co2_kg / 1000
total_trees      = total_co2_kg / TREE_ABSORPTION_KGCO2_PER_YEAR
total_car_km     = total_co2_kg / CAR_KM_EQUIV_KGCO2_PER_KM
total_flights    = total_co2_kg / FLIGHT_EQUIV_KGCO2
avg_co2          = df["CO2_saved_kg"].mean()
negative_count   = int(df["is_negative"].sum())
total_consults   = len(df)

triage_summary = df.groupby("triage_outcome").agg(
    patients=("CO2_saved_kg", "count"),
    co2_saved_kg=("CO2_saved_kg", "sum")
).reindex(["Green", "Yellow", "Red"]).fillna(0).reset_index()

if missing_cols:
    st.markdown(f'<div class="warn-box">⚠️ Columns not found and filled with defaults: <strong>{", ".join(missing_cols)}</strong>. {rows_defaulted} row(s) used fallback values.</div>', unsafe_allow_html=True)

st.caption(f"Data: {data_label} · {total_consults} consultations · Grid EF: {grid_ef:.4f} kgCO₂/kWh · Device load: {total_device_w}W · Session: {session_min:.0f} min")

# ── KPI CARDS ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Total CO₂ Saved</div><div class="kpi-value">{total_co2_t:.2f}</div><div class="kpi-unit">tonnes CO₂e</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Trees Equivalent</div><div class="kpi-value">{total_trees:.0f}</div><div class="kpi-unit">trees absorbing CO₂ for 1 year</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Car Travel Avoided</div><div class="kpi-value">{total_car_km:,.0f}</div><div class="kpi-unit">km equivalent</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">Flights Avoided</div><div class="kpi-value">{total_flights:.1f}</div><div class="kpi-unit">Delhi–Hyderabad equivalent</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total consultations", f"{total_consults:,}")
m2.metric("Avg CO₂ saved / patient", f"{avg_co2:.2f} kg")
m3.metric("E_device per patient", f"{e_device:.4f} kg", f"{total_device_w}W × {session_min:.0f} min")
m4.metric("Edge cases (negative ΔE)", str(negative_count) + (" ⚠️" if negative_count > 0 else " ✓"))

st.markdown("<br>", unsafe_allow_html=True)

# ── CHARTS ────────────────────────────────────────────────────────────────────
COLORS = {"Green": "#2D6A2D", "Yellow": "#E6A817", "Red": "#C0392B"}

ch1, ch2 = st.columns(2)

with ch1:
    st.markdown('<div class="section-title">CO₂ Saved by Triage Category</div>', unsafe_allow_html=True)
    fig = px.bar(
        triage_summary, x="triage_outcome", y="co2_saved_kg",
        color="triage_outcome", color_discrete_map=COLORS,
        text=triage_summary["co2_saved_kg"].apply(lambda x: f"{x:.1f} kg"),
        labels={"co2_saved_kg": "CO₂ Saved (kg)", "triage_outcome": ""},
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(
        showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
        font_family="Inter", margin=dict(t=10, b=10, l=0, r=0),
        yaxis_title="CO₂ Saved (kgCO₂e)", yaxis=dict(gridcolor="#F0F4F0"),
    )
    st.plotly_chart(fig, use_container_width=True)

with ch2:
    st.markdown('<div class="section-title">Emission Breakdown (Per-Patient Average)</div>', unsafe_allow_html=True)
    avg_cf = df["E_counterfactual_kg"].mean()
    avg_tv = df["E_travel_to_vc_kg"].mean()
    labels = ["Counterfactual\n(without tele)", "Travel to\nVision Centre", "Device\nelectricity", "Digital\noverhead"]
    values = [avg_cf, avg_tv, e_device, e_digital]
    bar_colors = ["#C0392B", "#E6A817", "#5A7A5A", "#C5DCC5"]
    fig2 = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=bar_colors,
        text=[f"{v:.3f} kg" for v in values],
        textposition="outside",
    ))
    fig2.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", font_family="Inter",
        margin=dict(t=10, b=10, l=0, r=0), showlegend=False,
        yaxis_title="kgCO₂e (avg per patient)", yaxis=dict(gridcolor="#F0F4F0"),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown('<div class="section-title">Transport Mode Distribution</div>', unsafe_allow_html=True)
mode_df = df.groupby("transport_mode").agg(
    patients=("CO2_saved_kg", "count"),
    avg_saving=("CO2_saved_kg", "mean"),
).reset_index().sort_values("patients", ascending=False)
fig3 = px.bar(
    mode_df, x="transport_mode", y="patients",
    color="avg_saving", color_continuous_scale=["#C5DCC5", "#1A3A1A"],
    text="patients",
    labels={"patients": "No. of Patients", "transport_mode": "Mode", "avg_saving": "Avg CO₂ Saved (kg)"},
)
fig3.update_traces(textposition="outside", marker_line_width=0)
fig3.update_layout(
    plot_bgcolor="white", paper_bgcolor="white", font_family="Inter",
    margin=dict(t=10, b=10, l=0, r=0),
    yaxis=dict(gridcolor="#F0F4F0"),
    coloraxis_colorbar=dict(title="Avg CO₂<br>Saved (kg)", thickness=14),
)
st.plotly_chart(fig3, use_container_width=True)

# ── PER-PATIENT TABLE ─────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Per-Patient Detail</div>', unsafe_allow_html=True)

fa, fb, fc = st.columns(3)
with fa:
    triage_filter = st.multiselect("Triage", ["Green", "Yellow", "Red"], default=["Green", "Yellow", "Red"])
with fb:
    mode_filter = st.multiselect("Transport mode", list(TRANSPORT_EF.keys()), default=list(TRANSPORT_EF.keys()))
with fc:
    show_neg = st.checkbox("Edge cases only (ΔE < 0)")

disp = df[df["triage_outcome"].isin(triage_filter) & df["transport_mode"].isin(mode_filter)]
if show_neg:
    disp = disp[disp["is_negative"]]

table = disp[[
    "patient_id", "consultation_date", "triage_outcome", "transport_mode",
    "distance_to_vc_km", "distance_to_alternative_km",
    "E_counterfactual_kg", "E_teleconsultation_kg", "CO2_saved_kg", "trees_equivalent",
]].copy()
table.columns = [
    "Patient ID", "Date", "Triage", "Transport",
    "Dist. to VC (km)", "Dist. to Alt. (km)",
    "Counterfactual CO₂ (kg)", "Teleconsult CO₂ (kg)", "ΔE Saved (kg)", "Trees Equiv.",
]
for col in ["Counterfactual CO₂ (kg)", "Teleconsult CO₂ (kg)", "ΔE Saved (kg)", "Trees Equiv."]:
    table[col] = table[col].round(3)

st.dataframe(table, use_container_width=True, height=400, hide_index=True)

if disp["is_negative"].any():
    st.markdown(f'<div class="warn-box">⚠️ {disp["is_negative"].sum()} patient(s) show negative ΔE — their distance to the alternative facility was shorter than their distance to GPR. These are edge cases.</div>', unsafe_allow_html=True)

csv_out = table.to_csv(index=False)
st.download_button("⬇️ Download results CSV", csv_out, "LVPEI_GPR_carbon_savings.csv", "text/csv")

with st.expander("📋 Current assumptions summary"):
    st.markdown(f"""
    | Parameter | Value | Source |
    |---|---|---|
    | Grid emission factor | {grid_ef:.4f} kgCO₂/kWh | CEA v21.0 FY2024-25 (adjustable) |
    | Session duration | {session_min:.0f} min | Dr. Rani 5–15 min range (adjustable) |
    | Total device load | {total_device_w}W | {fundus_w}W fundus + {slit_w}W slit + {workstation_w}W workstation + {router_w}W router |
    | E_device per patient | {e_device:.5f} kgCO₂ | Scope 2 |
    | DICOM size | {dicom_mb} MB | Standard fundus photo (adjustable) |
    | E_digital per patient | {e_digital:.6f} kgCO₂ | Scope 3 — negligible |
    | Default dist. to VC | {default_dist_vc:.0f} km | GPR catchment estimate (adjustable) |
    | Default dist. to alt. | {default_dist_alt:.0f} km | Rani et al. primary band (adjustable) |
    | Tree absorption | {TREE_ABSORPTION_KGCO2_PER_YEAR} kgCO₂/year | Literature standard |
    """)

st.divider()
st.caption("Tele-ophthalmology carbon calculator · Daiwik Singh (2024B1A41063H) · BITS Pilani Hyderabad · Supervisor: Dr. Padmaja Kumari Rani, LVPEI · PS-I 2025–26")