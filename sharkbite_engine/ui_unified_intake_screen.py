import streamlit as st
from sharkbite_engine.utils import (
    AI_HELPER_TEXTS_UNIFIED_INTAKE, ELIGIBILITY_CHECKS_UNIFIED_INTAKE,
    generate_progress_bar_markdown
)
from sharkbite_engine.solar_calculator_logic import calculate_solar_system_size_from_usage


# ---- Screen Flow Map for progress bar ----
SCREEN_FLOW_MAP_NEW = {
    'unified_intake': (1, "Unified Intake"),
    'solar_battery_calculator': (2, "Solar & Battery Calculator"),
    'incentive_preview': (3, "Incentive Preview"),
    'reap_deep_dive_documents': (4, "REAP Deep Dive & Docs"), # Adapting old S4
    'final_incentive_dashboard': (5, "Final Financial Dashboard"), # Adapting old S7
    'export_package': (6, "Export Package") # Adapting old S8
}


def display_unified_intake_screen():
    st.title("Let's Start Sizing!")
    st.markdown("Enter basic property and energy usage information to begin.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'unified_intake')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data

    # These are stored in st.session_state.form_data for use by subsequent screens
    form_data["unified_address_zip"] = st.text_input( # Changed key for clarity
        "📍 Property Address or ZIP Code",
        value=form_data.get("unified_address_zip", ""),
        key="s1_unified_address_zip",
        help=AI_HELPER_TEXTS_UNIFIED_INTAKE.get("address_zip")
    )
    
    zip_val_for_hint = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    zip_hint = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_val_for_hint, ELIGIBILITY_CHECKS_UNIFIED_INTAKE["default"])
    if zip_hint["type"] == "success":
        st.success(zip_hint["text"], icon="✅")
    else:
        st.info(zip_hint["text"], icon="💡")

    # Business Type - from the new screen flow ==> "Homeowner, Commercial, Farm, Nonprofit, etc."
    # This also maps to user_type input
    biz_type_options = ["Homeowner", "Commercial / Business", "Farm / Agriculture", "Nonprofit", "Tribal Entity", "Rural Cooperative"]
    current_biz_type = form_data.get("unified_business_type", biz_type_options[0])
    form_data["unified_business_type"] = st.selectbox(
        "👤 Primary User / Business Type",
        options=biz_type_options,
        index=biz_type_options.index(current_biz_type) if current_biz_type in biz_type_options else 0,
        key="s1_unified_biz_type",
        help=AI_HELPER_TEXTS_UNIFIED_INTAKE.get("business_type_unified")
    )

    col1, col2 = st.columns(2)
    with col1:
        form_data["unified_monthly_kwh"] = st.number_input(
            "⚡ Avg. Monthly Electricity Usage (kWh)",
            min_value=0, value=form_data.get("unified_monthly_kwh", 1000), step=50,
            key="s1_unified_monthly_kwh", help=AI_HELPER_TEXTS_UNIFIED_INTAKE.get("monthly_kwh_usage")
        )
    with col2:
        form_data["unified_electricity_rate"] = st.number_input(
            "💲 Current Electricity Rate ($/kWh)",
            min_value=0.0, value=form_data.get("unified_electricity_rate", 0.15), step=0.01, format="%.2f",
            key="s1_unified_elec_rate", help=AI_HELPER_TEXTS_UNIFIED_INTAKE.get("electricity_rate")
        )
    
    if form_data.get("unified_monthly_kwh", 0) > 0:
        recommended_size = calculate_solar_system_size_from_usage(form_data["unified_monthly_kwh"])
        st.info(f"Recommended solar system size based on your usage: **{recommended_size:.1f} kW**", icon="📐")
        form_data["calculator_initial_autosized_kw"] = recommended_size # Store for next screen

    st.markdown("---")
    if st.button("Continue to Solar & Battery Calculator ➡️", type="primary", use_container_width=True, key="s1_to_s2_continue"):
        # Store necessary pre-filled values for calculator screen based on unified intake
        form_data["calculator_address_from_s1"] = form_data.get("unified_address_zip")
        form_data["calculator_user_type_from_s1"] = form_data.get("unified_business_type")
        form_data["calculator_monthly_kwh_from_s1"] = form_data.get("unified_monthly_kwh")
        form_data["calculator_elec_rate_from_s1"] = form_data.get("unified_electricity_rate")
        return True # Signal to main_app to navigate
    return False