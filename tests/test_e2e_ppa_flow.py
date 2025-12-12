from streamlit.testing.v1 import AppTest
import sys, os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def test_ppa_button_visibility_for_homeowner():
    """
    Tests that the PPA button appears for homeowners.
    """

    at = AppTest.from_file("sharkbite_app.py").run()
    
    # Simulate a full run up to Screen 2 for a HOMEOWNER
    # This involves setting session state values programmatically
    at.session_state.logged_in = True
    at.session_state.username = "homeowner_test"
    at.session_state.current_screen = "solar_battery_calculator"
    at.session_state.form_data = {
        "unified_business_type": "Homeowner", # <== KEY condition
        "calculator_refined_system_size_kw": 8.0,
        "calculator_results_display": {"financials": {}} # Minimal data to prevent errors
    }
    at.run() # Rerun the script with the new state

    # Assert that the PPA button is now visible
    assert len(at.button) > 0
    ppa_button = next((b for b in at.button if "⚖️ Compare PPA vs. Ownership" in b.label), None)
    assert ppa_button is not None
    assert not ppa_button.disabled

def test_ppa_button_is_hidden_for_commercial():
    """
    Tests that the PPA button is HIDDEN for commercial users.
    """

    at = AppTest.from_file("sharkbite_app.py").run()
    
    # Simulate a full run up to Screen 2 for a COMMERCIAL user
    at.session_state.logged_in = True
    at.session_state.username = "commercial_test"
    at.session_state.current_screen = "solar_battery_calculator"
    at.session_state.form_data = {
        "unified_business_type": "Commercial / Business", # <-- KEY condition
        "calculator_refined_system_size_kw": 50.0,
        "calculator_results_display": {"financials": {}}
    }
    at.run()

    # Assert that the PPA button is NOT visible
    ppa_button = next((b for b in at.button if "⚖️ Compare PPA vs. Ownership" in b.label), None)
    assert ppa_button is None