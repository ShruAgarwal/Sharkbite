import streamlit as st
import math
import plotly.graph_objects as go
from sharkbite_engine.utils import (
    STATIC_TOOLTIPS, calculate_detailed_reap_score,
    generate_progress_bar_markdown,
    check_incentive_eligibility,
    perform_final_incentive_stack_calculations  # The master calculator for Screen 6
)
from sharkbite_engine.ui_unified_intake_screen import SCREEN_FLOW_MAP_NEW
from sharkbite_engine.incentive_definitions import INCENTIVE_PROGRAMS
from sharkbite_engine.claude_service import (
    get_ai_recommendations,
    get_core_equipment_recommendation,
    analyze_financial_data_with_claude
)

# --- Helper Function to Navigate ---
def set_screen_and_rerun(screen_name):
    st.session_state.current_screen = screen_name
    st.rerun()

# --- NEW: A simple, reusable helper function for formatting metrics ---
def format_financial_metric(value, unit="", precision=1, is_percent=False):
    """
    Handles formatting for ROI and Payback, including 'inf' cases.
    Returns a clean string ready for display.
    """
    if value is None or (isinstance(value, float) and math.isinf(value)):
        # For ROI, 'inf' means immediate return. For Payback, it means no payback.
        return "Immediate" if is_percent else "N/A (No Savings)"
    if value == 0.0 and not is_percent:
        return "Immediate" # A 0-year payback is immediate
    
    # Standard formatting for numbers
    formatted_value = f"{value:,.{precision}f}"
    return f"{formatted_value}{unit}"


# ========== Screen 3: Incentive Preview ==========
def display_incentive_preview_screen():
    st.title("🎁 Incentive Preview (New S3)")
    st.markdown("Based on your initial inputs, here are the grant, loan, and tax programs you may be eligible for. Select which ones you'd like to model in the next step.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'incentive_preview')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data
    
    # Ensure calculator results exist before trying to display them.
    calculator_results = st.session_state.get("calculator_results_display")
    if not calculator_results or "financials" not in calculator_results:
        st.error("Financial calculations from the previous step are missing.", icon="❗")
        st.warning("Please go back to the Solar & Battery Calculator and run the analysis before proceeding.")
        if st.button("⬅️ Back to Solar & Battery Calculator", key="s3_back_to_s2_error"):
            return "solar_battery_calculator"
        return None  # Stop rendering the rest of the page

    calculator_financials = calculator_results.get("financials", {})

    st.subheader("👀 Summary from Solar & Battery Calculator")
    col_rev1, col_rev2 = st.columns(2)
    with col_rev1:
        # Use a safe_format or default to 0 to prevent errors
        system_size = form_data.get('calculator_refined_system_size_kw', 0.0)
        annual_prod = calculator_results.get('ac_annual', 0.0)
        st.metric("System Size", f"{system_size:.1f} kW")
        st.metric("Est. Annual Production", f"{annual_prod:,.0f} kWh")
    with col_rev2:
        # Gracefully handle potentially missing data by defaulting to 0
        annual_savings = calculator_financials.get('total_annual_savings', 0.0) # annual_savings_calculator
        net_cost = calculator_financials.get('net_cost', 0.0) # net_cost_calculator
        st.metric("Est. Annual Savings", f"${annual_savings:,.0f}")
        st.metric("Est. Net Cost", f"${net_cost:,.0f}")

    with st.spinner("Checking your eligibility for dozens of programs..."):
        eligible_programs = check_incentive_eligibility(form_data)
        st.session_state.eligible_programs = eligible_programs
    
    st.subheader("Potentially Eligible Programs")
    st.caption("Select the incentives you wish to include in your final financial model.")

    if not eligible_programs:
        st.warning("Based on your initial inputs, no specific grant programs were matched. You can still proceed to model federal tax credits.")
        st.session_state.incentives_to_model = []
    
    with st.form("incentive_selection_form"):
        selected_incentives = []
        for program in INCENTIVE_PROGRAMS: # Loop through all to maintain order
            is_eligible = program['id'] in [p['id'] for p in eligible_programs]
            
            # Default to True if it's a core federal incentive and eligible
            default_selection = is_eligible and program['id'] in ['usda_reap_grant', 'itc_macrs']
            
            # Use a checkbox; disable if not eligible
            is_selected = st.checkbox(
                f"**{program['name']}** ({program['level']} {program['type']})",
                value=default_selection,
                key=f"select_{program['id']}",
                disabled=not is_eligible
            )
            if is_selected:
                selected_incentives.append(program['id'])
        
        submitted = st.form_submit_button("Continue with Selected Incentives ➡️", type="primary")
        if submitted:
            st.session_state.incentives_to_model = selected_incentives
            # Pre-fill data for next screen
            calculator_financials = st.session_state.get("calculator_results_display", {}).get("financials", {})
            form_data['q1_biz_structure'] = form_data.get("unified_business_type")
            form_data['address_for_reap'] = form_data.get("unified_address_zip")
            form_data['system_cost_for_reap'] = calculator_financials.get("total_capex")
            form_data['system_size_for_reap'] = form_data.get("calculator_refined_system_size_kw")
            form_data['technology_for_reap'] = "Solar PV"   # Assuming from calculator context
            set_screen_and_rerun("reap_deep_dive")

    # --- NEW: 1.1 "AI Recommendations" Feature ---
    st.subheader("Personalized AI Recommendations for Your Project")

    if st.button("Get AI Recommendations", key="s3_get_recs_btn", type="secondary", icon=":material/smart_toy:"):
        with st.expander("👇 View AI Recommendations here!"):
            # Check if recommendations have already been generated for this session's data
            if 'ai_recommendations' not in st.session_state or st.session_state.ai_recommendations is None:
                # Build a rich context dictionary for the prompt ---
                calculator_results = st.session_state.get("calculator_results_display", {})
                financials = calculator_results.get("financials", {})
                
                context_for_ai = {
                    "user_type": form_data.get("unified_business_type"),
                    "location_zip": form_data.get("unified_address_zip"),
                    "avg_monthly_kwh": form_data.get("unified_monthly_kwh"),
                    "system_size_kw": form_data.get("calculator_refined_system_size_kw"),
                    "backup_preference": form_data.get("calculator_backup_pref"),
                    "est_annual_production_kwh": calculator_results.get("ac_annual"),
                    "est_net_cost": financials.get("net_cost"), # net_cost_calculator
                    "est_annual_savings": financials.get("total_annual_savings"), # annual_savings_calculator
                    "initially_eligible_programs": [p['name'] for p in eligible_programs]
                }

                # Call the function and store the result in session state
                st.session_state.ai_recommendations = get_ai_recommendations("Incentive Selection Stage", context_for_ai)
                
            # Displays AI responses from stored `recommendations` variable
            recommendations = st.session_state.ai_recommendations
            if recommendations:
                for rec in recommendations:
                    st.markdown(f"- {rec}")
            else:
                st.info("No specific AI recommendations at this moment. Your current selections look like a good starting point.")

    st.markdown("---")
    if st.button("⬅️ Back to Solar & Battery Calculator", use_container_width=True, key="s3_back_to_s2_final"):
        set_screen_and_rerun("solar_battery_calculator")
    return None


# ========== Screen 4: REAP Deep Dive ==========
def display_reap_deep_dive_screen():
    st.title("📊 REAP Score Preview & Document Simulation (New S4)")
    st.markdown("Confirm your REAP eligibility details and see your live score update. A higher score increases funding chances.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'reap_deep_dive')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    form_data = st.session_state.form_data
    st.subheader("👀 Pre-filled from Calculator & Initial Intake")
    st.write(f"Business Type: {form_data.get('q1_biz_structure', 'N/A')}")
    st.write(f"Project Location (ZIP from Address): {form_data.get('address_for_reap', 'N/A')}")
    st.write(f"Technology: {form_data.get('technology_for_reap', 'Solar PV')}")
    st.write(f"System Size: {form_data.get('calculator_refined_system_size_kw', 0.0)} kW") # 'system_size_for_reap'
    st.write(f"Estimated Project Cost (CapEx): ${form_data.get('system_cost_for_reap', 0):,.0f}") #:,.0f

    # ==== INTEGRATES ORIGINAL REAP INTAKE FORM ====
    # Collect all inputs needed for the REAP score
    st.subheader("REAP Eligibility Details")
    with st.container(border=True):
        reap_col1, reap_col2 = st.columns(2)
        with reap_col1:
            form_data['reap_business_name'] = st.text_input(
            "Official Business Name for REAP Application",
            value=form_data.get('unified_business_type', 'N/A'),  # Pre-fill from S1
            key="s4_reap_biz_name"
        )
            
            # Note: Project Type and Technology are largely pre-filled from calculator
            # But we can allow confirmation or specification here if needed
            project_type_options = ["Renewable Energy System (RES)", "Energy Efficiency Improvement (EEI)", "Combined RES + EEI"]
            current_proj_type = form_data.get("q2_project_type_reap", project_type_options[0]) # Default to RES from calc
            form_data["q2_project_type_reap"] = st.selectbox(
                "Confirm REAP Project Type:",
                options=project_type_options,
                index=project_type_options.index(current_proj_type),
                key="s4_reap_proj_type",
                help="Confirm the category your project falls under for REAP."
            )

        with reap_col2:
            reap_tech_options = ["Solar PV", "Wind Turbine", "Anaerobic Digester", "Geothermal", "Battery Storage (with solar)", "Lighting / HVAC Upgrade", "Other"]
            # Pre-fill with a reasonable default from the calculator context
            default_tech_for_reap = "Solar PV" if "solar" in form_data.get('technology_for_reap', '').lower() else reap_tech_options[0]
            current_reap_tech = form_data.get('reap_specific_technology', default_tech_for_reap)
            form_data['reap_specific_technology'] = st.selectbox(
                "Confirm Primary Technology for REAP",
                options=reap_tech_options,
                index=reap_tech_options.index(current_reap_tech) if current_reap_tech in reap_tech_options else 0,
                key="s4_reap_tech_select",
                help="The technology type can affect REAP grant caps and scoring."
            )

            reap_history_options = ["First-time applicant", "Prior award (2+ years ago)", "Recent award (last 2 years)"]
            current_reap_history = form_data.get("q7_reap_funding_history", reap_history_options[0])
            form_data["q7_reap_funding_history"] = st.radio(
                "Have you received REAP funding before?",
                options=reap_history_options,
                index=reap_history_options.index(current_reap_history),
                key="s4_reap_history", horizontal=True,
                help="First-time applicants are prioritized for REAP scoring."
            )
        
        form_data["q4_ghg_emissions"] = st.toggle(
            "Does this project result in zero GHG emissions?",
            value=form_data.get("q4_ghg_emissions", True),
            key="s4_ghg_toggle",
            help="Zero-emissions projects get a scoring bonus."
        )

        st.subheader("Document Upload Simulation")
        form_data['mock_doc_score_reap'] = st.slider("Simulate Document Score (0-20 pts)", 0, 20, 10,
                                                    key="s4_doc_score_slider_live",
                                                    help="This simulates the points awarded for having documents like audits, permits, and deeds ready."
                                                    )
        st.info("👇 Your REAP score is affected by the completeness of your documentation.")
        
    st.subheader("⚡ Live REAP Score Preview")
    with st.container(border=True):

        # --- Performs live calculation ---
        # Use data directly from form_data which is being updated live by widgets
        reap_score_raw, breakdown, normalized_score = calculate_detailed_reap_score(form_data)
        # Store for the next screen
        st.session_state.form_data['final_reap_score_for_dashboard'] = reap_score_raw

        # Display score with progress bar
        st.metric("Current Estimated Score", f"{normalized_score} / 100")
        st.progress(normalized_score / 100)
        st.caption(f"Competitive Threshold: 75+")
        
        # Display score breakdown
        with st.expander("View Score Breakdown"):
            for detail in breakdown:
                st.markdown(f"- {detail}")

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Incentive Preview", use_container_width=True, key="s4_back_to_s3_reap_final"):
            set_screen_and_rerun("incentive_preview")
    with nav_col2:
        if st.button("Continue to Multi-Grant Stacker ➡️", type="primary", use_container_width=True, key="s4_to_s5_new"):
            set_screen_and_rerun("multi_grant_stacker")
    return None


# ========== Screen 5: Multi-Grant Stacker ==========
def display_multi_grant_stack_screen():
    st.title("💰 Multi-Grant & Incentive Stacker (New S5)")
    st.markdown("Please provide the specific details needed for each of your selected incentive programs.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'multi_grant_stacker')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data
    incentives_to_model_ids = st.session_state.get("incentives_to_model", [])
    other_programs_to_model = [p for p in INCENTIVE_PROGRAMS if p['id'] in incentives_to_model_ids and p['id'] not in ['usda_reap_grant', 'itc_macrs'] and p.get("calculation_inputs")]

    # --- NEW: Dedicated AI Section for CA CORE if it's eligible ---
    is_core_program_selected = 'ca_core' in incentives_to_model_ids
    if is_core_program_selected:
        st.subheader("🚜 AI Assistant for California CORE")
        st.info("Since you are eligible for the CA CORE voucher, AI can help recommend the best equipment type and estimate your voucher amount.")

        if st.button("Get AI Suggestion", key="s5_get_core_ai_suggestion", type="secondary", icon=":material/smart_toy:"):
            with st.expander('✨ View the AI Equipment Suggestion here!'):
                # Prepare a concise summary for this specific task
                project_summary_for_core = {
                    "User Profile": {
                        "Business Type": form_data.get("unified_business_type"),
                        "Location (ZIP)": form_data.get("unified_address_zip"),
                        "REAP Funding History": form_data.get("q7_reap_funding_history")
                    },
                    "Project Overview": {
                        "Primary Technology Focus": form_data.get("reap_specific_technology", form_data.get("technology_for_reap")),
                        "Project Type for REAP": form_data.get("q2_project_type_reap"),
                        "Is Zero GHG Emissions": form_data.get("q4_ghg_emissions"),
                        "Solar System Size (kW)": form_data.get("calculator_refined_system_size_kw"), # system_size_for_reap
                        "Battery Backup Preference": form_data.get("calculator_backup_pref"),
                        "Estimated Project Cost ($)": form_data.get("system_cost_for_reap")
                    }
                    
                }
                # Call the new AI function and store the result in session state
                st.session_state.core_ai_recommendation = get_core_equipment_recommendation(project_summary_for_core)
                # No rerun needed here, the result is displayed immediately below
            
            # Display the result if it exists in session state
            if 'core_ai_recommendation' in st.session_state and st.session_state.core_ai_recommendation:
                recommendation = st.session_state.core_ai_recommendation
                
                if "error" in recommendation:
                    st.error(f"AI Recommendation Error: {recommendation['error']}")
                else:
                    st.success(f"""
                    **Recommendation:** *{recommendation.get('explanation')}*\n
                    **Recommended Equipment:** *{recommendation.get("recommended_equipment_type")}*
                    """)
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Base Voucher", f"${recommendation.get('base_voucher_amount', 0):,}")
                    col2.metric("Total Voucher (with bonuses)", f"${recommendation.get('total_voucher_amount', 0):,}")

                    st.info(f"""
                            :blue[**This includes a {recommendation.get('enhancement_percent', 0)*100:.0f}% enhancement bonus.**]

                            ⭐ You can use this recommendation to fill out the manual CORE inputs below,
                            or choose a different option.""")

    with st.form("multi_grant_form"):

        st.subheader("Tax & Depreciation Assumptions")
    
        # This input is critical for the detailed MACRS calculation on the next screen.
        form_data["placed_in_service_year"] = st.selectbox(
            "Anticipated 'Placed in Service' Year",
            options=[2024, 2025, 2026, 2027],  # Provide relevant years
            index=0,  # Default to 2024
            key="s5_service_year",
            help="The year your project becomes operational. This determines the Bonus Depreciation rate (e.g., 60% for 2024, 40% for 2025)."
        )
         
        if not other_programs_to_model:
            st.info("No additional grant programs were selected to model. You can proceed directly to the final summary.")
        else:
            st.subheader("Details for Additional Selected Programs")
            for program in other_programs_to_model:
                with st.container(border=True):
                    st.markdown(f"**Inputs for: {program['name']}**")
                    for inp in program["calculation_inputs"]:
                        input_key = f"{program['id']}_{inp['id']}"
                        default_value = form_data.get(input_key, inp.get('value', 0.0))
                        
                        if inp['type'] == "number_input":
                            form_data[input_key] = st.number_input(inp['label'], value=float(default_value), key=input_key)
                        
                        elif inp['type'] == "slider":
                            form_data[input_key] = st.slider(inp['label'], min_value=inp['min'], max_value=inp['max'], value=int(default_value), key=input_key)
                        
                        elif inp['type'] == "selectbox":
                            options = inp.get("options", [])
                            index = options.index(default_value) if default_value in options else 0
                            form_data[input_key] = st.selectbox(inp['label'], options=options, index=index, key=input_key)
                        
                        elif inp['type'] == "toggle":
                            form_data[input_key] = st.toggle(inp['label'], value=bool(default_value or False), key=input_key)
            
        submitted = st.form_submit_button("Continue to Final Financial Dashboard ➡️", type="primary")
        if submitted:
            set_screen_and_rerun("final_incentive_dashboard")


    st.markdown("---")
    if st.button("⬅️ Back to REAP Deep Dive", use_container_width=True, key="s5_back_to_s4_final"):
        set_screen_and_rerun("reap_deep_dive")

    return None


# ========== Screen 6: Final Incentive Dashboard ==========
def display_final_incentive_dashboard_screen():
    st.title("💵 Final Incentive Dashboard (New S6)")
    st.markdown("This is your consolidated financial summary, incorporating all selected and calculated incentives based on the **Sharkbite Order of Operations**.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'final_incentive_dashboard')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    form_data = st.session_state.form_data
   
    # Perform the master calculation directly on this screen when it loads.
    # The results are used immediately for display.
    with st.spinner("Performing final compliance checks and financial modeling..."):
        final_results = perform_final_incentive_stack_calculations(form_data)
        # Store results in session state in case we need them on the export screen
        st.session_state.final_financial_results = final_results

    if not final_results:
        st.error("Financial results have not been calculated. Please complete the 'Multi-Grant Stacker' step.")
        if st.button("⬅️ Go Back", key="s6_back_no_results"):
            set_screen_and_rerun("multi_grant_stacker")
        return None

    # Now, simply display the results from the `final_results` dictionary
    st.subheader("✅ Final Compliant Incentive Stack Summary")
    calc_results = st.session_state.get("calculator_results_display", {})
    dep_details = final_results.get("depreciation_details", {})
    
    with st.container(border=True):
        st.write(f"#### Total Project Cost (CapEx): ${final_results.get('total_project_cost', 0):,.2f}")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏆 REAP Grant (Adjusted)", f"${final_results.get('reap_grant_final', 0):,.0f}",
                      help=STATIC_TOOLTIPS.get("REAP_GRANT"))
            st.metric("💰 Federal ITC (Total)", f"${final_results.get('total_itc_value', 0):,.0f}",
                      help=STATIC_TOOLTIPS.get("ITC"))
        with col2:
            st.metric("Correct Depreciable Basis", f"${final_results.get('correct_depreciable_basis', 0):,.2f}",
                      help="Your basis for depreciation after a 50% ITC reduction")
            
            # Only show this section if there are actual depreciation details to display
            if dep_details and dep_details.get("year_1_total_depreciation_tax_benefit", 0) > 0:
                st.write(f"**Year 1 Depreciation Benefits (for a {form_data.get('placed_in_service_year', 'N/A')} project):**")
                
                bonus_rate_pct = dep_details.get('bonus_depreciation_rate', 0) * 100
                bonus_value = dep_details.get('bonus_depreciation_value', 0)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• Bonus Depreciation (@ {bonus_rate_pct:.0f}%): **${bonus_value:,.2f}**")

                macrs_value = dep_details.get('macrs_year1_value', 0)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• 5-Year MACRS (Year 1 @ 20% on remainder): **${macrs_value:,.2f}**")

        with col3:
            st.metric("📉 MACRS + Bonus Dep. (Y1 Tax Benefit)", f"${final_results.get('year_1_depreciation_tax_benefit', 0):,.2f}" if final_results.get('year_1_depreciation_tax_benefit',0) > 0 else "N/A",
                      help="The total tax savings from depreciation in the first year, calculated on the adjusted basis.")
            st.metric("💵 Total Benefits (Year 1)", f"${final_results.get('total_grant_and_tax_benefits', 0):,.0f}")
        
        if not final_results.get("is_fed_share_compliant"):
            st.error(f"🚨 Federal Share Warning: The initial REAP Grant was reduced to comply with the 50% federal share limit. The final compliant grant is reflected above.", icon="⚖️")

    other_grants = final_results.get("other_grant_values", {})
    if other_grants:
        st.subheader("Other State & Federal Program Benefits")
        with st.container(border=True):
            # Display other grants in columns for better layout
            num_other_grants = len(other_grants)
            other_cols = st.columns(num_other_grants if num_other_grants > 0 else 1)
            for i, (name, value) in enumerate(other_grants.items()):
                with other_cols[i % num_other_grants]:
                    st.metric(label=name, value=f"${value:,.0f}" if isinstance(value, (int, float)) else str(value))

    st.subheader("Final Project Financials")
    with st.container(border=True):
        # --- GRACEFUL DISPLAY LOGIC ---
        fin_col1, fin_col2 = st.columns([7, 3])
        
        net_cost_final = final_results.get('final_net_cost', 0)
        final_roi = final_results.get('final_roi', 0)
        final_roi_25_yr = calc_results.get("financials", {}).get("roi_percent_25_yr")
        final_payback = final_results.get('final_payback', float('inf'))
        
        # Get the annual savings calculated with the hourly dispatch model
        annual_savings = calc_results.get("financials", {}).get('total_annual_savings')
        cash_positive_note = final_results.get('cash_positive_note', "")
        
        # --- NEW: Plotly Waterfall Chart ---
        waterfall_data = final_results.get("waterfall_chart_data")
        
        if waterfall_data:
            # Create the figure using Plotly Graph Objects
            fig = go.Figure(go.Waterfall(
                name = "Financial Breakdown",
                orientation = "v",
                measure = ["absolute"] + ["relative"] * (len(waterfall_data) - 1) + ["total"],
                x = list(waterfall_data.keys()) + ["Final Net Cost"],
                textposition = "outside",
                # Format the text that appears on the bars
                text = [f"${v:,.0f}" for v in list(waterfall_data.values())] + [f"${final_results.get('final_net_cost', 0):,.0f}"],
                y = list(waterfall_data.values()) + [final_results.get('final_net_cost', 0)],
                connector = {"line":{"color":"rgb(63, 63, 63)"}},
                increasing = {"marker":{"color": "#1f77b4"}}, # Blue for positive (cost)
                decreasing = {"marker":{"color": "#2ca02c"}}, # Green for negative (benefits)
                totals = {"marker":{"color": "#ff7f0e"}} # Orange for total
            ))

            fig.update_layout(
                title = "Financial Breakdown: From Gross to Net Cost",
                showlegend = False,
                yaxis_title="Amount ($)"
            )
            
            fin_col1.plotly_chart(fig, use_container_width=True)
            fin_col1.caption("This chart shows how each grant and tax credit reduces your total upfront project cost to arrive at the final net cost.")
        else:
            fin_col1.warning("Could not generate financial breakdown chart.")

        # Displays Final Net Cost, ROI metrics, & Payback ---
        # Show $0 if it's negative, because you don't have a "negative cost" in reality, you have positive cashflow.
        display_net_cost = max(0, net_cost_final)
        fin_col2.metric("💸 Final Net Project Cost (Y1)", f"${display_net_cost:,.0f}")
        fin_col2.metric("💰 Est. Annual Savings", f"${annual_savings:,.0f}",
                        help="Based on your TOU rates and self-consumption.")
        
        fin_col2.metric("🤑 Final ROI (Simple)",
                        format_financial_metric(final_roi, unit="%", precision=1, is_percent=True))
        fin_col2.metric("🤑 ROI (25 yrs)",
                        format_financial_metric(final_roi_25_yr, unit="%", precision=2, is_percent=True))
 
        fin_col2.metric("⏱️ Final Payback (Years)",
                        format_financial_metric(final_payback, unit=" years", precision=1))
        
        # If there's a cash positive note, display it prominently
        if cash_positive_note:
            st.success(f"🎉 **Excellent Outcome:** {cash_positive_note}", icon="💰")
    
    # --- NEW: 1.2 "AI Analyst" Feature ---
    st.subheader("🌟 AI-Powered Advanced Financial Insights")
    st.info("""Click the button below to send your final project data to Claude AI for an in-depth analysis,
            including risks and mitigation strategies.""")

    if st.button("Generate AI Analysis", key="s6_run_ai_analyst", type="secondary", icon=":material/smart_toy:"):

        with st.expander('📝 View the analysis report!'):
            
            final_results = st.session_state.get("final_financial_results")
            if not final_results:
                st.error("Cannot run AI analysis because final financial results are not available.")
            else:
                # Structure the data for AI
                project_summary_for_ai = {
                    "User Profile": {
                        "User Type": form_data.get("unified_business_type"),
                        "Location (ZIP)": form_data.get("unified_address_zip"),
                        "REAP History": form_data.get("q7_reap_funding_history"),
                        "Historical Monthly kWh": form_data.get("unified_monthly_kwh"),
                        "Future Load (EV, HP) kWh": calc_results.get("future_load_kwh"),
                        "TOU Rate Plan": form_data.get("rate_plan")
                    },
                    "Project Specs": {
                        "Technology": form_data.get("reap_specific_technology", "Solar PV"), # Use the confirmed tech from REAP screen
                        "System Size (kW)": form_data.get("calculator_refined_system_size_kw"),
                        "Battery Size (kWh)": calc_results.get("battery_kwh"),
                        "Estimated Annual Production (kWh)": calc_results.get("ac_annual")
                    },
                    "Financials (Compliant Stack)": {
                        "Total Project Cost (CapEx)": final_results.get("total_project_cost"),
                        "REAP Grant": final_results.get("reap_grant_final"),
                        "Total ITC": final_results.get("total_itc_value"),
                        "Year 1 Depreciation Tax Benefit (Commercial)": final_results.get("year_1_depreciation_tax_benefit"),
                        "Other Grants Total": sum(v for v in final_results.get("other_grant_values", {}).values() if isinstance(v, (int, float))),
                        "Total Benefits (Year 1)": final_results.get("total_grant_and_tax_benefits"),
                        "Final Net Project Cost (Year 1)": final_results.get("final_net_cost")
                    },
                    "Performance Metrics": {
                        "Annual Savings": calc_results.get("financials", {}).get('total_annual_savings'),
                        "Simple Payback (Years)": final_results.get("final_payback"),
                        "25-Year ROI (%)": calc_results.get("financials", {}).get("roi_percent_25_yr")
                        #"Simple ROI (%)": final_results.get("final_roi")
                    }
                }
                
                # Remove any entries with None values for a cleaner prompt
                # This is a good practice to avoid sending empty fields to the AI
                def clean_dict(d):
                    if not isinstance(d, dict):
                        return d
                    return {k: clean_dict(v) for k, v in d.items() if v is not None}

                cleaned_project_summary = clean_dict(project_summary_for_ai)
                
                # Call the AI service with the rich, detailed data
                advanced_analysis = analyze_financial_data_with_claude(cleaned_project_summary)
                
                # Display the structured response from Claude
                if "error" in advanced_analysis:
                    st.error(f"AI Analysis Error: {advanced_analysis['error']}")
                    if "raw_response" in advanced_analysis:
                        st.code(advanced_analysis["raw_response"], language="text")
                else:
                    st.markdown(f"**Executive Summary:** {advanced_analysis.get('executive_summary', 'N/A')}")
                    
                    st.markdown("**Key Opportunities:**")
                    for opp in advanced_analysis.get('key_opportunities', ['N/A']):
                        st.markdown(f"- {opp}")
                    
                    st.markdown(f"**Primary Risks:**")
                    for risk in advanced_analysis.get('primary_risks', ['N/A']):
                        st.markdown(f"- {risk}")
                    
                    st.markdown(f"**Mitigation Strategies:**")
                    for strat in advanced_analysis.get('mitigation_strategies', ['N/A']):
                        st.markdown(f"- {strat}")

    # Navigation
    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Multi-Grant Stacker", use_container_width=True, key="s6_back_to_s5_final"):
            set_screen_and_rerun("multi_grant_stacker")
    with nav_col2:
        if st.button("Continue to Export Package ➡️", type="primary", use_container_width=True, key="s6_to_s7_continue"):
            set_screen_and_rerun("export_package")
    
    return None


# ========== Screen 7: Export Package ==========
def display_export_package_screen():
    st.title("📤 Export Package (New S7)")
    st.markdown("Download your customized project package.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'export_package')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    st.info("TODO WEEK 3: Implement PDF/document generation and download/email functionality here.")
    
    st.download_button(
        label="📥 Download Project Summary (Placeholder TXT)",
        data="This is a placeholder for your Sharkbite project summary.",
        file_name="Sharkbite_Project_Summary.txt",
        mime="text/plain"
    )

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Final Dashboard", use_container_width=True, key="s7_back_to_s6_final"):
            return "final_incentive_dashboard"
    with nav_col2:
        if st.button("🎉 Start New Project / Home", type="primary", use_container_width=True, key="s7_finish_home"):
            # Clear relevant session state for a new project
            st.session_state.form_data = {}
            st.session_state.calculator_results_display = None
            st.session_state.reap_score_details = None 
            # Keep login state
            return "unified_intake" # Go back to the new start screen
    return None