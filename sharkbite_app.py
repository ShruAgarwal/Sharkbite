import streamlit as st
import boto3
import logging, os
from sharkbite_engine.solar_calculator_logic import NREL_API_KEY_HOLDER, perform_solar_battery_calculations
from sharkbite_engine.ui_login_screen import display_login_screen
from sharkbite_engine.ui_unified_intake_screen import display_unified_intake_screen
from sharkbite_engine.ui_calculator_screen import display_solar_battery_calculator_screen
from sharkbite_engine.ui_ppa_analyzer_screen import display_ppa_analyzer_screen
from sharkbite_engine.ui_reap_flow_screens import (
    display_incentive_preview_screen,
    display_reap_deep_dive_screen,
    display_multi_grant_stack_screen,
    display_final_incentive_dashboard_screen,
    display_export_package_screen
)

st.set_page_config(page_title="🦈 Sharkbite Platform v2.0")

# --- Constructs an absolute path to the CSS file ---
# This ensures the file can be found whether running the app directly or via pytest.
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    css_file_path = os.path.join(script_dir, 'assets/custom_style.css')
    with open(css_file_path) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    # Optional: Add a fallback or warning if the CSS is missing
    st.warning("custom_style.css not found. The app will run with default styling.")


# --- NREL API Key Setup ---
NREL_API_KEY_FROM_SECRETS = None
try:
    NREL_API_KEY_FROM_SECRETS = st.secrets.get("NREL_API_KEY")
    NREL_API_KEY_HOLDER["key"] = NREL_API_KEY_FROM_SECRETS
    if not NREL_API_KEY_FROM_SECRETS and 'nrel_key_warning_shown' not in st.session_state:
        st.toast("NREL_API_KEY not found in secrets.toml. Solar Calculator may be limited.", icon="🚫")
        st.session_state.nrel_key_warning_shown = True
except Exception:
    if 'secrets_error_shown' not in st.session_state:
        st.toast("Error loading NREL_API_KEY from secrets. Solar Calculator may be limited.", icon="⚠️")
        st.session_state.secrets_error_shown = True

# --- Session State Initialization ---
if 'current_screen' not in st.session_state:
    st.session_state.current_screen = 'login'
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'calculator_results_display' not in st.session_state:
    st.session_state.calculator_results_display = None # For S2 results
if 'trigger_calculator_api_processing' not in st.session_state:
    st.session_state.trigger_calculator_api_processing = False
if 'bedrock_client' not in st.session_state:
    st.session_state.bedrock_client = None


def clear_project_data():
    """Resets session state for a new project, keeping login info."""
    # Keep logged_in and username, clear everything that is project-related
    for key in list(st.session_state.keys()):
        if key not in ['logged_in', 'username', 'current_screen']:
             del st.session_state[key]
    st.session_state.form_data = {}
    st.session_state.calculator_results_display = None
    st.session_state.trigger_calculator_api_processing = False


def display_welcome_logged_in():
    """A dedicated screen for the logged-in dashboard/welcome."""
    st.title(f"👋 Welcome to your Sharkbite Dashboard, {st.session_state.username}!")
    st.markdown("Start a new project analysis or continue a saved one.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start New Project", type="primary", icon=":material/rocket_launch:", use_container_width=True):
            clear_project_data()
            st.session_state.current_screen = 'unified_intake'
            st.rerun()
    with col2:
        if st.button("Continue Saved Project (Simulated)", icon=":material/folder_special:", use_container_width=True):
            st.toast("Feature to load saved projects coming soon!", icon="⏳")


# ====== Main App Router for New 7-Screen Flow ======
if __name__ == "__main__":

    if not st.session_state.logged_in:
        # If not logged in, force to login screen
        username = display_login_screen()
        if username:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.current_screen = 'welcome_logged_in'  # Go to welcome dashboard after login
            st.rerun()
        st.stop()  # Stop execution here if not logged in

    # Persistent Sidebar
    with st.sidebar:
        st.image("assets/logo.png", width = 200)
        st.write(f":rainbow-background[🦈 **Welcome back, {st.session_state.username}**!]")
        st.subheader("Sharkbite Project Assistant")

        if st.button("Back to Main / Start Over", icon=":material/home:", use_container_width=True, key="sidebar_home_main"):
            clear_project_data()
            st.session_state.current_screen = 'welcome_logged_in'
            st.rerun()

        st.markdown("---")
        # Add CapEx input here if specific to REAP and not covered by calculator's system cost
        st.subheader("Project CapEx")
        
        capex_default = 100000.0  # Ensure default value is a float
        try:
            capex_default = float(st.session_state.form_data.get('system_cost_for_reap', capex_default))
        except (ValueError, TypeError):
            capex_default = 100000.0
        
        st.session_state.form_data['reap_specific_capex'] = st.number_input(
            "Confirm/Adjust Project CapEx", min_value=0.0, value=capex_default, step=1000.0,
            key="sidebar_reap_capex_main", help="Total project cost. Used for REAP and financial calculations."
        )
        
        if st.button("Logout", icon=":material/logout:", type="primary", use_container_width=True, key="sidebar_logout_main"):
            # Clear all session data on logout
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # --- Centralized API Call Logic for Calculator Screen (S2) ---
    if st.session_state.get("trigger_calculator_api_processing", False):
        st.session_state.trigger_calculator_api_processing = False # Consume signal
        
        # Consolidate inputs for the calculator logic from form_data (S1 and S2 refinements)
        calc_inputs = {
            "address": st.session_state.form_data.get("unified_address_zip"),
            "monthly_kwh_usage": st.session_state.form_data.get("unified_monthly_kwh"),
            "cost_per_kwh": st.session_state.form_data.get("unified_electricity_rate"),
            "system_size_kw": st.session_state.form_data.get("calculator_refined_system_size_kw"),
            "backup_pref": st.session_state.form_data.get("calculator_backup_pref"),
            "calc_battery_cost": st.session_state.form_data.get("override_battery_cost"),
            "user_type": st.session_state.form_data.get("unified_business_type"),
            "annual_kwh_est": st.session_state.form_data.get("annual_kwh_est"),
            "self_consumption_priority": st.session_state.form_data.get("self_consumption_priority"),
            "inverter_size_kw": st.session_state.form_data.get("inverter_size_kw"),
            "min_battery_reserve_pct": st.session_state.form_data.get("min_battery_reserve_pct"),
            "ev_annual_miles": st.session_state.form_data.get("ev_annual_miles"),
            "ev_efficiency_mi_kwh": st.session_state.form_data.get("ev_efficiency_mi_kwh"),
            "heat_pump_btu_yr": st.session_state.form_data.get("heat_pump_btu_yr"),
            "heat_pump_cop": st.session_state.form_data.get("heat_pump_cop"),
            "tou_enabled": st.session_state.form_data.get("tou_enabled"),
            "rate_plan": st.session_state.form_data.get("rate_plan")
        }
        # Ensure all inputs are present before calling
        if all(val is not None for val in calc_inputs.values()): # More robust check
            with st.spinner("Analyzing property and generating proposal..."):
                st.session_state.calculator_results_display = perform_solar_battery_calculations(calc_inputs)
        else:
            st.session_state.calculator_results_display = {"geo_error": "Missing one or more inputs from the Unified Intake or Calculator screen."}
        st.rerun() # Rerun to display results on the same screen


    # Screen Routing for logged-in users adapting to new 7-screen flow ---
    current_screen = st.session_state.current_screen
    next_screen_signal = None  # To capture navigation requests from UI functions

    # --- Initialize Bedrock client only when entering the AI-powered part of the flow ---
    if current_screen in ['ppa_analyzer', 'incentive_preview', 'multi_grant_stacker', 'final_incentive_dashboard'] \
       and st.session_state.bedrock_client is None:
        
        st.toast("Initializing AI Co-pilot...", icon="🤖")
        try:
            # Attempt to create the client and store it in session state
            st.session_state.bedrock_client = boto3.client(
                service_name='bedrock-runtime',
                region_name=st.secrets.get("AWS_REGION")
            )
            # Use a simple logger here or just a toast for success
            logging.info("Bedrock client initialized successfully on demand.")
        
        except Exception as e:
            logging.critical(f"Could not initialize AWS Bedrock client: {e}")
            st.session_state.bedrock_client = None # Ensure it's None on failure
            # A persistent error might be better than a toast
            st.error("Failed to initialize the AI Co-pilot. AI features will be unavailable.", icon="🚨")


    if current_screen == 'login':  # Should only be hit on first run before login succeeds
        pass # The login gate at the top handles this

    elif current_screen == 'welcome_logged_in':
        display_welcome_logged_in()

    elif current_screen == 'unified_intake':
        if display_unified_intake_screen():  # Returns True if "Continue"
            st.session_state.current_screen = 'solar_battery_calculator'
            st.rerun()
    
    elif current_screen == 'solar_battery_calculator':
        next_screen_signal = display_solar_battery_calculator_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()

    # --- THIS IS THE NEW ROUTE BRANCH (OPTIONAL) ---
    elif current_screen == 'ppa_analyzer':
        # The app is now on the PPA screen (main screen flow isn't shown here)
        display_ppa_analyzer_screen()
        # Navigation back is handled by the button within the screen function
            
    elif current_screen == 'incentive_preview':
        next_screen_signal = display_incentive_preview_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()

    elif current_screen == 'reap_deep_dive':
        next_screen_signal = display_reap_deep_dive_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()

    elif current_screen == 'multi_grant_stacker':
        next_screen_signal = display_multi_grant_stack_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()

    elif current_screen == 'final_incentive_dashboard':
        next_screen_signal = display_final_incentive_dashboard_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()

    elif current_screen == 'export_package':
        next_screen_signal = display_export_package_screen()
        if next_screen_signal:
            st.session_state.current_screen = next_screen_signal
            st.rerun()
    else: # Default case if screen state is unknown
        st.session_state.current_screen = 'welcome_logged_in'
        st.rerun()