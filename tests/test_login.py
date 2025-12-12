import sys, os
from streamlit.testing.v1 import AppTest

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def test_successful_login():
    """
    Tests that a user can log in and land on the welcome screen.
    """

    at = AppTest.from_file("sharkbite_app.py").run()
    
    # Ensure we start on the login screen
    #assert "Let's Get Started" in at.markdown[0].value
    assert at.tabs[1].label == "Login to existing account"

    at.text_input(key="main_login_user").input("testuser").run()
    at.text_input(key="main_login_pass").input("password").run()
    
    login_button = next((b for b in at.button if b.label.lower() == "login"), None)
    assert login_button is not None
    login_button.click().run()

    # After a successful login and rerun, we should be on the welcome screen
    assert at.title[0].value == "👋 Welcome to your Sharkbite Dashboard, testuser!"
    assert at.session_state.logged_in is True