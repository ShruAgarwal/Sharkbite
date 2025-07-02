import streamlit as st
import pandas as pd
from sharkbite_engine.utils import AI_HELPER_TEXTS_CALCULATOR, generate_progress_bar_markdown
from sharkbite_engine.ui_unified_intake_screen import SCREEN_FLOW_MAP_NEW


def display_solar_battery_calculator_screen():
    st.title("🛠️ Solar & Battery Calculator (New S2)")
    st.markdown("Refine system size and see initial savings/ROI (using simplified MACRS).")
    
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'solar_battery_calculator')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data

    st.subheader("👀 Review & Refine Your Project Details")
    col_review1, col_review2 = st.columns(2)
    with col_review1:
        st.caption("From Unified Intake:")
        st.write(f"**Address/ZIP:** {form_data.get('unified_address_zip', 'N/A')}")
        st.write(f"**User Type:** {form_data.get('unified_business_type', 'N/A')}")
    with col_review2:
        st.write(f"**Avg. Monthly kWh:** {form_data.get('unified_monthly_kwh', 0):,} kWh")
        st.write(f"**Rate:** ${form_data.get('unified_electricity_rate', 0.0):.2f}/kWh")
    st.markdown("---")

    # System Sizing Refinement
    st.subheader("☀️ Solar System Sizing")
    initial_autosized_kw = form_data.get("calculator_initial_autosized_kw", 5.0) # Get from S1
    
    form_data["calculator_refined_system_size_kw"] = st.number_input(
        "Refine or Confirm System Size (kW)",
        min_value=0.5,
        value=form_data.get("calculator_refined_system_size_kw", initial_autosized_kw),
        step=0.1, key="s2_refined_size_input", help=AI_HELPER_TEXTS_CALCULATOR.get("system_size_kw")
    )

    st.subheader("🔋 Battery Backup")
    backup_options = ["No Backup", "Essentials Only", "Whole House Backup"]
    current_backup_pref = form_data.get("calculator_backup_pref", backup_options[0])
    form_data["calculator_backup_pref"] = st.selectbox(
        "Battery Backup Preference", options=backup_options,
        index=backup_options.index(current_backup_pref),
        key="s2_backup_pref_select", help=AI_HELPER_TEXTS_CALCULATOR.get("backup_pref")
    )

    analysis_button_pressed = st.button("📊 Calculate Initial Savings & ROI", type="primary", use_container_width=True, key="s2_calculate_roi_signal_btn")

    if analysis_button_pressed:
        st.session_state.trigger_calculator_api_processing = True # Signal sharkbite_app
        st.session_state.calculator_results_display = None # Clear old results before rerun
        st.rerun() # Let sharkbite_app handle processing

    # Display results if populated by sharkbite_app.py
    if st.session_state.get("calculator_results_display"):
        results = st.session_state.calculator_results_display
        
        if results.get("geo_error"):
            st.error(f"Geocoding: {results['geo_error']}", icon="🗺️")
        elif results.get("lat"):
            st.success(f"Location: Lat {results['lat']:.4f}, Lon {results['lon']:.4f}", icon="📍")

        if results.get("pv_error"):
            st.error(f"PVWatts: {results['pv_error']}", icon="☀️")
        elif results.get("ac_annual") is not None:
            st.info(f"Est. Annual Solar Production: **{results['ac_annual']:,.0f} kWh**", icon="☀️")
            
            # Display monthly breakdown if 'ac_monthly' is in results
            if results.get("ac_monthly"):
                 df_prod = pd.DataFrame({"Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "kWh Produced": results["ac_monthly"]})
                 with st.expander("View Monthly Production Estimate"):
                     st.dataframe(df_prod, hide_index=True, use_container_width=True)
        
        financials = results.get("financials", {})
        if financials:
            st.subheader("📈 Initial Financial Estimates (Simplified MACRS)")
            # ... (metric display logic from previous response using `financials` dict) ...
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Est. Annual Savings", f"${financials.get('annual_savings_calculator',0):,.0f}")
                st.metric("Simple ROI", f"{financials.get('roi_calculator_percent',0):.1f}%")
            payback_val = financials.get('payback_calculator_years',0)
            st.metric("Simple Payback", f"{payback_val:.1f} Years" if isinstance(payback_val, (int,float)) and payback_val != float('inf') else "N/A")

            with col_b:
                st.metric("Est. Net Project Cost", f"${financials.get('net_cost_calculator',0):,.0f}")
                st.metric("Monthly Cashflow ($)", f"${financials.get('monthly_cashflow',0):.2f}")
            
                
            # Display Battery Info if calculated
            if results.get("battery_kwh", 0) > 0:
                st.write(f"**Est. Battery:** {results['battery_kwh']:.1f} kWh ({results['battery_units']} units), Cost: ${results['battery_cost']:,.0f}, Backup: {results['backup_duration_days']:.1f} days")

    # Navigation
    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Unified Intake", use_container_width=True, key="s2_back_to_s1"):
            st.session_state.calculator_results_display = None # Clear results
            return "unified_intake"
    with nav_col2:
        if st.button("Continue to Incentive Preview ➡️", type="primary", use_container_width=True, key="s2_to_s3_continue"):
            # Pass calculator results to form_data for next screen if needed for pre-fill
            form_data["calculator_system_cost_output"] = st.session_state.calculator_results_display.get("financials", {}).get("total_cost_with_battery")
            
            # Add other key outputs as needed
            return "incentive_preview"
    return None