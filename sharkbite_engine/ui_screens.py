import streamlit as st
from sharkbite_engine.utils import (
    AI_HELPER_TEXTS, ELIGIBILITY_CHECK_TEXTS,
    REAP_INTAKE_DEFINITIONS_PAGE3,
    calculate_reap_score_from_formulas, calculate_optional_reap_grant_estimate,
    MOCK_NON_REAP_INCENTIVES_DATA
)

def set_screen_and_rerun(screen_name):
    st.session_state.current_screen = screen_name
    st.rerun()

def display_header():
    st.markdown(
        """
        <style>

            div.st-emotion-cache-8atqhb.e1q5ojhd0{
                display: flex;
                justify-content: center;
                width: 100%;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.image("sk_logo.png", width = 350)

    #st.markdown("<h1 style='text-align: center; color: #00447C;'>🦈 SHARKBITE</h1>", unsafe_allow_html=True) # Sea-blue
    st.markdown("<h3 style='text-align: center; font-style: italic; color: #008080;'>🌟 Find Clean Energy Funding & Incentives That Work For Your Project</h3>", unsafe_allow_html=True)
    st.caption("---")

# ================ MAIN UI SCREENS LOGIC GOES HERE ================

def display_welcome_screen_ui():
    display_header()
    col1, col2 = st.columns(2)

    # Sidebar is now handled in main app globally for logged-in users
    if st.session_state.get('logged_in', False):
        with col1:
            if st.button("Start New Project", type="primary", icon=":material/rocket_launch:", use_container_width=True,
                key="loggedin_start_new_project_main_ui"):
                st.session_state.form_data = {} 
                set_screen_and_rerun('business_basics')

        with col2:
            # "Continue Saved Project" button can remain as a placeholder if desired
            if st.button("Continue Saved Project", use_container_width=True, key="btn_continue_saved_loggedin_ui"):
                st.toast("⏳ This feature for loading saved projects will be available in a future version.")

    else: # Not logged in
        st.markdown("### :material/lock: Let's Get Started")
        signup_tab, login_tab = st.tabs(["Sign Up for a new account", "Login to existing account"])
        with signup_tab:
            # For the MVP, we don't auto-login on signup for simplicity
            with st.form("signup_form_ui"): # Unique key for form
                new_username = st.text_input("Create a unique username", key="ui_signup_user_input")
                new_password = st.text_input("Create a password", type="password", key="ui_signup_pass_input")
                signup_button = st.form_submit_button("Sign Up", icon=":material/add_circle:", type="primary", use_container_width=True)
                if signup_button:
                    if new_username and new_password:
                        st.success(f"Welcome, {new_username}! Please log in with new credentials.", icon=":material/thumb_up:")
                    else:
                        st.error("Please fill up all the fields.", icon=":material/error:")
        with login_tab:
            with st.form("login_form_ui"): # Unique key for form
                username = st.text_input("Enter your unique username (demo: user)", key="ui_login_user_input")
                password = st.text_input("Enter your password (demo: pass)", type="password", key="ui_login_pass_input")
                login_button = st.form_submit_button("Login", type="primary", icon=":material/login:", use_container_width=True)
                if login_button:
                    if username and password: 
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        set_screen_and_rerun('welcome') # Rerun to show logged-in view & persistent sidebar
                    else:
                        st.error("Please enter correct username and password.", icon=":material/warning:")

    # This section now shown to everyone, prompting login/signup if not logged in
    st.info("⚡ Answer simple questions to unlock:\n- REAP grants up to $1M\n- Tax credits up to 30%\n- Bonus credits, depreciation & more")
    if st.button("Watch Demo: How It Works", type="secondary", icon=":material/slideshow:", use_container_width=True, key="btn_watch_demo_ui_main"):
        st.toast("✨ The demo video link will be placed here!")


def display_form_page_from_ui(page_title, progress_caption, section_title, item_definitions, prev_screen_target, next_screen_target, next_button_text):
    project_name_display = st.session_state.form_data.get('business_name', "Your Project")
    st.header(f"{page_title}: {project_name_display if page_title != 'Project & Business Basics' else ''}")
    
    # --- Progress Badge Implementation ---
    steps_map = {
        'business_basics': 1, 'project_details': 2, 'reap_score_preview': 3, 'incentive_stack_mock': 4, 'summary_dashboard': 5
    }
    total_steps = 5 # To update when more screens are added to the main flow
    current_step_num = steps_map.get(st.session_state.current_screen, 0)
    
    progress_items = ["BASICS", "PROJECT DETAILS", "SCORE PREVIEW", "INCENTIVE STACK", "SUMMARY"]
    progress_display_list = []
    for i, item_text in enumerate(progress_items):
        step_num_for_item = i + 1
        if step_num_for_item == current_step_num:
            progress_display_list.append(f":violet-badge[:material/screen_record: Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}]")
        else:
            progress_display_list.append(f"Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}")
    
    st.markdown("  >  ".join(progress_display_list), unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"#### {section_title}")

    cols = st.columns(2) 
    col_idx = 0
    for item_idx, item in enumerate(item_definitions):
        current_col = cols[col_idx % 2]
        with current_col:
            input_key = f"{item['key']}_{st.session_state.current_screen}" # Ensure unique key per screen per item
            current_value_from_state = st.session_state.form_data.get(item["id"])
            default_value_from_def = item.get("value")

            if item["id"] == "q4_ghg_emissions" and item_definitions is REAP_INTAKE_DEFINITIONS_PAGE3:
                # Default toggle to True (Yes) if no value in session state or definition
                toggle_default = True if current_value_from_state is None and default_value_from_def is None else \
                                (current_value_from_state if isinstance(current_value_from_state, bool) else \
                                (default_value_from_def if isinstance(default_value_from_def, bool) else True))

                toggle_val_str = st.toggle(
                    item["label"],
                    value=toggle_default,
                    key=input_key,
                    help=AI_HELPER_TEXTS.get(item["id"])
                )
                # Store as Yes/No string for consistency if needed by scoring
                st.session_state.form_data[item["id"]] = "Yes" if toggle_val_str else "No"
            
            elif item["widget"] == st.number_input:
                val_to_use = current_value_from_state if current_value_from_state is not None else default_value_from_def
                st.session_state.form_data[item["id"]] = item["widget"](item["label"], min_value=item.get("min_value", 0.0),
                                                                        value=float(val_to_use if val_to_use is not None else 0.0),
                                                                        step=item.get("step", 1.0),
                                                                        key=input_key, help=AI_HELPER_TEXTS.get(item["id"]))
            elif item["widget"] == st.selectbox:
                options = item.get("options", [])
                val_to_use = current_value_from_state if current_value_from_state in options else (options[0] if options else None)
                idx = options.index(val_to_use) if val_to_use in options else 0
                st.session_state.form_data[item["id"]] = item["widget"](item["label"], options=options, index=idx,
                                                                        key=input_key, help=AI_HELPER_TEXTS.get(item["id"]))
            elif item["widget"] == st.text_input:
                val_to_use = current_value_from_state if current_value_from_state is not None else (default_value_from_def if default_value_from_def is not None else "")
                st.session_state.form_data[item["id"]] = item["widget"](item["label"], value=val_to_use,
                                                                        key=input_key, help=AI_HELPER_TEXTS.get(item["id"]))
            elif item["widget"] == st.radio:
                options = item.get("options", [])
                val_to_use = current_value_from_state if current_value_from_state in options else (options[0] if options else None)
                idx = options.index(val_to_use) if val_to_use in options else item.get("index", 0) # Use definition index if no state
                st.session_state.form_data[item["id"]] = item["widget"](item["label"], options=options, index=idx,
                                                                        key=input_key, horizontal=item.get("horizontal", False), help=AI_HELPER_TEXTS.get(item["id"]))
        col_idx +=1
    
    if st.session_state.current_screen == 'business_basics':
        st.info(f"💡 AI TIP: {AI_HELPER_TEXTS.get('q1_biz_structure')}", icon="🧠")
    
    elif st.session_state.current_screen == 'project_details':
        zip_code_val = st.session_state.form_data.get("q5_zip_code_reap", "")
        zip_info = ELIGIBILITY_CHECK_TEXTS.get(zip_code_val, ELIGIBILITY_CHECK_TEXTS["default"])
        if zip_info["type"] == "success":
            st.success(f"🔍 ELIGIBILITY CHECK: {zip_info['text']}", icon="✅")
        elif zip_info["type"] == "warning":
            st.warning(f"🔍 ELIGIBILITY CHECK: {zip_info['text']}", icon="⚠️")
        else:
            st.info(f"🔍 ELIGIBILITY CHECK: {zip_info['text']}", icon="🗺️")

    st.markdown("<br>", unsafe_allow_html=True) 
    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button(f"⬅️ Back to {prev_screen_target.replace('_', ' ').title() if prev_screen_target else 'Welcome'}",
            use_container_width=True, key=f"btn_back_to_{prev_screen_target}_on_{st.session_state.current_screen}"):
            set_screen_and_rerun(prev_screen_target if prev_screen_target else 'welcome')
    
    with nav_cols[1]:
        if st.button(next_button_text, type="primary", icon="➡️", use_container_width=True, key=f"btn_continue_to_{next_screen_target}_on_{st.session_state.current_screen}"):
            if next_screen_target == 'reap_score_preview':
                is_rural_mock = ELIGIBILITY_CHECK_TEXTS.get(st.session_state.form_data.get("q5_zip_code_reap", ""), {}).get("text", "").lower().count("rural") > 0
                is_energy_community_mock = ELIGIBILITY_CHECK_TEXTS.get(st.session_state.form_data.get("q5_zip_code_reap", ""), {}).get("text", "").lower().count("energy community") > 0
                score_data = calculate_reap_score_from_formulas(st.session_state.form_data, is_rural_mock, is_energy_community_mock)
                st.session_state.reap_score_details = {"raw_score_formula": score_data[0], "breakdown_formula": score_data[1], "norm_score_formula": score_data[2], "max_formula_score": score_data[3]}
            
            #elif next_screen_target == 'incentive_stack_mock':

                # system_capacity_str = st.session_state.form_data.get("system_size_kw")
                # zip_code = st.session_state.form_data.get("q5_zip_code_reap")
                    
                # # Ensure system_capacity is a valid number for the API
                # # Reset previous PVWatts results before making a new call
                # st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = None
                # st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = None

                # if NREL_API_KEY_FROM_MAIN and system_capacity_str and zip_code:
                    # try:
                    #     #system_capacity_float = float(system_capacity)
                    #     # pv_value, pv_error = get_solar_production_pvwatts(
                    #     #     NREL_API_KEY_HOLDER,
                    #     #     system_capacity,
                    #     #     zip_code
                    #     # )
                    #     # st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = pv_value
                    #     # st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = pv_error
                    #     # if pv_value:
                    #     #     st.markdown(f"#### ☀️ PVWatts Estimated: {pv_value:,.0f} kWh/yr")
                    #     # else:
                    #     #     st.write(pv_error)

                #     # except ValueError:
                #     #     # st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = None
                #     #     st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = "Invalid system capacity value."
                # else:
                #     st.toast("Skipping PVWatts: API key, incorrect/null system size or ZIP missing.", icon="⚠️")
            set_screen_and_rerun(next_screen_target)


def display_reap_score_preview_screen_from_ui():
    project_name_display = st.session_state.form_data.get('business_name', "Your Project")
    st.header(f"REAP Score Preview: {project_name_display}")
    
    progress_items = ["BASICS", "PROJECT DETAILS", "SCORE PREVIEW", "INCENTIVE STACK", "SUMMARY"]
    current_step_num = 3 # This is the Score Preview screen
    total_steps = 5
    progress_display_list = []
    for i, item_text in enumerate(progress_items):
        step_num_for_item = i + 1
        if step_num_for_item == current_step_num:
            progress_display_list.append(f":violet-badge[:material/screen_record: Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}]")
        else:
            progress_display_list.append(f"Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}")
    st.markdown("  >  ".join(progress_display_list), unsafe_allow_html=True)
    st.markdown("---")

    score_details = st.session_state.reap_score_details
    if not score_details:
        st.error("Score details not available. Please complete project information first.", icon="❗")
        if st.button("⬅️ Back to Project Details", key="btn_p_score_back_error_detailed_ui", use_container_width=True):
            set_screen_and_rerun('project_details')
        return

    raw_score_formula = score_details["raw_score_formula"]
    breakdown_formula = score_details["breakdown_formula"]
    norm_score_formula = score_details["norm_score_formula"]

    st.markdown(f"### 📊 Current Estimated REAP Score (New Formula): **{norm_score_formula}/100**")
    st.progress(norm_score_formula / 100)
    st.caption(f"(Raw formula score: {raw_score_formula}/{score_details['max_formula_score']} points based on simplified scoring logic)")

    competitive_threshold = 75 # As per wireframe
    if norm_score_formula >= competitive_threshold:
        st.success(f"⭐ Competitive Threshold: {competitive_threshold}+ (Your project is showing strong potential!)", icon="🏆")
    else:
        st.warning(f"⭐ Competitive Threshold: {competitive_threshold}+ (Consider improvements to become more competitive)", icon="📉")
    
    # Optional REAP Grant Estimate
    capex = st.session_state.form_data.get("capex_sharkbite") # Ensure this key matches actual collection
    tech = st.session_state.form_data.get("q3_primary_technology")

    if capex and capex > 0 and tech: # Check if capex is positive
        optional_grant_estimate = calculate_optional_reap_grant_estimate(float(capex), tech)
        st.info(f"💡 Optional REAP Grant Estimate (Max): **${optional_grant_estimate:,.0f}** (based on 50% of CapEx & tech caps). This will be refined in Week 2.", icon="💰")
    
    with st.expander("📝 View Simplified Score Breakdown (Formula Based)"):
        for item_detail in breakdown_formula:
            st.markdown(f"- {item_detail}")
    
    st.markdown("---")
    # AI Recommendation from wireframe (Screen 5)
    if norm_score_formula < competitive_threshold:
         st.info("💡 AI RECOMMENDATION: To improve your score, consider if your project aligns with REAP priorities like being a first-time applicant, located in a rural/energy community, or having zero emissions. The 'doc_score' (mocked for Week 1, from document uploads in future) can also add up to 20 points.", icon="🧠")
    else:
        st.info("💡 AI RECOMMENDATION: Your score is competitive! Proceed to explore the incentive stack. Ensure all supporting documents (Screen 4 in full app) are ready for a strong application.", icon="👍")

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("⬅️ Back to Project Details", use_container_width=True, key="btn_p5_back_detailed_ui"):
            set_screen_and_rerun('project_details')
    with nav_cols[1]:
        if st.button("Continue to Incentive Stack (Mock) →", type="primary", use_container_width=True, key="btn_p5_continue_detailed_ui"):
            set_screen_and_rerun('incentive_stack_mock')


def display_incentive_stack_mock_screen(): # New Screen 6 (Mocked for Week 1)
    st.header("🧮 Incentive Stack Builder (Mock - Week 1)")

    progress_items = ["BASICS", "PROJECT DETAILS", "SCORE PREVIEW", "INCENTIVE STACK", "SUMMARY"]
    current_step_num = 4 # This is the Incentive Stack screen
    total_steps = 5
    progress_display_list = []
    for i, item_text in enumerate(progress_items):
        step_num_for_item = i + 1
        if step_num_for_item == current_step_num:
            progress_display_list.append(f":violet-badge[:material/screen_record: Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}]")
        else:
            progress_display_list.append(f"Step [{step_num_for_item}/{total_steps}]: {item_text.upper()}")
    st.markdown("  >  ".join(progress_display_list), unsafe_allow_html=True)
    st.markdown("---")

    st.write("""This screen allows selection of various incentives.
    For Week 1, we're showing mock non-REAP incentive data based on the provided dictionary:
    """)

    st.subheader("Mock ITC & Other Non-REAP Bonuses")
    form_data = st.session_state.form_data
    # Ensure capex_sharkbite is collected, e.g., in a sidebar or earlier form. Default to 0 if not found.
    system_cost = float(form_data.get("capex_sharkbite", 0))

    itc_rate = MOCK_NON_REAP_INCENTIVES_DATA["base_itc_rate"]
    itc_bonus_details = []

    # Check for Energy Community based on ZIP mock data
    is_energy_community_mock = ELIGIBILITY_CHECK_TEXTS.get(form_data.get("q5_zip_code_reap", ""), {}).get("text", "").lower().count("energy community") > 0
    if is_energy_community_mock:
        itc_rate += MOCK_NON_REAP_INCENTIVES_DATA["bonus_energy_community"]
        itc_bonus_details.append(f"+{MOCK_NON_REAP_INCENTIVES_DATA['bonus_energy_community']*100:.0f}% Energy Community Bonus")

    # Check for Zero Emissions from form_data (expecting "Yes" or True from toggle)
    ghg_emissions_val = form_data.get("q4_ghg_emissions")
    if ghg_emissions_val == "Yes" or ghg_emissions_val is True:
        itc_rate += MOCK_NON_REAP_INCENTIVES_DATA["bonus_zero_emissions"]
        itc_bonus_details.append(f"+{MOCK_NON_REAP_INCENTIVES_DATA['bonus_zero_emissions']*100:.0f}% Zero Emissions Bonus")
    
    total_itc_amount = itc_rate * system_cost if system_cost > 0 else 0
    st.metric(label="Estimated Total ITC Rate", value=f"{itc_rate*100:.0f}%")
    if itc_bonus_details:
        st.write("Applied ITC Bonuses:")
        for detail in itc_bonus_details:
            st.markdown(f"  - {detail}")
    st.metric(label="Estimated Total ITC Amount", value=f"${total_itc_amount:,.0f}")


    st.subheader("Mock State Incentives")
    total_state_incentives = 0
    zip_prefix_mock = form_data.get("q5_zip_code_reap", "")[:2] # Using first 2 digits of ZIP
    system_size_kw = float(form_data.get("system_size_kw", 0))

    for incentive in MOCK_NON_REAP_INCENTIVES_DATA["state_incentives"]:
        if incentive.get("applicable_zip_prefix", "") == zip_prefix_mock:
            val = 0
            if incentive["type"] == "per_watt" and system_size_kw > 0:
                # Assuming 'value' is per watt, so multiply by kW * 1000
                val = incentive["value"] * system_size_kw * 1000 
            elif incentive["type"] == "flat":
                val = incentive["value"]
            if val > 0:
                st.write(f"- {incentive['name']}: ${val:,.0f}")
                total_state_incentives += val
    st.metric(label="Total Estimated State Incentives", value=f"${total_state_incentives:,.0f}")
    
    st.markdown("---")
    # Conditional call to PVWatts (e.g., on a button click or if inputs change and API key present)
    # This logic is in display_form_page_from_ui when navigating TO this screen.

    annual_kwh_est_val = st.session_state.form_data.get("estimated_annual_kwh_pvwatts_value")
    
    # Value was successfully retrieved
    if annual_kwh_est_val is not None:
        st.info(f"☀️ PVWatts Estimated Annual Solar Production: **{annual_kwh_est_val:,.0f} kWh/year** (This will drive MACRS, Payback, CO2 Savings in Week 2+).")

    nav_cols = st.columns(2)
    with nav_cols[0]:
        if st.button("⬅️ Back to REAP Score", use_container_width=True, key="btn_stack_back_ui"):
            set_screen_and_rerun('reap_score_preview')
    with nav_cols[1]:
        if st.button("Continue to Summary Dashboard (Week 2+) →", type="primary", use_container_width=True, key="btn_stack_continue_ui"):
            st.info("Summary Dashboard (Screen 7 from wireframe) is a future deliverable.", icon="➡️")
            # set_screen_and_rerun('summary_dashboard')