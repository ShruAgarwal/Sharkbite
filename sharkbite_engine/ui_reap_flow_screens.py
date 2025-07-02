import streamlit as st
#import pandas as pd  # If needed for displaying tables
from sharkbite_engine.utils import (
    BASE_ITC_RATE, MOCK_NON_REAP_INCENTIVES_PREVIEW, calculate_simplified_reap_score,
    ELIGIBILITY_CHECKS_UNIFIED_INTAKE, # For rural/energy community checks
    REAP_GRANT_CAPS_BY_TECH,
    generate_progress_bar_markdown
    # ... import functions for DETAILED MACRS and Order of Operations for Screen 5 later
)
from sharkbite_engine.ui_unified_intake_screen import SCREEN_FLOW_MAP_NEW


# ========== Screen 3: Incentive Preview ==========
def display_incentive_preview_screen():
    st.title("🎁 Incentive Preview (New S3)")
    st.markdown("""Based on your initial inputs, here's a high-level look at potential incentives.
                Let's dive deeper to find out exactly how much you could save!""")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'incentive_preview')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data
    # calculator_financials are the results from Screen 2's simplified calculations
    calculator_financials = st.session_state.get("calculator_results_display", {}).get("financials", {})


    st.subheader("👀 Summary from Solar & Battery Calculator")
    # ... (Display key metrics from calculator_financials as in previous response) ...
    col_rev1, col_rev2 = st.columns(2)
    with col_rev1:
        st.metric("Calculator System Size", f"{form_data.get('calculator_refined_system_size_kw', 'N/A')} kW")
        st.metric("Calculator Est. Annual Production", f"{st.session_state.get('calculator_results_display',{}).get('ac_annual', 'N/A'):,.0f} kWh")
    with col_rev2:
        st.metric("Calculator Est. Annual Savings", f"${calculator_financials.get('annual_savings_calculator', 'N/A'):,.0f}")
        st.metric("Calculator Est. Net Cost", f"${calculator_financials.get('net_cost_calculator', 'N/A'):,.0f}")


    st.subheader("Potential Additional Incentives to Explore")
    # ... (Display potential for ITC, REAP using simplified score, State/Utility, MACRS as in previous response) ...
    st.write(f"- **Federal ITC:** Up to {BASE_ITC_RATE*100:.0f}% of system cost, plus potential bonuses.")
    
    zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    is_rural_mock_val = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("rural") > 0
    is_ec_mock_val = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("energy community") > 0

    # Simplified REAP Score Preview (using data from form_data, some might be defaults)
    reap_preview_inputs = {
        "q7_reap_funding_history": form_data.get("reap_funding_history_s1", "First-time applicant"), # Default if not collected yet
        "q4_ghg_emissions_toggle": form_data.get("q4_ghg_emissions", True), # Default
        "q2_project_type_reap_for_scoring": "Renewable Energy System (RES)" if form_data.get("calculator_refined_system_size_kw",0)>0 else "Energy Efficiency Improvement (EEI)",
        "q3_primary_technology_for_scoring": "Solar PV" # Usually Solar PV from calculator
    }
    _, _, reap_norm_score, _ = calculate_simplified_reap_score(reap_preview_inputs, is_rural_mock_val, is_ec_mock_val, 0)
    st.write(f"- **USDA REAP Grant:** Potential eligibility (Preview Score: {reap_norm_score}/100).")
    st.write("- **State & Utility Rebates:** Varies by location.")
    st.write("- **Accelerated Depreciation (MACRS):** Significant tax benefits for businesses (detailed calculation next).")

    st.markdown("---")
    st.warning("The figures above are high-level. The next steps will refine these based on detailed eligibility and accurate financial modeling.", icon="💡")

    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Solar & Battery Calculator", use_container_width=True, key="s3_back_to_s2"):
            return "solar_battery_calculator"
    with nav_col2:
        if st.button("Unlock Full Incentive Package (REAP Deep Dive) ➡️", type="primary", use_container_width=True, key="s3_to_s4_continue"):
            # Pre-fill form_data for REAP intake (New Screen 4)
            form_data['q1_biz_structure'] = form_data.get("unified_business_type") # From S1
            form_data['address_for_reap'] = form_data.get("unified_address_zip") # From S1
            form_data['system_cost_for_reap'] = calculator_financials.get("total_cost_with_battery") # From S2
            form_data['system_size_for_reap'] = form_data.get("calculator_refined_system_size_kw") # From S2
            form_data['technology_for_reap'] = "Solar PV" # Assuming this from calculator context for now
            # ... other necessary pre-fills ...
            return "reap_deep_dive_documents" # New Screen 4
    return None


# ========== Screen 4: REAP Deep Dive & Document Upload ==========
def display_reap_deep_dive_screen():
    st.title("📝 REAP Grant Application & Document Upload (New S4)")
    st.markdown("Provide detailed information for your REAP Grant application and upload necessary documents.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'reap_deep_dive_documents')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    form_data = st.session_state.form_data
    st.subheader("👀 Pre-filled from Calculator & Initial Intake")
    st.write(f"Business Type: {form_data.get('q1_biz_structure', 'N/A')}")
    st.write(f"Project Location (ZIP from Address): {form_data.get('address_for_reap', 'N/A')}")
    st.write(f"Technology: {form_data.get('technology_for_reap', 'Solar PV')}")
    st.write(f"System Size: {form_data.get('system_size_for_reap', 'N/A')} kW")
    st.write(f"Estimated Project Cost (CapEx): ${form_data.get('system_cost_for_reap', 0):,.0f}")

    # === HERE WE WOULD INTEGRATE OUR ORIGINAL REAP INTAKE FORM UI ===
    # Collect all inputs needed for the simplified REAP score from "FORMULAS" PDF.
    # --- ADDED: REAP-SPECIFIC INPUTS (from old wireframe screens) ---
    st.subheader("REAP Eligibility Details")

    reap_col1, reap_col2 = st.columns(2)
    with reap_col1:
        # These inputs are needed for the simplified REAP scoring formula
        reap_history_options = ["First-time applicant", "Prior award (2+ years ago)", "Recent award (last 2 years)"]
        current_reap_history = form_data.get("q7_reap_funding_history", reap_history_options[0])
        form_data["q7_reap_funding_history"] = st.radio(
            "Have you received REAP funding before?",
            options=reap_history_options,
            index=reap_history_options.index(current_reap_history),
            key="s4_reap_history", horizontal=True,
            help="First-time applicants are prioritized for REAP scoring."
        )

    with reap_col2:
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
    
    form_data["q4_ghg_emissions"] = st.toggle(
        "Does this project result in zero GHG emissions?",
        value=form_data.get("q4_ghg_emissions", True),
        key="s4_ghg_toggle",
        help="Zero-emissions projects get a scoring bonus."
    )
    
    st.subheader("Document Upload (Simulated for Week 2)")
    st.info("TODO: Implement full REAP intake form and document upload simulation here.")
    
    # Mock doc score for now
    form_data['mock_doc_score_reap'] = st.slider("Simulate Document Score (0-20 pts)", 0, 20, 10, key="s4_doc_score_slider")

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to Incentive Preview", use_container_width=True, key="s4_back_to_s3"):
            return "incentive_preview"
    with nav_col2:
        if st.button("Continue to Final Financial Dashboard ➡️", type="primary", use_container_width=True, key="s4_to_s5_continue"):
            # Recalculate REAP score with potentially new inputs from this screen
            zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
            is_rural = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("rural") > 0
            is_ec = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("energy community") > 0
            
            reap_score_final, _, _, _ = calculate_simplified_reap_score(
                form_data, is_rural, is_ec, form_data.get('mock_doc_score_reap', 0)
            )
            form_data['final_reap_score_for_dashboard'] = reap_score_final
            
            # Calculate REAP Grant Amount
            system_cost_for_reap = form_data.get("reap_specific_capex", form_data.get('calculator_system_cost_output', 0))
            tech_for_reap = form_data.get("q2_project_type_reap", "Renewable Energy System (RES)")
            max_cap = REAP_GRANT_CAPS_BY_TECH.get(tech_for_reap, 500000)
            form_data['reap_grant_amount_calculated'] = min(0.5 * system_cost_for_reap, max_cap)



            # is_rural = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(form_data.get('address_for_reap','').split(',')[-1].strip()[:5], {}).get("text", "").lower().count("rural") > 0
            # is_ec = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(form_data.get('address_for_reap','').split(',')[-1].strip()[:5], {}).get("text", "").lower().count("energy community") > 0
            
            # reap_score_final, _, _, _ = calculate_simplified_reap_score(
            #     form_data, # Pass the full form_data which now includes REAP specific answers
            #     is_rural, is_ec,
            #     form_data.get('mock_doc_score_reap', 0)
            # )
            # form_data['final_reap_score_for_dashboard'] = reap_score_final
            
            # # Calculate REAP Grant Amount (using formula from "Formulas" PDF)
            # # final_grant = min(0.5 * system_cost, max_cap_by_tech[technology])
            # system_cost_for_reap_grant = form_data.get('system_cost_for_reap', 0)
            # tech_for_reap_grant = form_data.get('technology_for_reap', "Other") # Use a default if not specific
            
            # max_cap = REAP_GRANT_CAPS_BY_TECH.get(tech_for_reap_grant, REAP_GRANT_CAPS_BY_TECH["Other"])
            # form_data['reap_grant_amount_calculated'] = min(0.5 * system_cost_for_reap_grant, max_cap)

            return "final_incentive_dashboard" # New Screen 5
    return None


# ========== Screen 5: Final Incentive Dashboard (Detailed MACRS, Order of Ops) ==========
def display_final_incentive_dashboard_screen():
    st.title("💵 Final Incentive Dashboard (New S5)")
    st.markdown("Full financial picture using **detailed MACRS** and precise incentive calculations following the **Sharkbite Order of Operations**.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'final_incentive_dashboard')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")

    form_data = st.session_state.form_data
    # calculator_financials = st.session_state.get("calculator_financials_results", {}) # From S2 (simplified)

    st.subheader("Key Project & Financial Data (Recap & Refined)")
    total_project_cost = form_data.get('system_cost_for_reap', 0) # This is CapEx from Calculator
    st.write(f"**Total Project Cost (CapEx):** ${total_project_cost:,.0f}")
    
    # --- Apply Sharkbite Order of Operations ---
    # Step 1: CapEx (already have total_project_cost)

    # Step 2: REAP Grant Amount (already calculated when moving from S4)
    reap_grant_calculated = form_data.get('reap_grant_amount_calculated', 0)
    st.write(f"**1. Calculated REAP Grant:** ${reap_grant_calculated:,.0f}")

    # Step 3: Calculate ITC (based on full gross project cost, before REAP)
    # ITC = 30% * CapEx (plus bonuses)
    #base_itc_on_capex = total_project_cost * BASE_ITC_RATE # BASE_ITC_RATE = 0.30
    
    # Add ITC Bonuses (Energy Community, etc. - based on ZIP and other factors)
    # These bonus percentages would come from a more detailed config or direct user selection
    # For now, using mock potential from utils
    total_itc_bonus_rate = 0
    zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5] # From S1
    is_ec_mock_val = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("energy community") > 0
    if is_ec_mock_val:
        total_itc_bonus_rate += MOCK_NON_REAP_INCENTIVES_PREVIEW.get("bonus_energy_community_potential",0)
    # Add other bonuses here if applicable (e.g. Domestic Content - future)
    
    total_itc_value = (BASE_ITC_RATE + total_itc_bonus_rate) * total_project_cost
    st.write(f"**2. Calculated Total ITC (incl. bonuses):** ${total_itc_value:,.0f} (Rate: {(BASE_ITC_RATE + total_itc_bonus_rate)*100:.0f}%)")

    # Step 4: Federal Share Compliance Check
    federal_share = (reap_grant_calculated + total_itc_value) / total_project_cost if total_project_cost > 0 else 0
    st.write(f"**3. Federal Share Check:** {federal_share:.2%} (Target: <= 50%)")
    if federal_share > 0.50:
        st.error(f"🚨 AI WARNING: Federal share ({federal_share:.2%}) exceeds 50%! You may need to reduce REAP grant request or forgo some ITC bonuses to be compliant.", icon="⚖️")
        # TODO WEEK 2: Add logic for user to adjust REAP or ITC bonuses here
        st.write("Action: For this demo, assuming user reduces REAP to meet cap if needed.")
        # Corrected REAP if over cap (simplified correction for demo)
        if federal_share > 0.50:
            max_allowed_reap_plus_itc = 0.50 * total_project_cost
            adjusted_reap_grant = max(0, max_allowed_reap_plus_itc - total_itc_value)
            if adjusted_reap_grant < reap_grant_calculated:
                st.warning(f"REAP Grant adjusted from ${reap_grant_calculated:,.0f} to ${adjusted_reap_grant:,.0f} to meet 50% Federal Share Cap.", icon="🔧")
                reap_grant_calculated = adjusted_reap_grant
                federal_share = (reap_grant_calculated + total_itc_value) / total_project_cost if total_project_cost > 0 else 0
                st.write(f"   New Federal Share: {federal_share:.2%}")


    # Step 5: Calculate Correct Depreciable Basis
    itc_basis_reduction_amount = 0.5 * total_itc_value
    correct_depreciable_basis = total_project_cost - itc_basis_reduction_amount
    st.write(f"**4. Correct Depreciable Basis (after ITC reduction):** ${correct_depreciable_basis:,.0f}")

    # Step 6: Apply MACRS and Bonus Depreciation (DETAILED - TODO FOR WEEK 2)
    st.subheader("Detailed Depreciation Benefits (Week 2 Implementation)")
    st.write(f"   - Depreciable Basis for MACRS: ${correct_depreciable_basis:,.0f}")
    
    # ToDo WEEK 2: Implement 5-year MACRS schedule + Bonus Depreciation logic here
    # For now, use a placeholder or the simplified one for display continuity
    #macrs_year1_detailed_placeholder = correct_depreciable_basis * 0.20 # Example for 5yr MACRS Y1 (no bonus)
    bonus_dep_rate_for_current_year = 0.80 # Example for 2023, needs to be dynamic
    bonus_dep_value_placeholder = correct_depreciable_basis * bonus_dep_rate_for_current_year
    remaining_basis_for_macrs = correct_depreciable_basis - bonus_dep_value_placeholder
    macrs_year1_after_bonus_placeholder = remaining_basis_for_macrs * 0.20 # MACRS on remaining
    total_year1_depreciation_benefit_placeholder = (bonus_dep_value_placeholder + macrs_year1_after_bonus_placeholder) * 0.21 # Assuming 21% tax rate

    st.write(f"   - *Placeholder* Year 1 Bonus Dep. Value (@{bonus_dep_rate_for_current_year*100}%): ${bonus_dep_value_placeholder:,.0f}")
    st.write(f"   - *Placeholder* Year 1 MACRS Value (on remaining): ${macrs_year1_after_bonus_placeholder:,.0f}")
    st.write(f"   - *Placeholder* Year 1 Total Depreciation Tax Benefit: ${total_year1_depreciation_benefit_placeholder:,.0f}")
    form_data['final_year1_depreciation_benefit'] = total_year1_depreciation_benefit_placeholder # Store for summary


    # --- Final Summary Metrics using detailed calculations ---
    st.subheader("Final Financial Summary")
    # Net Cost = CapEx - REAP - ITC - Year 1 Dep Benefit (if user type is commercial)
    net_cost_final = total_project_cost - reap_grant_calculated - total_itc_value
    if form_data.get("unified_business_type") == "Commercial / Business":
        net_cost_final -= total_year1_depreciation_benefit_placeholder # Subtracting the tax *benefit*
    
    annual_savings_final = st.session_state.get("calculator_results_display", {}).get("financials", {}).get('annual_savings_calculator',0) # From S2 calculator
    
    roi_final = (annual_savings_final / net_cost_final) * 100 if net_cost_final > 0 else float('inf') if annual_savings_final > 0 else 0
    payback_final = net_cost_final / annual_savings_final if annual_savings_final > 0 else float('inf')

    # fin_col1, fin_col2, fin_col3 = st.columns(3)
    # fin_col1.metric("Final Net Project Cost (after all incentives)", f"${net_cost_final:,.0f}")
    # fin_col2.metric("Final ROI (Simple)", f"{roi_final:.1f}%")
    # fin_col3.metric("Final Payback (Years)", f"{payback_final:.1f}" if payback_final != float('inf') else "N/A")
    st.metric("Final Net Project Cost (after all incentives)", f"${net_cost_final:,.0f}")
    st.metric("Final ROI (Simple)", f"{roi_final:.1f}%")
    st.metric("Final Payback (Years)", f"{payback_final:.1f}" if payback_final != float('inf') else "N/A")

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅️ Back to REAP Deep Dive", use_container_width=True, key="s5_back_to_s4"):
            return "reap_deep_dive_documents"
    with nav_col2:
        if st.button("Continue to Export Package ➡️", type="primary", use_container_width=True, key="s5_to_s6_continue"):
            return "export_package"
    return None


# ========== Screen 6: Export Package ==========
def display_export_package_screen():
    st.title("📤 Export Package (New S6)")
    st.markdown("Download your customized project package.")
    progress_bar_md = generate_progress_bar_markdown(SCREEN_FLOW_MAP_NEW, 'export_package')
    st.markdown(progress_bar_md, unsafe_allow_html=True)
    st.markdown("---")
    
    st.info("TODO WEEK 3: Implement PDF/document generation and download/email functionality here.")
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
        if st.button("⬅️ Back to Final Dashboard", use_container_width=True, key="s6_back_to_s5"):
            return "final_incentive_dashboard"
    with nav_col2:
        if st.button("🎉 Start New Project / Home", type="primary", use_container_width=True, key="s6_finish_home"):
            # Clear relevant session state for a new project
            st.session_state.form_data = {}
            st.session_state.calculator_results_display = None
            st.session_state.reap_score_details = None 
            # Keep login state
            return "unified_intake" # Go back to the new start screen
    return None