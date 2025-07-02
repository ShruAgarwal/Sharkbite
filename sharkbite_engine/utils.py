# --- Constants from code file `solar_proposal_ai_battery.py` & "Formulas" PDF ---
AVG_SUN_HOURS_FOR_AUTOSIZE = 5
DERATE_FACTOR_FOR_AUTOSIZE = 0.75
SOLAR_SYSTEM_COST_PER_KW = 2500 # From the code script
BATTERY_UNIT_KWH = 13.5
BATTERY_UNIT_COST = 12000
BASE_ITC_RATE = 0.30 # For calculator step
LOAN_RATE = 0.06

# MACRS for Calculator (Screen 2 of new flow)
CALCULATOR_SIMPLIFIED_MACRS_RATE = 0.26 # Flat 26% of (System + Battery Cost) for commercial

# AI Helper Texts (Comprehensive - aligning with PDF scoring insights)
AI_HELPER_TEXTS_REAP = {
    "q1_biz_structure": "REAP prioritizes: First-time applicants, Small Businesses (SBA definition), entities in Rural areas, Tribal entities, and Agricultural Producers. Max 15 pts for this category (combined with prior history).",
    "q7_reap_funding_history": "Being a first-time REAP applicant gives a significant point advantage. Recent awardees (last 2 years) score lower. Max 15 pts (combined with business type).",
    "business_name": "Enter the legal name of your business as registered.",
    "q2_project_type_reap": "Energy Efficiency (EEI) or Combined (RES+EEI) projects often score higher in REAP due to comprehensive benefits & cost savings. Max 15 pts.",
    "q3_primary_technology": "While Solar PV is common, REAP may give priority to 'underutilized' tech with high impact like Anaerobic Digesters or Geothermal. Max 10 pts.",
    "system_size_kw": "System capacity in kW. Affects grant caps ($1M for RES, $500k for EEI) & technical report needs (>$200k project cost).",
    "q5_zip_code_reap": "Crucial for REAP! Used for USDA rural status, Energy Community & Justice40 bonus. Check official USDA map. Max 10 pts.",
    "q4_ghg_emissions": "Projects achieving net-zero GHG emissions typically receive maximum points for Environmental Benefit. Max 10 pts.",
    "project_name_sharkbite": "A unique, descriptive name helps track your project.",
    "capex_sharkbite": "Total Capital Expenditure. REAP grant is up to 50% of this, subject to project type caps ($1M RES, $500k EEI)."
}

MOCK_NON_REAP_INCENTIVES_PREVIEW = {
    "base_itc_rate_display": 0.30,
    "bonus_energy_community_potential": 0.10, # If ZIP is in energy community
    "bonus_zero_emissions": 0.05,   # If project is zero emissions
    "state_incentives": [
        {"name": "Xcel MN Solar Rewards", "type": "per_watt", "value": 0.08, "applicable_zip_prefix": "55"}, # Example condition
        {"name": "MN PV Bonus", "type": "flat", "value": 15000, "applicable_zip_prefix": "55"}
    ]
}

# REAP Grant Caps
REAP_GRANT_CAPS_BY_TECH = {
    "Solar PV": 500000, "Wind Turbine": 1000000, "Anaerobic Digester": 1000000,
    "Geothermal": 750000, "Battery Storage (with solar)": 500000,
    "Lighting / HVAC Upgrade": 500000, # Changed to match EEI Cap
    "Other": 250000, # Default for other tech
    "Renewable Energy System (RES)": 1000000, # General Cap from REAP PDF
    "Energy Efficiency Improvement (EEI)": 500000, # General Cap
    "Combined RES + EEI": 1000000
}

# AI Helper Texts (Keep and expand as needed)
AI_HELPER_TEXTS_UNIFIED_INTAKE = {
    "address_zip": "Full property address (Street, City, State, ZIP) for accurate solar estimates and local incentive checks.",
    "business_type_unified": "Select your primary entity type. This influences eligible incentives like MACRS for businesses.",
    "monthly_kwh_usage": "Average monthly electricity consumption in kWh (from your utility bill). Used for system auto-sizing.",
    "electricity_rate": "Your average cost per kWh ($/kWh) from your utility bill. Impacts savings calculations."
}
AI_HELPER_TEXTS_CALCULATOR = {
    "system_size_kw": "Confirm or adjust the auto-recommended solar system size in kilowatts (kW).",
    "backup_pref": "'Essentials' covers critical loads. 'Whole House' aims to power most of your home during an outage."
}
# ToDo: Add AI_HELPER_TEXTS for REAP flow screens as before

# Mock Eligibility Check for Unified Intake
ELIGIBILITY_CHECKS_UNIFIED_INTAKE = {
    "55714": {"text": "This ZIP (mock) qualifies as RURAL and is in an ENERGY COMMUNITY! Potential 10% ITC bonus and strong REAP eligibility.", "type": "success"},
    "90210": {"text": "This ZIP (mock) is URBAN and likely NOT in a designated Energy Community for ITC bonus.", "type": "warning"},
    "default": {"text": "Enter a valid 5-digit ZIP from your address for specific eligibility insights.", "type": "info"}
}

# REAP Scoring Formula (Simplified for preview on Screen 3, and for Screen 5 of original flow)
# This is the simplified one from Francie's "FORMULAS" PDF
# score = (+15 if first_time_applicant else 0 + 10 if rural + 10 if energy_community + 
#          10 if zero_emissions + 15 if renewable_project + 
#          10 if technology in ['Solar PV', 'Wind'] + doc_score)
def calculate_simplified_reap_score(form_data, is_rural_mock, is_energy_community_mock, doc_score_mock=0):
    # ... (Implementation from previous response, ensure it uses relevant keys from form_data) ...
    # Example relevant keys from form_data (ensure these are collected/mapped from Unified Intake or Calculator)
    # form_data.get('reap_funding_history_from_reap_intake') -> maps to first_time_applicant
    # form_data.get('zero_emissions_toggle_from_reap_intake') -> maps to zero_emissions
    # form_data.get('project_type_from_reap_intake') -> maps to renewable_project
    # form_data.get('technology_from_reap_intake') -> maps to technology
    score = 0
    breakdown_details = []

    # For REAP Scoring, we need REAP-specific inputs. These will be collected in the REAP Deep Dive (New S4).
    # For the "Incentive Preview" (New S3), we can make some assumptions or use defaults.
    first_time = form_data.get("q7_reap_funding_history", "First-time applicant") == "First-time applicant" # Default to true for preview
    zero_emissions = form_data.get("q4_ghg_emissions_toggle", True) # Default to true
    # Infer project_type and technology from calculator if possible, else use defaults for preview
    project_type_reap = form_data.get("q2_project_type_reap_for_scoring", "Renewable Energy System (RES)")
    technology_reap = form_data.get("q3_primary_technology_for_scoring", "Solar PV")

    if first_time:
        score += 15
        breakdown_details.append("+15: First-time REAP applicant (assumed/input)")
    if is_rural_mock:
        score += 10
        breakdown_details.append("+10: Project in mock rural area")
    if is_energy_community_mock:
        score += 10
        breakdown_details.append("+10: Project in mock energy community")
    if zero_emissions:
        score += 10
        breakdown_details.append("+10: Zero-emissions project (assumed/input)")
    if project_type_reap == "Renewable Energy System (RES)":
        score += 15
        breakdown_details.append("+15: Renewable Energy project type")
    if technology_reap in ["Solar PV", "Wind Turbine"]:
        score += 10
        breakdown_details.append(f"+10: Tech ({technology_reap})")
    
    score += min(doc_score_mock, 20) # Max 20 for docs
    breakdown_details.append(f"+{min(doc_score_mock,20)}: Document score (mocked)")
    
    max_formula_score = 15+10+10+10+15+10+20 # 90
    normalized_score = int((score / max_formula_score) * 100) if max_formula_score > 0 else 0
    return score, breakdown_details, normalized_score, max_formula_score


# --- Progress Badge Utility ---
def generate_progress_bar_markdown(screen_flow_map, current_screen_key, total_steps_override=None):
    """Generates markdown for a progress bar with the current step highlighted."""
    total_steps_val = total_steps_override if total_steps_override else len(screen_flow_map)
    
    progress_display_list = []
    for screen_name_loop_key, (step_num, step_name_val) in screen_flow_map.items():
        display_name = step_name_val.replace(" ", " ") # Ensure spaces are kept
        if screen_name_loop_key == current_screen_key:
            progress_display_list.append(f":violet-badge[:material/screen_record: STEP [{step_num}/{total_steps_val}]: {display_name}]")
        else:
            progress_display_list.append(f"STEP [{step_num}/{total_steps_val}]: {display_name}")
    return " > ".join(progress_display_list)


# --- TODO WEEK 2: Detailed Financials & Order of Operations Logic ---
# Placeholder for functions related to detailed MACRS, Federal Share Cap, etc.
# def calculate_detailed_macrs_5_year(depreciable_basis, bonus_depreciation_rate_year1, year_placed_in_service): ...
# def check_federal_share_cap(reap_grant, total_itc, total_project_cost): ...
# def apply_order_of_operations(total_project_cost, form_data_from_reap_intake, calculator_results): ...