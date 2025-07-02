import streamlit as st

from sharkbite_engine_v1.ui_screens import (
    set_screen_and_rerun,
    display_welcome_screen_ui,
    display_form_page_from_ui,
    display_reap_score_preview_screen_from_ui,
    display_incentive_stack_mock_screen
)

from sharkbite_engine_v1.utils_v1 import (
    AI_HELPER_TEXTS,
    REAP_INTAKE_DEFINITIONS_PAGE2,
    REAP_INTAKE_DEFINITIONS_PAGE3,
    get_solar_production_pvwatts
)

# --- Page Config ---
st.set_page_config(page_title="🦈 Sharkbite MVP App")

# --- Secrets Management for NREL PVWatts API Key ---
NREL_API_KEY_FROM_SECRETS = None
try:
    NREL_API_KEY_FROM_SECRETS = st.secrets["NREL_API_KEY"]
    if not NREL_API_KEY_FROM_SECRETS:
        # This warning will appear once when the app loads if the key is missing.
        # It's less intrusive than a sidebar warning on every screen.
        st.toast("NREL_API_KEY not found in secrets.toml. PVWatts API calls will be disabled.", icon="🚫")
except Exception:
    if 'secrets_error_shown' not in st.session_state:
        st.toast("Error loading secrets (NREL_API_KEY). PVWatts may be disabled.", icon="⚠️")
        st.session_state.secrets_error_shown = True # Show only once
    NREL_API_KEY_FROM_SECRETS = None


# --- Session State Initialization ---
if 'current_screen' not in st.session_state:
    st.session_state.current_screen = 'welcome'
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'reap_score_details' not in st.session_state:
    st.session_state.reap_score_details = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = "" # Ensure username is initialized


# --- Main App Router ---
if __name__ == "__main__":
    current_screen = st.session_state.current_screen

    # --- API Call Logic Before Rendering Target Screen ---
    # If we just navigated to 'incentive_stack_mock', and haven't processed PVWatts for current form_data yet
    # This check prevents re-calling API on every rerun of the incentive_stack_mock screen
    if st.session_state.current_screen == 'incentive_stack_mock' and \
       (st.session_state.form_data.get("estimated_annual_kwh_pvwatts_value") is None and \
        st.session_state.form_data.get("estimated_annual_kwh_pvwatts_error") is None or \
        st.session_state.form_data.get('_pvwatts_inputs_hash') != hash( (st.session_state.form_data.get("system_size_kw"), st.session_state.form_data.get("q5_zip_code_reap")) ) ):
        
        system_capacity_str = st.session_state.form_data.get("system_size_kw")
        zip_code = st.session_state.form_data.get("q5_zip_code_reap")

        if NREL_API_KEY_FROM_SECRETS and system_capacity_str and zip_code:
            try:
                system_capacity_float = float(system_capacity_str)
                
                api_result_display = get_solar_production_pvwatts(
                    NREL_API_KEY_FROM_SECRETS,
                    system_capacity_float,
                    zip_code
                )
                if isinstance(api_result_display, str): # Error message returned
                    st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = None
                    st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = api_result_display
                else: # Value returned
                    st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = api_result_display
                    st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = None
                # Store a hash of inputs to avoid re-calling if inputs haven't changed
                st.session_state.form_data['_pvwatts_inputs_hash'] = hash( (system_capacity_str, zip_code) )

            except ValueError:
                error_msg = f"Invalid system capacity format: '{system_capacity_str}'. Must be a number."
                st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = None
                st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = error_msg
        else:
            error_msg = "Cannot call PVWatts: NREL API key, system size, or ZIP code is missing."
            st.session_state.form_data["estimated_annual_kwh_pvwatts_value"] = None
            st.session_state.form_data["estimated_annual_kwh_pvwatts_error"] = error_msg

    # --- Persistent Sidebar for Logged-in Users ---
    if st.session_state.get('logged_in', False):
        with st.sidebar:
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
            st.image("logo.png", width = 200)
            st.subheader(f"🦈 Welcome back, {st.session_state.username}!")
            #st.caption("Sharkbite Project Assistant")
            
            # Simplified Navigation based on user flow
            if current_screen != 'welcome':
                if st.button("🏠 Back to Main / Start Over", use_container_width=True, key="sidebar_home_nav"):
                    # Optionally clear form data if "Start Over"
                    # st.session_state.form_data = {}
                    # st.session_state.reap_score_details = None
                    set_screen_and_rerun('welcome') # Go to logged-in welcome screen

            # Global actions
            # if st.button("📋 My Projects (Future)", use_container_width=True, key="sidebar_my_projects"):
            #     st.toast("Feature coming soon!")
            
            if st.button("Logout", icon=":material/logout:", type="primary", use_container_width=True, key="sidebar_logout_nav_main"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.form_data = {} # Clear form on logout
                st.session_state.reap_score_details = None
                set_screen_and_rerun('welcome')
            
            st.markdown("---")
            # Collect capex if user is past welcome and form_data is initialized
            if current_screen not in ['welcome'] and st.session_state.form_data is not None:
                st.subheader("Project CapEx")
                st.session_state.form_data['capex_sharkbite'] = st.number_input(
                    "Total Project CapEx (USD)",
                    min_value=0.0,
                    value=float(st.session_state.form_data.get('capex_sharkbite', 100000.0)),
                    step=1000.0,
                    help=AI_HELPER_TEXTS.get('capex_sharkbite'),
                    key="sidebar_capex_input" # Unique key
                )

    
    if current_screen == 'welcome':
        display_welcome_screen_ui()
    elif current_screen == 'business_basics':
        display_form_page_from_ui(
            page_title="Project & Business Basics",
            progress_caption="Step [1/5]: BASICS  >  2. PROJECT DETAILS  >  3. SCORE PREVIEW  >  4. INCENTIVE STACK  > 5. SUMMARY", # Updated total steps
            section_title="Let's get to know your business",
            item_definitions=REAP_INTAKE_DEFINITIONS_PAGE2, # Defined in ui_screens or utils
            prev_screen_target='welcome',
            next_screen_target='project_details',
            next_button_text="Continue to Project Details"
        )
    elif current_screen == 'project_details':
        display_form_page_from_ui(
            page_title="Project Details",
            progress_caption="1. BASICS  >  Step [2/5]: PROJECT DETAILS  >  3. SCORE PREVIEW  >  4. INCENTIVE STACK  > 5. SUMMARY",
            section_title="Tell us about your clean energy project",
            item_definitions=REAP_INTAKE_DEFINITIONS_PAGE3, # Defined in ui_screens or utils
            prev_screen_target='business_basics',
            next_screen_target='reap_score_preview',
            next_button_text="Calculate REAP Score Preview"
        )
    elif current_screen == 'reap_score_preview':
        display_reap_score_preview_screen_from_ui()
    elif current_screen == 'incentive_stack_mock':
        display_incentive_stack_mock_screen()
    # To add other screens as they are built