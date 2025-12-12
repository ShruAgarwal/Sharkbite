import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sharkbite_engine.ui_reap_flow_screens import set_screen_and_rerun
from sharkbite_engine.claude_service import get_ai_ppa_analysis
from sharkbite_engine.utils import TOOLTIPS

def display_ppa_analyzer_screen():
    st.title("⚖️ PPA vs. System Ownership Analyzer")
    st.markdown("**Compare the long-term financial outcomes of a Power Purchase Agreement (PPA) versus owning your solar system.**")
    st.markdown("---")

    form_data = st.session_state.form_data

    try:
        # --- 1. Pull Correct, Sensible Data from Previous Steps ---
        # We must use the calculator's output, not the incorrect values from your test run.
        calculator_results = st.session_state.get("calculator_results_display", {})
        financials = calculator_results.get("financials", {})
        
        # Use sane defaults if data is missing, to prevent crashes.
        system_size_kw = float(form_data.get("calculator_refined_system_size_kw", 0.0))
        annual_production_kwh_y1 = float(calculator_results.get("ac_annual", 0.0))
        
        # Use the TOTAL PROJECTED annual usage (historical + future electrification)
        annual_usage_kwh = float(form_data.get('total_projected_annual_kwh', 0.0))
        utility_rate_y1 = float(form_data.get("unified_electricity_rate", 0.0))
        ownership_net_cost_y1 = float(financials.get('net_cost', 0.0))

        # VALIDATION: Check for unrealistic production values passed from the calculator
        # A check that's more tolerant and logical than a rigid ratio.
        # It checks if production is zero when it shouldn't be, or if it's absurdly high.
        # A 1 MW system (1000 kW) is a reasonable upper bound for this calculator's context.
        if system_size_kw > 0 and (annual_production_kwh_y1 <= 0 or system_size_kw > 1000):
             
            st.error(f"The annual production data from the calculator seems invalid ({annual_production_kwh_y1:,.0f} kWh for a {system_size_kw} kW system). Please go back and recalculate.", icon="⚠️")
        
            if st.button("⬅️ Back to Main Calculator"):
                set_screen_and_rerun("solar_battery_calculator")
            st.stop()

    except (ValueError, TypeError):
        st.error("Could not load valid project data. Please complete the Solar & Battery Calculator first.", icon="❗")
        if st.button("⬅️ Back to Main Calculator"):
            set_screen_and_rerun("solar_battery_calculator")
        st.stop()
    
    st.subheader("Your Project Data (from Solar Calculator)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Solar System Size", f"{system_size_kw:.1f} kW")
    col2.metric("Est. Annual Production", f"{annual_production_kwh_y1:,.0f} kWh")
    col3.metric("Your Current Utility Rate", f"${utility_rate_y1:.3f}/kWh")
    col4.metric("Ownership Net Cost (Y1)",
                f"${ownership_net_cost_y1:,.0f}",
                help=TOOLTIPS.get("ownership_net_cost_y1"))
    st.markdown("---")

    # --- 2. User Inputs for PPA and Future Projections ---
    st.subheader("Enter PPA & Utility Assumptions for 25-Year Model")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### PPA Terms")
        ppa_rate_y1 = st.number_input("PPA Rate Year 1 ($/kWh)", 0.010, 1.000, 0.160, 0.001, format="%.3f",
                                      help=TOOLTIPS.get("ppa_rate_y1"))
        ppa_escalator = st.number_input("Annual PPA Rate Escalator (%)", 0.0, 5.0, 2.5, 0.1, format="%.1f",
                                        help=TOOLTIPS.get("ppa_escalator"))

    with col_b:
        st.markdown("#### Utility Assumptions")
        utility_escalator = st.number_input("Expected Annual Utility Rate Increase (%)", 0.0, 10.0, 2.0, 0.1, format="%.1f",
                                            help=TOOLTIPS.get("utility_escalator"))

    # Add inputs for O&M and Inverter Replacement for Ownership model
    with st.expander("Advanced Ownership Cost Assumptions"):
        owner_om_cost_per_kw_yr = st.number_input("Annual O&M Cost ($/kW/year)", 0, 50, 20,
                                                  help=TOOLTIPS.get("owner_om_cost_per_kw_yr"))
        owner_inverter_replacement_cost = st.number_input("Inverter Replacement Cost ($)", 0, 10000, 2500,
                                                          help=TOOLTIPS.get("owner_inverter_replacement_cost"))
        owner_inverter_replacement_year = st.slider("Inverter Replacement Year", 10, 15, 12)

    # --- 3. Run 25-Year Cash Flow Analysis ---
    ppa_term_years = 25  # Standard term for comparison
    years = np.arange(1, ppa_term_years + 1)
    degradation_rate = 0.005  # 0.5% per year, a standard assumption

    # System Production Schedule with Degradation
    production_over_time = annual_production_kwh_y1 * ((1 - degradation_rate) ** (years - 1))

    # Ownership Model Calculations
    annual_om_costs = system_size_kw * owner_om_cost_per_kw_yr
    inverter_cost_schedule = np.zeros(ppa_term_years)
    inverter_cost_schedule[owner_inverter_replacement_year - 1] = owner_inverter_replacement_cost
    utility_rates_over_time = utility_rate_y1 * (1 + utility_escalator / 100) ** (years - 1)
    
    value_of_solar_produced = production_over_time * utility_rates_over_time
    ownership_annual_savings = value_of_solar_produced - annual_om_costs
    ownership_annual_cashflow = ownership_annual_savings - inverter_cost_schedule
    ownership_total_savings = np.sum(ownership_annual_cashflow) # - ownership_net_cost_y1

    # --- PPA Model Calculations ---
    # PPA Pricing Structure & Financial Calculation
    ppa_rates_over_time = ppa_rate_y1 * (1 + ppa_escalator / 100) ** (years - 1)
    ppa_annual_payment = production_over_time * ppa_rates_over_time

    # Customer Savings vs. Utility
    utility_rates_over_time = utility_rate_y1 * (1 + utility_escalator / 100) ** (years - 1)
    utility_cost_without_solar_annual = annual_usage_kwh * utility_rates_over_time  # Use TOTAL projected usage
    ppa_annual_savings = utility_cost_without_solar_annual - ppa_annual_payment  # Simplified savings
    ppa_total_savings = np.sum(ppa_annual_savings)

    total_utility_cost_no_solar = np.sum(utility_cost_without_solar_annual)

    # --- 4. Display Results ---
    st.subheader(f"📊 {ppa_term_years}-Year Financial Comparison")
    summary_df = pd.DataFrame({
        "Metric": ["Upfront Cost", "25-Year Estimated Total Savings"],
        "System Ownership": [f"${ownership_net_cost_y1:,.0f}", f"${ownership_total_savings:,.0f}"],
        "PPA Agreement": ["$0", f"${ppa_total_savings:,.0f}"],
        "Utility (No Solar)": [f"${total_utility_cost_no_solar:,.0f}", f"${np.mean(utility_rates_over_time):,.3f}"]
    }).set_index("Metric")

    st.table(summary_df)

    # --- Render the Chart with Matplotlib ---
    st.subheader("📈 Cumulative Cost & Effective Rate Over Time")
    
    # Create the DataFrame with the Year as the index
    # The chart data is now based on realistic, cumulative costs.
    # np.full_like -- Return a full array with the same shape and type as a given array.
    # numpy.cumsum() -- Cumulative sum refers to a sequence where each element is the sum of all previous elements plus itself.
    # - Example: given an array [1, 2, 3, 4, 5], the cumulative sum would be [1, 3, 6, 10, 15].
    
    # Prepare Data for Plotting ---
    # Cumulative Costs
    cumulative_utility_cost = np.cumsum(utility_cost_without_solar_annual)
    cumulative_ppa_cost = np.cumsum(ppa_annual_payment) # Assuming this is calculated
    cumulative_ownership_cost = np.full_like(years, ownership_annual_cashflow, dtype=float)
    
    # Effective Blended Rates ($/kWh)
    # Rate = Cumulative Cost / Cumulative Production
    cumulative_production = np.cumsum(production_over_time)
    
    # Avoid division by zero on the first element if production is zero
    with np.errstate(divide='ignore', invalid='ignore'):
        effective_rate_ppa = np.divide(cumulative_ppa_cost, cumulative_production)
        effective_rate_ownership = np.divide(cumulative_ownership_cost, cumulative_production)
    # Replace any potential NaNs or infs with 0 or a placeholder
    effective_rate_ppa = np.nan_to_num(effective_rate_ppa, nan=0.0, posinf=0.0, neginf=0.0)
    effective_rate_ownership = np.nan_to_num(effective_rate_ownership, nan=0.0, posinf=0.0, neginf=0.0)

    # Create the Matplotlib Plot
    fig, ax1 = plt.subplots(figsize=(10, 5)) # Create a figure and a set of subplots

    # Plotting Costs on the left Y-axis (ax1)
    color_cost = 'tab:blue'
    ax1.set_xlabel('Project Year')
    ax1.set_ylabel('Cumulative Cost ($)', color=color_cost)
    ax1.plot(years, cumulative_utility_cost, color='gray', linestyle='--', label='Utility Cost (No Solar)')
    ax1.plot(years, cumulative_ppa_cost, color='orange', linestyle='-', label='PPA Cumulative Cost')
    ax1.plot(years, cumulative_ownership_cost, color='green', linestyle='-', label='Ownership Upfront Cost')
    ax1.tick_params(axis='y', labelcolor=color_cost)
    ax1.grid(True, linestyle=':', alpha=0.6)
    
    # Format the left Y-axis with commas for thousands
    ax1.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda x, _: format(int(x), ','))
    )

    # Create a second Y-axis (ax2) that shares the same X-axis
    ax2 = ax1.twinx()
    color_rate = 'tab:red'
    ax2.set_ylabel('Effective Rate ($/kWh)', color=color_rate)
    ax2.plot(years, effective_rate_ppa, color='darkorange', linestyle=':', label='PPA Effective Rate')
    ax2.plot(years, effective_rate_ownership, color='darkgreen', linestyle=':', label='Ownership Effective Rate')
    ax2.tick_params(axis='y', labelcolor=color_rate)

    # Format the right Y-axis as currency
    ax2.get_yaxis().set_major_formatter(
        plt.FuncFormatter(lambda x, _: f'${x:.2f}')
    )

    # Create a unified legend for both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    fig.tight_layout()  # Adjust plot to ensure everything fits without overlapping
    
    # Display the plot
    st.pyplot(fig)
    st.caption("Solid lines represent cumulative costs (left axis). Dotted lines represent the effective blended rate per kWh over time (right axis).")
    
    # --- NEW: Save results to session state for the PDF report generator ---
    st.session_state.ppa_results = {
        "summary_df": summary_df,
        "matplotlib_chart_fig": fig
    }

    # --- AI Analyst Integration ---
    st.markdown("---")
    st.subheader("🤖 AI-Powered Trade-Off Analysis")
    st.info("Leverage AI to get a sophisticated summary of the financial trade-offs between these two options based on your specific project data.")

    if st.button("Generate AI Analyst Summary", icon=":material/smart_toy:",
                 key="ppa_ai_analyst_button_final", type="secondary",
                 use_container_width=True):
        # Prepare the context dictionaries for Claude
        ppa_vs_ownership_data = {
            "Ownership Model Upfront Net Cost ($)": ownership_net_cost_y1,
            "Ownership Model 25-Year Net Savings ($)": ownership_total_savings,
            "PPA Model Upfront Cost ($)": 0,
            "PPA Model 25-Year Net Savings ($)": ppa_total_savings,
            "PPA Year 1 Rate ($/kWh)": ppa_rate_y1,
            "PPA Escalator (%)": ppa_escalator
        }
        
        future_load_data = {
            "ev_annual_kwh": form_data.get("ev_annual_miles", 0) / form_data.get("ev_efficiency_mi_kwh", 4.0),
            "heat_pump_annual_kwh": (form_data.get("heat_pump_btu_yr", 0) / 3412) / form_data.get("heat_pump_cop", 3.0)
        }
        
        # Call the specific AI function
        st.session_state.ai_ppa_analysis_result = get_ai_ppa_analysis(ppa_vs_ownership_data, future_load_data)
        
    # --- Display the structured result ---
    if 'ai_ppa_analysis_result' in st.session_state and st.session_state.ai_ppa_analysis_result:
        ai_analysis = st.session_state.ai_ppa_analysis_result
        
        with st.expander("👇 View AI Analysis here!"):
            if "error" in ai_analysis:
                st.error(f"AI Analysis Error: {ai_analysis['error']}")
                if ai_analysis.get("raw_response"):
                    st.code(ai_analysis["raw_response"], language="text")
            else:        
                st.markdown("### Key Trade-Off: Upfront Cost vs. Long-Term Savings")
                st.write(ai_analysis.get('primary_trade_off', 'N/A'))
                
                st.markdown("### Impact of the Federal Tax Credit (ITC)")
                st.write(ai_analysis.get('itc_impact', 'N/A'))

                st.markdown("### Impact of Your Future Electrification Plans")
                st.write(ai_analysis.get('future_load_impact', 'N/A'))

    # --- Debugging Expander ---
    with st.expander("Show Calculation Inputs & Intermediate Values"):
        st.write("**Inputs used for calculation:**")
        st.json({
            "system_size_kw": system_size_kw,
            "annual_production_kwh": annual_production_kwh_y1,
            "annual_usage_kwh": annual_usage_kwh,
            "utility_rate": utility_rate_y1,
            "ownership_net_cost_y1": ownership_net_cost_y1,
            "ppa_rate_y1": ppa_rate_y1,
            "ppa_escalator": ppa_escalator,
            "utility_escalator": utility_escalator,
            "ppa_term_years": ppa_term_years
        })
        st.write("**Intermediate annual cost arrays (first 10 years):**")
        st.dataframe({
            "Year": years[:10],
            "PPA_Cost_Annual": ppa_annual_payment[:10],
            "Utility_Cost_Annual": utility_cost_without_solar_annual[:10]
        })


    st.markdown("---")
    if st.button("⬅️ Back to Main Calculator", use_container_width=True, key="ppa_back_to_calc"):
        set_screen_and_rerun("solar_battery_calculator") # Assumes this nav function is available