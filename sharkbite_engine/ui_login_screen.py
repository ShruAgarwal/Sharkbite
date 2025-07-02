import streamlit as st

def display_header():
    
    st.image("assets/logo.png", width = 350)
    # <h1 style='text-align: center; color: #00447C;'>🦈 Take a Bite Out of Energy Costs</h1>
    st.markdown("""
                <h2 style='text-align: center; font-style: italic; color: #00447C;'>🌟 Find Clean Energy Funding & Incentives That Work For Your Project</h2>
                """, unsafe_allow_html=True)
    st.caption("---")

def display_login_screen():
    """
    Displays the login and signup forms.
    Returns the username if login is successful, otherwise returns None.
    """
    display_header()
    st.markdown("### :material/lock: Let's Get Started")
    signup_tab, login_tab = st.tabs(["Sign Up for a new account", "Login to existing account"])
    
    with login_tab:
        with st.form("login_form_main"):
            username = st.text_input("Enter your unique username (demo: user)", key="main_login_user")
            password = st.text_input("Enter your password (demo: pass)", type="password", key="main_login_pass")
            login_button = st.form_submit_button("Login", type="primary", icon=":material/login:", use_container_width=True)
            
            if login_button:
                if username and password: # Mock validation
                    return username # Signal successful login
                else:
                    st.error("Please enter correct username and password.", icon=":material/warning:")
    
    with signup_tab:
        with st.form("signup_form_main"):
            new_username = st.text_input("Create a unique username", key="main_signup_user")
            new_password = st.text_input("Create a password", type="password", key="main_signup_pass")
            signup_button = st.form_submit_button("Sign Up", icon=":material/add_circle:", type="primary", use_container_width=True)

            if signup_button:
                if new_username and new_password:
                    st.success(f"Welcome, {new_username}! Please proceed to log in with new credentials.", icon=":material/thumb_up:")
                else:
                    st.error("Please fill up all the fields.", icon=":material/error:")
    
    # This section now shown to everyone, prompting login/signup if not logged in
    st.info("⚡ Answer simple questions to unlock:\n- REAP grants up to $1M\n- Tax credits up to 30%\n- Bonus credits, depreciation & more")
    if st.button("Watch Demo: How It Works", type="secondary", icon=":material/slideshow:", use_container_width=True, key="btn_watch_demo_ui_main"):
        st.toast("✨ The demo video link will be placed here!")