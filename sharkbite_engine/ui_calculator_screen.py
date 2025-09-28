import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sharkbite_engine.utils import (
    AI_HELPER_TEXTS_CALCULATOR, generate_progress_bar_markdown,
    BATTERY_COST_PER_KWH, DEFAULT_DC_AC_RATIO,
    NET_METER_CREDIT_FACTOR, TOU_SCHEDULE_CONFIG
)
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
        st.write(f"**Address/ZIP:** {form_data.get('unified_address_zip', 'N/A')}")
        st.write(f"**User Type:** {form_data.get('unified_business_type', 'N/A')}")
    with col_review2:
        st.write(f"**Avg. Monthly kWh:** {form_data.get('unified_monthly_kwh', 0):,} kWh")
        st.write(f"**Rate:** ${form_data.get('unified_electricity_rate', 0.0):.2f}/kWh")
    st.markdown("---")


    with st.container(border=True):
        # System Sizing + Battery Refinement
        sb1, sb2 = st.columns(2)
        with sb1:
            st.subheader("☀️ Solar System Sizing")
            initial_autosized_kw = form_data.get("calculator_initial_autosized_kw", 8.0) # Get from S1

            form_data["calculator_refined_system_size_kw"] = st.number_input(
                "Confirm or Adjust PV System Size (kW)",
                1.0, 500.0, initial_autosized_kw, 0.1,
                key="s2_refined_size_input",
                help=AI_HELPER_TEXTS_CALCULATOR.get("system_size_kw")
            )

            # Inverter Size Input
            default_inverter_size = form_data.get("calculator_refined_system_size_kw", 8.0) / DEFAULT_DC_AC_RATIO
            form_data["inverter_size_kw"] = st.number_input("Inverter AC Size (kW)", 1.0, 500.0,
                                                            default_inverter_size, 0.1,
                                                            help="Often sized smaller than the DC array (e.g., DC/AC ratio of 1.25).")

        with sb2:
            st.subheader("🔋 Battery Backup")
            backup_options = ["No Backup", "Essentials Only (10 kWh)", "Whole House Backup (25 kWh)"]
            current_backup_pref = form_data.get("calculator_backup_pref", backup_options[0])
            form_data["calculator_backup_pref"] = st.selectbox(
                "Battery Backup Preference", options=backup_options,
                index=backup_options.index(current_backup_pref),
                key="s2_backup_pref_select", help=AI_HELPER_TEXTS_CALCULATOR.get("backup_pref")
            )

            form_data["min_battery_reserve_pct"] = st.slider(
            "Minimum Battery Reserve (%)", 0, 100, 20,
            help="Set a minimum charge level to maintain for backup during outages."
            )

        form_data["override_battery_cost"] = st.number_input(
            "Battery Turn-key Cost $/kWh (Optional)", 400, 1200, BATTERY_COST_PER_KWH, 25,
            key="s2_adv_battery_cost", help="Override the default battery cost."
        )

    # --- "Future Load" Modeling & Advanced TOU Settings UI Inputs ---
    with st.expander("⚙️ Plan for Future Electrification & Advanced Financial Assumptions (Optional)"):
        st.info("**Add potential future electric loads to right-size your system for tomorrow.**")
        load_col1, load_col2 = st.columns(2)
        with load_col1:  # EV Charging
            st.write("🚗 **Electric Vehicle (EV) Charging**")
            form_data["ev_annual_miles"] = st.number_input("Annual Miles Driven", 0, 50000,
                                                        value=form_data.get("ev_annual_miles", 0), step=1000)
            form_data["ev_efficiency_mi_kwh"] = st.number_input("EV Efficiency (miles/kWh)", 1.0, 6.0,
                                                                value=form_data.get("ev_efficiency_mi_kwh", 4.0), step=0.1)

        with load_col2:  # Heat Pump
            st.write("🔥 **Electric Heat Pump**")
            form_data["heat_pump_btu_yr"] = st.number_input("Heat Pump Annual BTU (in millions)", 0, 100,
                                                            value=int(form_data.get("heat_pump_btu_yr", 0)/1_000_000), step=5) * 1_000_000
            form_data["heat_pump_cop"] = st.number_input("Heat Pump COP (Efficiency)", 1.0, 5.0,
                                                        value=form_data.get("heat_pump_cop", 3.0), step=0.1)
            
        st.write('---')
        st.info("⌚ **These settings will enable a more detailed Time-of-Use (TOU) battery savings analysis in the final summary.**")
        
        # This checkbox acts as the 'tou_enabled' flag
        form_data["tou_enabled"] = st.checkbox("Want to Model Time-of-Use (TOU) Savings?", value=True, key="s2_tou_checkbox")
        
        st.write("*Select your utility rate plan to enable a detailed Time-of-Use (TOU) savings analysis.*")
        rate_plan_options = list(TOU_SCHEDULE_CONFIG.keys())
        
        # The user's choice here will be the single source of truth for TOU rates.
        form_data["rate_plan"] = st.selectbox(
            "Utility Rate Plan",
            options=rate_plan_options,
            key="s2_rate_plan_final_select_v2",
            help="This determines the peak/off-peak rates and times used in the financial model."
        )
        selected_plan_desc = TOU_SCHEDULE_CONFIG[form_data["rate_plan"]]["description"]
        st.caption(selected_plan_desc)


    analysis_button_pressed = st.button("Calculate Initial Proposal", type="primary",
                                        icon=":material/finance:", use_container_width=True,
                                        key="s2_calculate_roi_signal_btn")
    
    if analysis_button_pressed:
        st.session_state.trigger_calculator_api_processing = True # Signals the sharkbite_app
        st.session_state.calculator_results_display = None # Clear old results before rerun
        st.rerun() # Let sharkbite_app handle processing

    # Displays results if populated by `sharkbite_app.py`
    if st.session_state.get("calculator_results_display"):
        results = st.session_state.calculator_results_display
        inputs = st.session_state.get("calculator_inputs_for_processing", {})
        
        if results.get("geo_error"):
            st.error(f"Geocoding: {results['geo_error']}", icon="🗺️")
        elif results.get("lat"):
            st.success(f"Location: Lat {results['lat']:.4f}, Lon {results['lon']:.4f}", icon="📍")

        if results.get("pv_error"):
            st.error(f"PVWatts: {results['pv_error']}", icon="☀️")
        elif results.get("ac_annual") is not None:
            st.info(f"Est. Annual Solar Production: **{results['ac_annual']:,.0f} kWh**", icon="☀️")
            
            # Display monthly breakdown if 'ac_monthly' is in results
            # if results.get("ac_monthly"):
            #      df_prod = pd.DataFrame({"Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], "kWh Produced": results["ac_monthly"]})
            #      with st.expander("View Monthly Production Estimate"):
            #          st.dataframe(df_prod, hide_index=True, use_container_width=True)

        st.info(f"⚡ Future Electrification adds **{results['future_load_kwh']:,.0f} kWh** to your annual usage.", icon="🔌")
            
        st.subheader("Solar Energy Flow")
        sol1, sol2 = st.columns(2)
        sol1.metric("Total Projected Annual Usage (kWh)",
                    f"{st.session_state.form_data.get('total_projected_annual_kwh', 0):,.0f}")
        sol1.metric("PV System Cost ($)", f"${results.get('pv_system_cost'):,.0f}")

        sol2.metric("Battery Size (kWh)",
                    f"{results.get('battery_kwh', 0):.1f}" if results.get('battery_kwh', 0) > 0 else "N/A")
        sol2.metric("Battery Cost ($)",
                    f"${results.get('battery_cost', 0):,.0f}" if results.get('battery_cost', 0) > 0 else "N/A")
            
        # --- KPIs results from the dispatch model ---
        st.subheader("🍀 Energy Independence & Financial Estimates")
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        
        with kpi_col1:
            st.metric("Self-Consumption Rate", f"{results.get('self_consumption_rate_percent', 0):.1f}%",
                        help="Percentage of your solar energy used directly on-site (by loads or battery).")
        with kpi_col2:
            st.metric("Grid Independence Rate", f"{results.get('grid_independence_rate_percent', 0):.2f}%",
                        help="Percentage of your total electricity needs met by your own solar and battery.")
        with kpi_col3:
            st.metric("Net Grid Interaction (kWh/yr)", f"{results.get('net_grid_interaction_kwh', 0):,.0f}",
                        help="Total kWh imported from the grid minus total kWh exported. A lower number means less reliance on the grid.")
    
        financials = results.get("financials", {})
        if financials:
            st.subheader("📈 Initial Financial Estimates (Simplified MACRS)")
            # ... (metric display logic from previous response using `financials` dict) ...
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                st.metric("Capex", f"${financials.get('total_capex', 0):.2f}")
                st.metric("Federal ITC", f"${financials.get('itc_amount', 0):,.0f}")
                st.metric("MACRS Benefit (Commercial)",
                          f"${financials.get('macrs_benefit', 0):,.0f}" if inputs.get("user_type") == "Commercial / Business" else "N/A")

            with col_b:
                st.metric("Net Cost After Incentives", f"${financials.get('net_cost', 0):,.0f}") 
                st.metric("Est. Annual Savings", f"${financials.get('total_annual_savings', 0):,.0f}")
                # Value generated by discharging the battery during high-cost peak hours
                st.metric("Savings from Battery TOU Shifting",
                          f"{financials.get('savings_from_battery_tou_shifting', 0):,.0f}")

            with col_c:
                st.metric("ROI (25 yrs)",
                          f"{financials.get('roi_percent_25_yr', 0):.3f}%" if financials.get('roi_percent_25_yr') != float('inf') else "Immediate")
        
                st.metric("Payback (Years)",
                          f"{financials.get('payback_years', 0):.1f}" if financials.get('payback_years') != float('inf') else "Immediate")
                
                st.metric("Estimated Backup Duration (days)",
                     f"{results.get('backup_duration_days', 0):.1f}" if results.get('backup_duration_days', 0) > 0 else "N/A")
                
            # --- Clarification for Net Metering Credit ---
            st.subheader("⚡ Net Metering Credit Details")
            with st.container(border=True):
                st.markdown(
                    f"""
                    In a self-consumption model, grid export is minimized. Any excess energy sent to the grid is typically credited at a wholesale or 'avoided cost' rate, which is often lower than the retail rate you pay.

                    - **Your Retail Rate:** `${form_data.get("unified_electricity_rate", 0):.3f}/kWh`
                    - **Assumed Export Credit Rate:** `{NET_METER_CREDIT_FACTOR * 100:.0f}%` of retail rate
                    - **Effective Export Value:** `${form_data.get("unified_electricity_rate", 0) * NET_METER_CREDIT_FACTOR:.3f}/kWh`

                    This model prioritizes using your own generated power to maximize savings from **avoided grid purchases** at the higher retail rate.
                    """
                )

        # --- Displays Interactive Charts using Plotly ---
        tab1, tab2, tab3 = st.tabs(["📈 Hourly Energy Flow Chart", "📊 Monthly Cash-Flow Projection", "💸 Comparison Of Estimated Monthly Bill"])
        with tab1:
            st.subheader("How Your Energy Needs are Met Throughout a Typical Summer Day")
            # Select a representative summer day for visualization (e.g., July 15th)
            day_of_year = 195 
            start_hour = day_of_year * 24
            end_hour = start_hour + 24
            day_slice = slice(start_hour, end_hour)

            # Check if the necessary hourly data is available
            if results.get("hourly_solar_to_load") is not None:
                try:
                    # Create a DataFrame for the sample day's data
                    chart_df = pd.DataFrame({
                        "Hour": range(24),
                        "Total Load": results["hourly_load"][day_slice],
                        "Total Solar Production (DC)": results["hourly_solar"][day_slice],
                        "Solar to Load": results["hourly_solar_to_load"][day_slice],
                        "Battery to Load": results["hourly_battery_to_load"][day_slice],
                        "Grid Import": results["hourly_import"][day_slice],
                    }).set_index("Hour")

                    # Creates the figure with a secondary y-axis
                    fig = make_subplots(specs=[[{"secondary_y": True}]])

                    # Bar Traces for Load Components (Left Y-Axis)
                    fig.add_trace(
                        go.Bar(x=chart_df.index, y=chart_df['Solar to Load'],
                            name='Load Met by Solar', marker_color='#FFD700'), # Gold
                        secondary_y=False,
                    )
                    fig.add_trace(
                        go.Bar(x=chart_df.index, y=chart_df['Battery to Load'],
                            name='Load Met by Battery', marker_color='#00BFFF'), # Deep Sky Blue
                        secondary_y=False,
                    )
                    fig.add_trace(
                        go.Bar(x=chart_df.index, y=chart_df['Grid Import'],
                            name='Load Met by Grid (Import)', marker_color='#DC143C'), # Crimson Red
                        secondary_y=False,
                    )

                    # Line Trace for Total Load (Left Y-Axis)
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df['Total Load'], name='Total Household Load',
                                mode='lines', line=dict(dash='dot', color='black', width=3)),
                        secondary_y=False,
                    )

                    # Adding Line Trace for Total Solar Production (Right Y-Axis)
                    # This shows the classic solar "bell curve"
                    fig.add_trace(
                        go.Scatter(x=chart_df.index, y=chart_df['Total Solar Production (DC)'],
                                name='Total Solar Production', mode='lines',
                                line=dict(dash='dot', color='orange', width=3)),
                        secondary_y=True,
                    )

                    # Updates Layout and Axes
                    fig.update_layout(
                        barmode='stack',
                        xaxis_title="Hour of the Day",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    # Set Y-axis titles
                    fig.update_yaxes(title_text="<b>Energy Flow (kWh)</b>", secondary_y=False)
                    fig.update_yaxes(title_text="<b>Solar Production (kWh)</b>", secondary_y=True)

                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("This chart shows how your home's energy needs (black dotted line) are met throughout the day. The stacked bars show the source: first by solar, then by battery, and finally by the grid. The orange line shows your total available solar energy.")
                    
                except Exception as e:
                    st.warning(f"Could not generate the daily energy flow chart. Error: {e}", icon="📊")

        if 'monthly_cash_flow_df' in financials:    
            monthly_df = financials.get('monthly_cash_flow_df')
            if monthly_df is not None and not monthly_df.empty:
                with tab2:
                    st.subheader("Breakdown of Monthly Energy Costs & Savings (Year 1)")
                    fig1 = px.bar(
                        monthly_df,
                        barmode='stack',
                        x=monthly_df.index,
                        y=["Cost Avoided by Solar ($)", "Cost Avoided by Battery ($)", "Remaining Grid Import Cost ($)"],
                        labels={"value": "Cost / Savings ($)", "index": "Month", "variable": "Component"}
                    )
                    fig1.add_scatter(x=monthly_df.index, y=monthly_df["Original Bill Cost ($)"], mode='lines', name='Original Bill Cost', line=dict(dash='dash', color='red'))
                    st.plotly_chart(fig1, use_container_width=True)
                           
                with tab3:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(x=monthly_df.index, y=monthly_df["Monthly Savings ($)"], name='Monthly Utility Savings'))
                    fig2.add_trace(go.Bar(x=monthly_df.index, y=-monthly_df["Loan_Payment_$"], name='Loan Payment (Cost)')) # Show as negative
                    fig2.add_trace(go.Scatter(x=monthly_df.index, y=monthly_df["Net_Cash_Flow_$"], mode='lines+markers', name='Net Cash Flow', line=dict(color='green')))
                    fig2.update_layout(barmode='relative', title_text="Monthly Savings, Loan Payment, and Net Cash Flow", yaxis_title="Amount ($)")
                    st.plotly_chart(fig2, use_container_width=True)
                    st.caption("This chart shows your estimated monthly utility savings versus a simplified loan payment, and the resulting net cash flow.")
                    
                
                    with st.expander("View Detailed Monthly Data"):
                        st.dataframe(monthly_df.style.format("${:,.2f}"))
            else:
                st.warning("Could not generate monthly cash flow data.")
            
    # --- PPA Analyzer Button (Only for Residential users) ---
    user_type = form_data.get("unified_business_type")
    if user_type == "Homeowner":
        st.subheader("Financing Options Comparison")
        if st.button("⚖️ Compare PPA vs. Ownership", use_container_width=True, type="secondary", key="s2_to_ppa_analyzer"):
            # This signals `sharkbite_app.py` to navigate to the new page
            return "ppa_analyzer"

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