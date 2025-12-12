import streamlit as st
from sharkbite_engine.utils import (
    SPECIFIC_YIELD_RULE_OF_THUMB,
    TOOLTIPS,
    ELIGIBILITY_CHECKS_UNIFIED_INTAKE,
    generate_progress_bar_markdown
)

# ---- Screen Flow Map for User Journey (progress bar) ----
SCREEN_FLOW_MAP_NEW = {
    'unified_intake': (1, "Unified Intake"),
    'solar_battery_calculator': (2, "Solar & Battery Calculator"),
    'incentive_preview': (3, "Incentive Preview"),
    'reap_deep_dive': (4, "REAP Deep Dive"),
    'multi_grant_stacker': (5, "Multi-Grant Stacker"),
    'final_incentive_dashboard': (6, "Financial Dashboard"), # Adapting old S7
    'export_package': (7, "Export Package")
}


def display_unified_intake_screen():
    st.title("Let's Start Sizing!")
    st.markdown("**Enter basic property and energy usage information to begin.**")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'unified_intake')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data

    # These are stored in `st.session_state.form_data` for use by subsequent screens
    form_data["unified_address_zip"] = st.text_input( # Changed key for clarity
        "📍 Property Address or ZIP Code",
        value=form_data.get("unified_address_zip", ""),
        key="s1_unified_address_zip",
        help=TOOLTIPS.get("address_zip")
    )
    
    zip_val_for_hint = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    zip_hint = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_val_for_hint, ELIGIBILITY_CHECKS_UNIFIED_INTAKE["default"])
    if zip_hint["type"] == "success":
        st.success(zip_hint["text"], icon="✅")
    else:
        st.info(zip_hint["text"], icon="💡")

    # Business Type from the new screen flow -- maps to `user_type` input
    biz_type_options = ["Homeowner", "Commercial / Business", "Farm / Agriculture", "Nonprofit", "Tribal Entity", "Rural Cooperative"]
    current_biz_type = form_data.get("unified_business_type", biz_type_options[0])
    form_data["unified_business_type"] = st.selectbox(
        "👤 Primary User / Business Type",
        options=biz_type_options,
        index=biz_type_options.index(current_biz_type) if current_biz_type in biz_type_options else 0,
        key="s1_unified_biz_type",
        help=TOOLTIPS.get("unified_business_type")
    )

    st.subheader("⚡ Your Current Energy Profile")
    col1, col2 = st.columns(2)
    with col1:
        form_data["unified_monthly_kwh"] = st.number_input(
            "Avg. Monthly Electricity Usage (kWh)",
            min_value=0,
            value=form_data.get("unified_monthly_kwh", 1000),
            step=50,
            key="s1_unified_monthly_kwh",
            help=TOOLTIPS.get("unified_monthly_kwh")
        )
        
    with col2:
        form_data["unified_electricity_rate"] = st.number_input(
            "Current Electricity Rate ($/kWh)",
            min_value=0.0,
            value=form_data.get("unified_electricity_rate", 0.15), step=0.01, format="%.2f",
            key="s1_unified_elec_rate",
            help=TOOLTIPS.get("unified_electricity_rate")
        )
    
    form_data["avg_monthly_bill"] = st.number_input(
        "Avg. Monthly Electric Bill ($)",
        min_value=0,
        value=form_data.get("avg_monthly_bill", 250),
        key="s1_avg_bill")  # <--- NEWLY ADDED

    # --- ESTIMATES USAGE & SUGGEST SIZE ---
    avg_monthly_bill = form_data["avg_monthly_bill"]
    electricity_rate = form_data["unified_electricity_rate"]

    if electricity_rate > 0:
        annual_kwh_est = (avg_monthly_bill * 12) / electricity_rate
        form_data["annual_kwh_est"] = annual_kwh_est   # Store for later
        st.info(f"Based on your bill and rate, your estimated annual usage is **{annual_kwh_est:,.0f} kWh**.", icon="💡")
        
        target_offset = st.slider("Desired Annual Bill Offset (%)", 50, 110, 95, key="s1_target_offset",
                                  help="What percentage of your usage do you want the solar system to cover?")
        form_data["target_offset"] = target_offset
        
        target_kwh = annual_kwh_est * (target_offset / 100.0)
        suggested_kw = round(target_kwh / SPECIFIC_YIELD_RULE_OF_THUMB, 1)
        form_data["calculator_initial_autosized_kw"] = suggested_kw
        
        st.success(f"To offset {target_offset}% of your usage, a system size of approximately **{suggested_kw:.1f} kW** is recommended.", icon="📐")


    # --- UI Element for Self-Consumption Priority ---
    st.subheader("Project Optimization Goal")
    user_type = form_data.get("unified_business_type", "Homeowner")
    
    # Default to True for commercial/ag, False for residential
    default_self_consumption = user_type in ["Commercial / Business", "Farm / Agriculture", "Rural Cooperative"]
    
    form_data["self_consumption_priority"] = st.toggle(
        "Optimize for Self-Consumption (Minimize Grid Export)?",
        value=form_data.get("self_consumption_priority",
        default_self_consumption),
        key="s1_self_consumption_toggle",
        help=TOOLTIPS.get("self_consumption_priority"),
    )
    if form_data["self_consumption_priority"]:
        st.info("💡 **Self-Consumption Mode:** The system will be sized to maximize on-site energy use, and savings will primarily come from avoiding grid purchases.", icon="🔋")
    else:
        st.info("💡 **Bill Offset Mode:** The system will be sized to offset a percentage of your annual bill, which may involve more grid export.", icon="💸")
    
    
    st.markdown("---")
    if st.button("Continue to Solar & Battery Calculator ➡️", type="primary", use_container_width=True, key="s1_to_s2_continue"):
        # Store necessary pre-filled values for calculator screen based on unified intake
        form_data["calculator_address_from_s1"] = form_data.get("unified_address_zip")
        form_data["calculator_user_type_from_s1"] = form_data.get("unified_business_type")
        form_data["calculator_monthly_kwh_from_s1"] = form_data.get("unified_monthly_kwh")
        form_data["calculator_elec_rate_from_s1"] = form_data.get("unified_electricity_rate")
        return True # Signals the sharkbite_app to navigate
    return False