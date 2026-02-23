import streamlit as st
import numpy as np
import pandas as pd
import os
from CoolProp.CoolProp import PropsSI
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import pagesizes
from io import BytesIO
from datetime import datetime

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="Hydrogen Gas Cooler Tool", layout="wide")

st.title("🔵 Hydrogen Gas Cooler Design Tool")
st.markdown("Electrolyzer Balance of Plant | Preliminary Engineering Tool")
st.markdown("Developed by **Gaurav Tomar**")

st.markdown("---")

# ==============================
# INPUT SECTION
# ==============================

st.header("🔹 Hydrogen Process Inputs")

col1, col2 = st.columns(2)

with col1:
    flow_hot_nm3_hr = st.number_input(
        "Hydrogen Flow (Nm³/hr)",
        value=750.000,
        step=1.000,
        format="%.3f"
    )
    T_hot_in_C = st.number_input(
        "Hydrogen Inlet Temp (°C)",
        value=80.000,
        format="%.3f"
    )
    T_hot_out_C = st.number_input(
        "Hydrogen Outlet Temp (°C)",
        value=40.000,
        format="%.3f"
    )
    P_hot_bar = st.number_input(
        "Hydrogen Pressure (bar)",
        value=16.000,
        format="%.3f"
    )

with col2:
    T_cold_in_C = st.number_input(
        "Cooling Water Inlet Temp (°C)",
        value=35.000,
        format="%.3f"
    )
    T_cold_out_C = st.number_input(
        "Cooling Water Outlet Temp (°C)",
        value=40.000,
        format="%.3f"
    )
    P_cold_bar = st.number_input(
        "Cooling Water Pressure (bar)",
        value=3.000,
        format="%.3f"
    )

auto_water = st.checkbox("Auto Calculate Cooling Water Flow", True)

if not auto_water:
    m_dot_cold = st.number_input(
        "Cooling Water Flow (kg/s)",
        value=7.000,
        format="%.3f"
    )

st.header("🔹 Mechanical Inputs")

D_i = st.number_input(
    "Tube Inner Diameter (m)",
    value=0.025,
    step=0.001,
    format="%.3f"
)

t_wall = st.number_input(
    "Tube Wall Thickness (m)",
    value=0.0020,
    step=0.0001,
    format="%.4f"
)

velocity_target = st.number_input(
    "Design Tube Velocity (m/s)",
    value=9.000,
    format="%.3f"
)

passes = st.selectbox("Number of Tube Passes", [1, 2, 4])

# ==============================
# CALCULATION SECTION
# ==============================

if st.button("Run Hydrogen Cooler Design"):

    try:

        # Unit conversion
        T_hot_in = T_hot_in_C + 273.15
        T_hot_out = T_hot_out_C + 273.15
        T_cold_in = T_cold_in_C + 273.15
        T_cold_out = T_cold_out_C + 273.15

        P_hot = P_hot_bar * 1e5
        P_cold = P_cold_bar * 1e5
        flow_hot_m3_s = flow_hot_nm3_hr / 3600

        # Hydrogen properties
        rho_h = PropsSI('D','T',T_hot_in,'P',P_hot,'Hydrogen')
        Cp_h = PropsSI('C','T',T_hot_in,'P',P_hot,'Hydrogen')
        mu_h = PropsSI('V','T',T_hot_in,'P',P_hot,'Hydrogen')
        k_h = PropsSI('L','T',T_hot_in,'P',P_hot,'Hydrogen')
        Pr_h = PropsSI('PRANDTL','T',T_hot_in,'P',P_hot,'Hydrogen')

        m_dot_h = rho_h * flow_hot_m3_s
        Q = m_dot_h * Cp_h * (T_hot_in - T_hot_out)

        # Auto water calculation
        if auto_water:
            Cp_water = PropsSI('C','T',T_cold_in,'P',P_cold,'Water')
            m_dot_cold = Q / (Cp_water * (T_cold_out - T_cold_in))

        # Tube design
        A_single = np.pi * D_i**2 / 4
        N_per_pass = int(np.ceil(m_dot_h / (rho_h * velocity_target * A_single)))
        N_total = N_per_pass * passes
        velocity = m_dot_h / (rho_h * N_per_pass * A_single)

        # Heat transfer coefficients
        Re_h = rho_h * velocity * D_i / mu_h
        Nu_h = 0.023 * Re_h**0.8 * Pr_h**0.4
        h_hot = Nu_h * k_h / D_i

        h_shell = 3000  # Simplified realistic shell-side estimate

        Rf_i = 0.0001
        Rf_o = 0.0002
        k_tube = 16

        U = 1 / (1/h_hot + Rf_i + t_wall/k_tube + 1/h_shell + Rf_o)

        # LMTD
        deltaT1 = T_hot_in - T_cold_out
        deltaT2 = T_hot_out - T_cold_in
        LMTD = (deltaT1 - deltaT2) / np.log(deltaT1/deltaT2)

        F = 1 if passes == 1 else 0.85
        A_required = Q/(U*F*LMTD)

        D_o = D_i + 2*t_wall
        K = 0.9
        D_shell = D_o * np.sqrt(N_total/(0.785*K))

        # ==============================
        # DISPLAY RESULTS
        # ==============================

        st.header("📊 Design Results")

        st.write(f"Heat Duty: **{Q/1000:.2f} kW**")
        st.write(f"Cooling Water Flow: **{m_dot_cold:.2f} kg/s**")
        st.write(f"Overall U: **{U:.1f} W/m²-K**")
        st.write(f"Required Area: **{A_required:.2f} m²**")
        st.write(f"Total Tubes: **{N_total}**")
        st.write(f"Shell Diameter: **{D_shell:.2f} m**")
        st.write(f"Tube Velocity: **{velocity:.2f} m/s**")

        # ==============================
        # PDF GENERATION
        # ==============================

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=pagesizes.A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("Hydrogen Gas Cooler Design Datasheet", styles["Heading1"]))
        elements.append(Spacer(1, 0.3 * inch))

        table_data = [
            ["Parameter", "Value"],
            ["Hydrogen Flow (Nm3/hr)", flow_hot_nm3_hr],
            ["Heat Duty (kW)", f"{Q/1000:.2f}"],
            ["Cooling Water Flow (kg/s)", f"{m_dot_cold:.2f}"],
            ["Overall U (W/m2-K)", f"{U:.1f}"],
            ["Required Area (m2)", f"{A_required:.2f}"],
            ["Total Tubes", N_total],
            ["Shell Diameter (m)", f"{D_shell:.2f}"],
        ]

        table = Table(table_data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('GRID',(0,0),(-1,-1),0.5,colors.black)
        ]))

        elements.append(table)
        doc.build(elements)

        pdf = buffer.getvalue()
        buffer.close()

        st.download_button(
            "📥 Download Design Datasheet (PDF)",
            pdf,
            "Hydrogen_Gas_Cooler_Datasheet.pdf",
            "application/pdf"
        )

    except Exception as e:
        st.error("Calculation Error")
        st.write(e)

# ==============================
# FEEDBACK SECTION
# ==============================

st.markdown("---")
st.header("📝 Feedback & Suggestions")

st.markdown(
    """
    <a href="https://www.linkedin.com/in/gaurav-tomar-739257152" target="_blank">
        <button style="
            background-color:#0077B5;
            color:white;
            padding:10px 20px;
            border:none;
            border-radius:6px;
            font-size:16px;
            cursor:pointer;">
            Follow Gaurav Tomar on LinkedIn
        </button>
    </a>
    """,
    unsafe_allow_html=True
)

name = st.text_input("Your Name")
feedback_text = st.text_area("Your Feedback")

if st.button("Submit Feedback"):
    if name and feedback_text:
        feedback_data = {
            "Timestamp": datetime.now(),
            "Name": name,
            "Feedback": feedback_text
        }

        file_exists = os.path.isfile("feedback.csv")
        df = pd.DataFrame([feedback_data])

        if file_exists:
            df.to_csv("feedback.csv", mode='a', header=False, index=False)
        else:
            df.to_csv("feedback.csv", index=False)

        st.success("Thank you for your feedback!")

if os.path.isfile("feedback.csv"):
    st.subheader("📢 Visitor Feedback")
    feedback_df = pd.read_csv("feedback.csv")
    st.dataframe(feedback_df)