# This file will house calculation logic, API calls, etc.
import streamlit as st
import requests

# AI Helper Texts (Comprehensive - aligning with PDF scoring insights)
AI_HELPER_TEXTS = {
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

ELIGIBILITY_CHECK_TEXTS = { # Mock for Week 1 - Add more diverse examples
    "55714": {"text": "This ZIP (mock) qualifies as RURAL and is in an ENERGY COMMUNITY! Potential 10% ITC bonus.", "type": "success"},
    "90210": {"text": "This ZIP (mock) is URBAN and NOT in a designated Energy Community.", "type": "warning"},
    "rural_default": {"text": "This ZIP (mock) qualifies as RURAL. Further checks needed for Energy Community status.", "type": "info"},
    "energy_community_default": {"text": "This ZIP (mock) is in an ENERGY COMMUNITY! Potential 10% ITC bonus.", "type": "success"},
    "default": {"text": "Enter a valid 5-digit ZIP for specific eligibility checks.", "type": "info"}
}

# REAP Intake Definitions (from Wireframes & REAP Form PDF)
REAP_INTAKE_DEFINITIONS_PAGE2 = [
    {"id": "q1_biz_structure", "label": "Business Type", "options": ["Sole Proprietor", "Partnership", "LLC", "Corporation", "Tribal Entity", "Rural Co-op", "Non-profit (501c3)", "Farm/Agriculture", "Small Business",], "widget": st.selectbox, "key": "p2_biz_structure"},
    {"id": "business_name", "label": "Business Name", "widget": st.text_input, "key": "p2_biz_name"},
    {"id": "q7_reap_funding_history", "label": "Have you received REAP funding before?", "options": ["First-time applicant", "Prior award (2+ years ago)", "Recent award (last 2 years)"], "widget": st.radio, "key": "p2_reap_history", "horizontal": True},
]
REAP_INTAKE_DEFINITIONS_PAGE3 = [
    {"id": "q2_project_type_reap", "label": "Project Type", "options": ["Renewable Energy System (RES)", "Energy Efficiency Improvement (EEI)", "Combined RES + EEI"], "widget": st.radio, "key": "p3_proj_type", "horizontal": True},
    {"id": "q3_primary_technology", "label": "Technology", "options": ["Solar PV", "Wind Turbine", "Anaerobic Digester", "Geothermal", "Battery Storage (with solar)", "Lighting / HVAC Upgrade", "Other"], "widget": st.radio, "key": "p3_tech"},
    {"id": "system_size_kw", "label": "System Size (kW)", "widget": st.number_input, "key": "p3_sys_size", "min_value": 0.05, "max_value": 500000.0, "value": 100.0, "step": 1.0},
    {"id": "q5_zip_code_reap", "label": "Project ZIP Code", "widget": st.text_input, "key": "p3_zip", "value": "55714"},
    {"id": "q4_ghg_emissions", "label": "🌍 Zero GHG Emissions Project?", "options": ["Yes", "No"], "widget": st.radio, "key": "p3_ghg", "horizontal": True, "index":0},
    # For Week 1, Q6, Q8, Q9, Q10 inputs are deferred as they relate to Screen 4 (Doc Upload)
]

# Mock data for non-REAP incentives (Week 1)
MOCK_NON_REAP_INCENTIVES_DATA = {
    "base_itc_rate": 0.30,
    "bonus_energy_community": 0.10, # If ZIP is in energy community
    "bonus_zero_emissions": 0.05,   # If project is zero emissions
    "state_incentives": [
        {"name": "Xcel MN Solar Rewards", "type": "per_watt", "value": 0.08, "applicable_zip_prefix": "55"}, # Example condition
        {"name": "MN PV Bonus", "type": "flat", "value": 15000, "applicable_zip_prefix": "55"}
    ]
}

# REAP Grant Caps by Technology (from optional grant estimate guidance)
# Example: $500K for PV, $1M for anaerobic digester.
REAP_GRANT_CAPS_BY_TECH = {
    "Solar PV": 500000,
    "Wind Turbine": 1000000, # Assuming similar to RES cap
    "Anaerobic Digester": 1000000,
    "Geothermal": 750000, # Example
    "Battery Storage (with solar)": 500000, # Often tied to solar cap
    "Lighting / HVAC Upgrade": 250000, # Example EEI cap
    "Other": 250000 # Default example
}


# ---------- NREL PVWatts API ----------
PVWATTS_URL = "https://developer.nrel.gov/api/pvwatts/v8.json"

# Simulated values for lat/lon from ZIPs
MOCK_ZIP_TO_LATLON = {
    "55714": {"lat": 46.83, "lon": -92.21}, # Hibbing, MN area
    "90210": {"lat": 35.05, "lon": -116.62}, # Beverly Hills, CA
    "68845": {"lat": 40.66, "lon": -98.33}, # Kearney, NE
    "98327": {"lat": 47.30, "lon": -122.08}, # DuPont, WA area, US
    "default": {"lat": 44.5, "lon": -93.1} # Northfield, Minnesota, USA
}

@st.cache_data
def get_solar_production_pvwatts(api_key, system_capacity_kw, zip_code, tilt=None, azimuth=None, array_type=1, module_type=0, losses=14):
    """
    Calls NREL PVWatts API to estimate annual solar energy production.
    Simulates lat/lon from ZIP for Week 1.

    array_type: 0=Fixed Open Rack, 1=Fixed Roof Mounted, 2=1-Axis Tracking, 3=1-Axis Backtracking, 4=2-Axis Tracking
    module_type: 0=Standard, 1=Premium, 2=Thin Film

    Returns (value or error message).
    Value is the 'ac_annual' if successful.
    Error_message is a string describing the error if one occurred.
    """
    # if not api_key:
    #     st.warning(":material/warning: NREL API Key not configured. Solar production estimate will be a rough mock.")
    #     # Fallbacks to a very rough estimate (Whimsical kWh per kW per year) if API key is not added
    #     return system_capacity_kw * 1200
    if not api_key:
        return "NREL API Key not configured. Solar production cannot be estimated."

    # Validate system_capacity_kw before making the API call
    try:
        system_capacity_float = float(system_capacity_kw)
        if system_capacity_float <= 0 or system_capacity_float > 500000: # PVWatts limit
             return f"Invalid system capacity: {system_capacity_kw} kW. Must be > 0 and <= 500,000 kW."
    except ValueError:
        return f"Invalid system capacity format: '{system_capacity_kw}'. Must be a number."

    lat_lon = MOCK_ZIP_TO_LATLON.get(zip_code, MOCK_ZIP_TO_LATLON["default"])

    params = {
        "api_key": api_key,
        "lat": lat_lon["lat"],
        "lon": lat_lon["lon"],
        "system_capacity": system_capacity_kw,
        "azimuth": azimuth if azimuth is not None else (180 if array_type !=0 else 180), # Default south for fixed
        "tilt": tilt if tilt is not None else (lat_lon["lat"] if array_type !=0 else 30), # Default to latitude for fixed, or common tilt
        "array_type": array_type,
        "module_type": module_type,
        "losses": losses, # Percentage
        "timeframe": "hourly" # Though we only need annual
    }
    try:
        response = requests.get(PVWATTS_URL, params=params, timeout=10)
        # Check if the response status code indicates an error
        if response.status_code != 200:
            try:
                # Attempt to parse error from JSON response body
                error_data = response.json()
                errors = error_data.get('errors', [])
                if errors:
                    # Join multiple error messages if present
                    error_message = "; ".join(str(e) for e in errors)
                    return f"PVWatts API Error (HTTP {response.status_code}): {error_message}"
                else:
                    # If no 'errors' key, use the reason or text
                    return f"PVWatts API HTTP Error {response.status_code}: {response.reason} - {response.text[:200]}"
            except ValueError: # If response is not JSON
                return f"PVWatts API HTTP Error {response.status_code}: {response.reason}. Non-JSON response: {response.text[:200]}"
        
        # If status code is 200, proceed to parse successful response
        data = response.json()
        if "outputs" in data and "ac_annual" in data["outputs"]:
            return data["outputs"]["ac_annual"] # Success
        else:
            # This case might occur if status is 200 but expected output is missing
            return "PVWatts API response missing 'ac_annual' output, though request was successful."

    except requests.exceptions.RequestException as e: # Catches network issues, timeout, etc.
        return f"PVWatts API Request Failed: {e}"
    except ValueError as e: # Catches JSON decoding errors for successful status codes
        return f"PVWatts API: Error decoding JSON response - {e}. Response text: {response.text[:200]}"
    except Exception as e: # Catch-all for other unexpected errors
        return f"Unexpected error during PVWatts API call: {e}"


def calculate_reap_score_from_formulas(form_data, is_rural_mock, is_energy_community_mock, doc_score_mock=0):
    """
    Calculates REAP score based on the simplified formula from the PDF.
    doc_score_mock is 0 for Week 1 as document upload is not implemented.
    is_rural_mock and is_energy_community_mock are booleans based on ZIP.
    """
    score = 0
    breakdown_details = [] # To provide some textual feedback for the score

    # +15 if first_time_applicant else 0
    if form_data.get("q7_reap_funding_history") == "First-time applicant":
        score += 15
        breakdown_details.append("+15: First-time REAP applicant")
    else:
        breakdown_details.append("+0: Not a first-time REAP applicant")

    # +10 if rural
    if is_rural_mock:
        score += 10
        breakdown_details.append("+10: Project in mock rural area")
    else:
        breakdown_details.append("+0: Project not in mock rural area")

    # +10 if energy_community
    if is_energy_community_mock:
        score += 10
        breakdown_details.append("+10: Project in mock energy community")
    else:
        breakdown_details.append("+0: Project not in mock energy community")

    # +10 if zero_emissions_project else 0
    # Assuming 'q4_ghg_emissions' from form_data is "Yes" or True if toggle
    if form_data.get("q4_ghg_emissions") == "Yes" or form_data.get("q4_ghg_emissions") is True:
        score += 10
        breakdown_details.append("+10: Zero-emissions project")
    else:
        breakdown_details.append("+0: Project not zero-emissions")
        
    # +15 if project_type == "Renewable Energy" else 0
    # The REAP form has "Renewable Energy System (RES)"
    if form_data.get("q2_project_type_reap") == "Renewable Energy System (RES)":
        score += 15
        breakdown_details.append("+15: Renewable Energy System project type")
    elif form_data.get("q2_project_type_reap") == "Combined RES + EEI": # Combined also implies RES
        score += 15 # Assuming combined also gets this
        breakdown_details.append("+15: Combined RES+EEI project type")
    else: # EEI only
        breakdown_details.append("+0: Not primarily a Renewable Energy System project type for this specific bonus")


    # +10 if technology in ["Solar PV", "Wind"] else 0
    if form_data.get("q3_primary_technology") in ["Anaerobic Digester", "Geothermal", "Battery Storage (with solar)"]:
        score += 10
        breakdown_details.append(f"+10: Technology is {form_data.get('q3_primary_technology')}")
    elif form_data.get("q3_primary_technology") in ["Solar PV", "Wind Turbine"]:
        score += 1
        breakdown_details.append(f"+1: Technology is {form_data.get('q3_primary_technology')}")
    else:
        breakdown_details.append(f"+0: Technology ({form_data.get('q3_primary_technology')}) not Geothermal or Solar for this specific bonus")

    # + doc_score # max 20 points
    # For Week 1, doc_score is 0 or a small mock value if we want to show it.
    # Formula breakdown: Docs uploaded (up to 20 pts)
    mock_doc_score_applied = min(doc_score_mock, 20)
    score += mock_doc_score_applied
    breakdown_details.append(f"+{mock_doc_score_applied}: Document score (mocked for Week 1)")
    
    # Max possible score based on this simplified formula for UI normalization (if needed, though formula is additive)
    # 15 (first_time) + 10 (rural) + 10 (energy_comm) + 10 (zero_emiss) + 15 (RES_project) + 10 (Solar/Wind) + 20 (doc_score_max) = 90
    max_formula_score = 90
    normalized_score = int((score / max_formula_score) * 100) if max_formula_score > 0 else 0
    
    return score, breakdown_details, normalized_score, max_formula_score


def calculate_optional_reap_grant_estimate(system_cost, technology):
    """Calculates the optional REAP Grant Estimate for Week 1."""
    if not system_cost or system_cost <= 0:
        return 0
    
    base_grant = 0.50 * system_cost
    grant_cap = REAP_GRANT_CAPS_BY_TECH.get(technology, REAP_GRANT_CAPS_BY_TECH["Other"]) # Default if tech not listed
    
    final_grant = min(base_grant, grant_cap)
    return final_grant