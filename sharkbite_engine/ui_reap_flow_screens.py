import streamlit as st
from sharkbite_engine.utils import (
    calculate_detailed_reap_score,
    generate_progress_bar_markdown,
    check_incentive_eligibility,
    perform_final_incentive_stack_calculations # The master calculator for Screen 6
)
from sharkbite_engine.ui_unified_intake_screen import SCREEN_FLOW_MAP_NEW
from sharkbite_engine.incentive_definitions import INCENTIVE_PROGRAMS


# --- Helper Function to Navigate ---
def set_screen_and_rerun(screen_name):
    st.session_state.current_screen = screen_name
    st.rerun()


# ========== Screen 3: Incentive Preview ==========
def display_incentive_preview_screen():
    st.title("🎁 Incentive Preview (New S3)")
    st.markdown("Based on your initial inputs, here are the grant, loan, and tax programs you may be eligible for. Select which ones you'd like to model in the next step.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'incentive_preview')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data
    calculator_financials = st.session_state.get("calculator_results_display", {}).get("financials", {})

    st.subheader("👀 Summary from Solar & Battery Calculator")
    col_rev1, col_rev2 = st.columns(2)
    with col_rev1:
        st.metric("Calculator System Size", f"{form_data.get('calculator_refined_system_size_kw', 'N/A')} kW")
        st.metric("Calculator Est. Annual Production", f"{st.session_state.get('calculator_results_display',{}).get('ac_annual', 'N/A'):,.0f} kWh")
    with col_rev2:
        st.metric("Calculator Est. Annual Savings", f"${calculator_financials.get('annual_savings_calculator', 'N/A'):,.0f}")
        st.metric("Calculator Est. Net Cost", f"${calculator_financials.get('net_cost_calculator', 'N/A'):,.0f}")

    with st.spinner("Checking your eligibility for dozens of programs..."):
        eligible_programs = check_incentive_eligibility(form_data)
        st.session_state.eligible_programs = eligible_programs
    
    st.subheader("⭐ Potentially Eligible Programs")
    st.caption("Select the incentives you wish to include in your final financial model 👇")

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
            form_data['system_cost_for_reap'] = calculator_financials.get("total_cost_with_battery")
            form_data['system_size_for_reap'] = form_data.get("calculator_refined_system_size_kw")
            form_data['technology_for_reap'] = "Solar PV" # Assuming from calculator context
            set_screen_and_rerun("reap_deep_dive")

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
    st.write(f"System Size: {form_data.get('system_size_for_reap', 'N/A')} kW")
    st.write(f"Estimated Project Cost (CapEx): ${form_data.get('system_cost_for_reap', 0):,.0f}")

    # === Collect all inputs needed for the simplified REAP score ===
    #reap_tab1, reap_tab2 = st.columns([5, 3], gap="small")
    st.subheader("REAP Eligibility Details")
    with st.container(border=True):
        reap_col1, reap_col2 = st.columns(2)
        with reap_col1:
            form_data['reap_business_name'] = st.text_input(
            "Official Business Name for REAP Application",
            value=form_data.get('unified_business_type', 'N/A'), # Pre-fill from S1
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

        #st.subheader("Document Upload Simulation")
        
        form_data['mock_doc_score_reap'] = st.slider("Simulate Document Score (0-20 pts)", 0, 20, 10,
                                                    key="s4_doc_score_slider_live",
                                                    help="This simulates the points awarded for having documents like audits, permits, and deeds ready."
                                                    )
        st.info("👇 Your REAP score is affected by the completeness of your documentation.")
   
    #st.markdown('---')
    st.subheader("Live REAP Score Preview")
    with st.container(border=True):

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
            set_screen_and_rerun("multi_grant_stacker") # New Screen 5
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

    with st.form("multi_grant_form"):
         
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
            
        submitted = st.form_submit_button("Continue to Final Financial Dashboard ➡️", type="primary")
        if submitted:
            set_screen_and_rerun("final_incentive_dashboard")


    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to REAP Deep Dive", use_container_width=True, key="s5_back_to_s4_final"):
        set_screen_and_rerun("reap_deep_dive")

    return None


# ========== Screen 6: Final Incentive Dashboard (Now reads pre-calculated results) ==========
def display_final_incentive_dashboard_screen():
    st.title("💵 Final Incentive Dashboard (New S6)")
    st.markdown("This is your consolidated financial summary, incorporating all selected and calculated incentives based on the **Sharkbite Order of Operations**.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'final_incentive_dashboard')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    form_data = st.session_state.form_data
    
    # --- Performs all the master calculations directly on this screen when it loads ---
    with st.spinner("Performing final compliance checks and financial modeling..."):
        final_results = perform_final_incentive_stack_calculations(form_data)
        # Store results in session state in case we need them on the export screen
        st.session_state.final_financial_results = final_results

    if not final_results:
        st.error("Financial results have not been calculated. Please complete the 'Multi-Grant Stacker' step.")
        if st.button("⬅️ Go Back", key="s6_back_no_results"):
            set_screen_and_rerun("multi_grant_stacker")
        return None

    # Displaying the results from the `final_results` dictionary
    st.subheader("✅ Final Compliant Incentive Stack Summary")
    
    with st.container(border=True):
        st.write(f"**Total Project Cost (CapEx):** ${final_results.get('total_project_cost', 0):,.2f}")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("🏆 REAP Grant (Adjusted)", f"${final_results.get('reap_grant_final', 0):,.0f}")
            st.metric("💰 Federal ITC (Total)", f"${final_results.get('total_itc_value', 0):,.0f}")
        with col2:
            st.metric("📉 MACRS + Bonus Dep. (Y1 Tax Benefit)", f"${final_results.get('year_1_depreciation_tax_benefit', 0):,.0f}" if final_results.get('year_1_depreciation_tax_benefit',0) > 0 else "N/A")
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
        fin_col1, fin_col2, fin_col3 = st.columns(3)
        
        net_cost_final = final_results.get('final_net_cost', 0)
        final_roi = final_results.get('final_roi', 0)
        final_payback = final_results.get('final_payback', float('inf'))
        cash_positive_note = final_results.get('cash_positive_note', "")

        # Final Net Cost
        # Show $0 if it's negative, because you don't have a "negative cost" in reality, you have positive cashflow.
        display_net_cost = max(0, net_cost_final)
        fin_col1.metric("💸 Final Net Project Cost (Y1)", f"${display_net_cost:,.0f}")
        
        # Final ROI
        if final_roi == float('inf'):
            roi_display_text = "Immediate"
            fin_col2.metric("🤑 Final ROI (Simple)", roi_display_text)
        else:
            roi_display_text = f"{final_roi:.1f}%"
            fin_col2.metric("🤑 Final ROI (Simple)", roi_display_text)

        # Final Payback
        if final_payback == 0.0:
            payback_display_text = "Immediate"
            fin_col3.metric("⏱️ Final Payback (Years)", payback_display_text)
        elif final_payback == float('inf'):
            payback_display_text = "N/A (No Savings)"
            fin_col3.metric("⏱️ Final Payback (Years)", payback_display_text)
        else:
            payback_display_text = f"{final_payback:.1f}"
            fin_col3.metric("⏱️ Final Payback (Years)", payback_display_text)

        # If there's a cash positive note, display it prominently
        if cash_positive_note:
            st.success(f"🎉 **Excellent Outcome:** {cash_positive_note}", icon="💰")
    
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
    
    st.info("📌 TODO WEEK 3: Implement PDF/document generation and download/email functionality here.")
    # Display key summary numbers again if helpful
    
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