from sharkbite_engine.incentive_definitions import INCENTIVE_PROGRAMS
from datetime import date
import inspect  # To inspect function arguments
import re
import numpy as np
import pandas as pd
import streamlit as st

# --- Important Constants ---
AVG_SUN_HOURS_FOR_AUTOSIZE = 5
DERATE_FACTOR_FOR_AUTOSIZE = 0.75
BATTERY_UNIT_KWH = 13.5
BATTERY_UNIT_COST = 12000

# Specific yield: kWh produced annually per kW of system size which varies by location (for auto-sizing from bill)
SPECIFIC_YIELD_RULE_OF_THUMB = 1300 # a reasonable US average for a simple rule-of-thumb.
INVERTER_EFF = 0.96

PV_COST_PER_WATT = 3.50  # $/W installed, for CapEx calculation
SOLAR_SYSTEM_COST_PER_KW = PV_COST_PER_WATT * 1000 # For consistency with our kW-based logic
BATTERY_COST_PER_KWH = 700  # $/kWh turn-key (adjust as needed)
DEFAULT_DC_AC_RATIO = 1.25

BASE_ITC_RATE = 0.30 # For calculator step
LOAN_RATE = 0.06

WHOLESALE_EXPORT_RATE = 0.03  # Placeholder for self-consumption model
NET_METER_CREDIT_FACTOR = 0.75 # 75% of retail rate for exports
MACRS_TAX_RATE = 0.21 # Corporate tax rate for commercial projects

# SOLAR_SYSTEM_COST_PER_KW = 2500
# CALCULATOR_SIMPLIFIED_MACRS_RATE = 0.26 # Flat MACRS @26% of (System + Battery Cost) for commercial

# --- Detailed TOU Schedule Configuration ---
# This structure is based on the PG&E tariff documents that defines seasons, day types, & peak hours for different rate plans.
HOLIDAYS_2025 = [ # For rate calculations
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 5, 26),
    date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 11), date(2025, 11, 27),
    date(2025, 12, 25),
]

TOU_SCHEDULE_CONFIG = {
    "Residential E-TOU-C": {
        "description": "Common residential plan with a daily peak period in the evening.",
        "seasons": {
            "all_year": {"peak_rate": 0.55, "offpeak_rate": 0.35}
        },
        "periods": {
            "peak": {"days": ["weekday"], "hours": range(16, 21)}, # 4 PM to 9 PM
        }
    },
    "Ag Rate AG-4B (Summer Peak)": {
        "description": "Agricultural rate with a summer mid-day peak.",
        "seasons": {
            "summer": {"peak_rate": 0.29802, "offpeak_rate": 0.16173}, # May-Oct
            "winter": {"peak_rate": 0.16188, "offpeak_rate": 0.13657} # Winter has a "Partial Peak" - we simplify to peak for this model
        },
        "periods": {
            "peak": {"days": ["weekday"], "hours": range(12, 18)}, # 12 PM to 6 PM
        }
    },
    "Ag Rate AG-5B (Summer Peak)": {
        "description": "Agricultural rate with lower off-peak prices.",
        "seasons": {
            "summer": {"peak_rate": 0.22184, "offpeak_rate": 0.09543}, # May-Oct
            "winter": {"peak_rate": 0.11743, "offpeak_rate": 0.08633} # Winter has a "Partial Peak"
        },
        "periods": {
            "peak": {"days": ["weekday"], "hours": range(12, 18)}, # 12 PM to 6 PM
        }
    }
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

# Mock Eligibility Check for Unified Intake
ELIGIBILITY_CHECKS_UNIFIED_INTAKE = {
    "55714": {"text": "This ZIP (mock) qualifies as RURAL and is in an ENERGY COMMUNITY! Potential 10% ITC bonus and strong REAP eligibility.", "type": "success"},
    "90210": {"text": "This ZIP (mock) is URBAN and likely NOT in a designated Energy Community for ITC bonus.", "type": "warning"},
    "default": {"text": "Enter a valid 5-digit ZIP from your address for specific eligibility insights.", "type": "info"}
}

# --- NEW: Static Tooltips / Helper Texts ---
# This dictionary will hold all static helper texts. It is more reliable and cost-effective than calling an LLM.
TOOLTIPS = {
    # --- Screen 1: Unified Intake ---
    "address_zip": "Your full property address (Street, City, State, ZIP) is used for accurate geocoding, solar production estimates, and local incentive checks.",
    "unified_business_type": "Choose your primary entity type—like 'Homeowner' for residential analysis or a business type to unlock commercial tax incentives like MACRS depreciation. Let’s maximize your benefits!",
    "unified_monthly_kwh": "Your average monthly electricity usage (in kWh) from your utility bill. This is the primary input for auto-sizing your solar system.",
    "unified_electricity_rate": "Your average cost per kWh ($/kWh) from your utility bill is essential for calculating potential savings. Knowing this figure empowers your energy choices!",
    "self_consumption_priority": "Prioritizes using your own solar/battery power before exporting. Recommended for areas with low grid export rates.",

    # --- Screen 2: Solar & Battery Calculator ---
    "system_size_kw": "Confirm or adjust the auto-recommended solar system size in kilowatts (kW). A larger system produces more energy but costs more.",
    "inverter_size_kw": "The inverter converts DC solar power to AC household power. Sizing it smaller than the solar array (e.g., DC/AC ratio of 1.25) can be cost-effective but may lead to 'clipping' (lost energy) on very sunny days.",
    "calculator_backup_pref": "Essentials provides backup for critical loads (e.g., fridge, lights), whereas the 'Whole House' option aims to power most of your home during an outage.",
    "min_battery_reserve_pct": "Sets a minimum charge level that the battery will not discharge below during normal operation, preserving it for a power outage.",
    "override_battery_cost": "Override the default battery cost assumption if you have a specific quote. This is an advanced setting.",
    "tou_enabled": "Enable a more sophisticated savings calculation based on peak and off-peak electricity rates, which is crucial for battery optimization.",
    "rate_plan": "The selected plan determines the peak/off-peak rates and times used in the financial model, based on real utility tariff structures.",
    "self_consumption_rate": "Percentage of solar energy you produce that is used directly on-site (powering your home or charging your battery), instead of being exported to the grid.",
    "grid_independence_rate": "Percentage of your total electricity needs that are met by your own solar and battery system, indicating your reliance on the grid.",
    "net_grid_interaction": "Total kWh imported from the grid minus total kWh exported. A lower number means less reliance on the grid.",
    
    # --- PPA Analyzer Screen ---
    "ownership_net_cost_y1": "Your estimated cost to own the system after all grants and tax credits.",
    "ppa_rate_y1": "The fixed price per kilowatt-hour (kWh) you agree to pay the PPA provider in the first year of the contract.",
    "ppa_escalator": "The annual percentage increase in your PPA rate. A 2.9% escalator means your price per kWh will go up by 2.9% each year.",
    "utility_escalator": "Your best estimate for how much your standard utility electricity rates will increase each year. This is used as the baseline for calculating your savings.",
    "owner_om_cost_per_kw_yr": "Estimated annual cost for maintenance, cleaning, and monitoring for a system you own. Typically $15-30 per kW per year.",
    "owner_inverter_replacement_cost": "The estimated cost to replace the solar inverter, which typically has a shorter lifespan (10-15 years) than the solar panels.",
    
    # --- Screen 4 (REAP Deep Dive) & 5 (Multi-Grant Stacker) ---
    # "business_name": "Enter the legal name of your business as registered.",
    # "project_name_sharkbite": "A unique, descriptive name helps track your project.",
    "capex_sharkbite": "Total Capital Expenditure. REAP grant is up to 50% of this, subject to project type caps ($1M RES, $500k EEI).",
    "system_size_kw": "System capacity in kW. Affects grant caps ($1M for RES, $500k for EEI) & technical report needs (>$200k project cost).",
    "q1_biz_structure": "REAP prioritizes: First-time applicants, Small Businesses (SBA definition), entities in Rural areas, Tribal entities, and Agricultural Producers. Max 15 pts for this category (combined with prior history).",
    "q2_project_type_reap": "Confirm the category your project falls under for REAP. Energy Efficiency (EEI) or Combined (RES+EEI) projects often score higher in REAP due to comprehensive benefits & cost savings. Max 15 pts.",
    "q3_primary_technology": "The technology type can affect REAP grant caps and scoring. While Solar PV is common, REAP may give priority to 'underutilized' tech with high impact like Anaerobic Digesters or Geothermal. Max 10 pts.",
    "q4_ghg_emissions": "Projects that result in zero greenhouse gas emissions (like solar and wind) receive a significant scoring bonus for their environmental benefit.",
    "q5_zip_code_reap": "Crucial for REAP! Used for USDA rural status, Energy Community & Justice40 bonus. Check the official USDA map. Max 10 pts.",
    "q7_reap_funding_history": "First-time applicants are often prioritized with 15 bonus points in the REAP scoring evaluation, increasing their approval chances. Recent awardees or repeat applicants score lower unless projects differ significantly.",
    "mock_doc_score_reap": "This simulates the points awarded for having necessary documents like energy audits, permits, and deeds ready for your application. Higher readiness leads to a better score.",
    "placed_in_service_year": "The year your project becomes operational. This determines the Bonus Depreciation rate (e.g., 60% for 2024, 40% for 2025).",
    
    # --- Screen 6: Final Dashboard Metrics (with calculations) ---
    "correct_depreciable_basis": "Your basis for depreciation after a 50% ITC reduction",
    "total_itc_value": "30% of Total Project Cost plus any eligible bonuses (e.g., Energy Community).",
    "year_1_depreciation_tax_benefit": "The tax savings from depreciation in Year 1. Calculated on the 'Correct Depreciable Basis' using Bonus + MACRS rules.",
    "final_net_cost": "The estimated out-of-pocket cost in Year 1. Calculation: Total Project Cost - (REAP Grant + ITC + Depreciation Tax Benefit + Other Grants).",
    "annual_savings": "Based on your TOU rates and self-consumption.",
}


# --- Progress Badge Utility ---
def generate_progress_bar_markdown(screen_flow_map,
                                   current_screen_key,
                                   final_step_completed=False,
                                   total_steps_override=None):
    """
    Generates markdown for a progress bar with completed, current, and future steps highlighted.
    """
    
    ppa_visited = st.session_state.get("ppa_screen_visited", False)

    total_steps_val = total_steps_override if total_steps_override else len(screen_flow_map)

    # If on the optional PPA screen, treat the calculator as the current step for the progress bar
    effective_screen_key = 'solar_battery_calculator' if current_screen_key == 'ppa_analyzer' else current_screen_key
    
    current_step_num = screen_flow_map.get(effective_screen_key, (0, ''))[0]

    # If the final step is marked as complete, advance the step number beyond the map
    if final_step_completed:
        current_step_num = total_steps_val + 1

    progress_display_list = []
    screen_keys_in_order = list(screen_flow_map.keys())

    for screen_name_loop_key in screen_keys_in_order:
        step_num, step_name_val = screen_flow_map[screen_name_loop_key]
        display_name = step_name_val.replace(" ", " ")

        if step_num < current_step_num:
            # Completed step: Green badge
            progress_display_list.append(f":green-badge[:material/task_alt: {step_num}: {display_name}]")
        elif screen_name_loop_key == effective_screen_key:
            # Current/active step: Violet badge
            progress_display_list.append(f":violet-badge[:material/screen_record: {step_num}: {display_name}]")
        else:
            # Not yet visited step: Grey badge
            progress_display_list.append(f":grey-badge[:material/radio_button_partial: {step_num}: {display_name}]")
    
    # After building the main list, insert the optional PPA screen name if it has been visited
    if ppa_visited:
        try:
            # Finds the original index of the calculator screen
            calculator_index_in_keys = screen_keys_in_order.index('solar_battery_calculator')
            # Insert the colorless PPA label right after it in the display list
            progress_display_list.insert(calculator_index_in_keys + 1, ":blue-badge[PPA Analyzer]")
        except ValueError:
            # Failsafe in case 'solar_battery_calculator' isn't in the map keys
            pass

    return " **--** ".join(progress_display_list)


# --- NEW: Auto-Sizing Function ---
def calculate_autosized_system_kw(monthly_kwh_usage):
    """
    Auto-sizes a solar system based on monthly usage as per Francie's formula.
    Formula: Monthly Usage ÷ (Sun Hours * 30 * Derate Factor)
    """
    if not monthly_kwh_usage or monthly_kwh_usage <= 0:
        return 0.0
    try:
        # Perform calculation
        size = float(monthly_kwh_usage) / (AVG_SUN_HOURS_FOR_AUTOSIZE * 30 * DERATE_FACTOR_FOR_AUTOSIZE)
        # Round to one decimal place for a clean recommendation
        return round(size, 1)
    except (ValueError, TypeError):
        return 0.0
    

# --- TOU Rate Schedule Generator ---
def generate_hourly_rate_schedule(rate_plan: str):
    """
    Generates a NumPy array of 8760 hourly electricity rates based on a selected TOU plan.
    """
    if rate_plan not in TOU_SCHEDULE_CONFIG:
        # Fallback to a flat rate: if rate_plan is not found
        return np.full(8760, 0.18) 

    plan = TOU_SCHEDULE_CONFIG[rate_plan]
    timestamps = pd.to_datetime(pd.date_range("2025-01-01", periods=8760, freq="h"))
    
    hourly_rates = np.zeros(8760)

    for i, ts in enumerate(timestamps):
        # Determine Season
        season = "winter"
        if 5 <= ts.month <= 10:   # May-to-Oct is Summer
            season = "summer"
        
        # Use correct season or fall back safely
        if season in plan["seasons"]:
            season_rates = plan["seasons"][season]
        elif "all_year" in plan["seasons"]:
            season_rates = plan["seasons"]["all_year"]
        else:
            raise ValueError(f"Rate plan '{rate_plan}' is missing season '{season}' and has no 'all_year' fallback.")
    
       # Use "all_year" if specific season not defined
        peak_rate = season_rates["peak_rate"]
        offpeak_rate = season_rates["offpeak_rate"]
        
        # Determine Day Type
        is_weekday = ts.dayofweek < 5   # Monday=0, Sunday=6
        is_holiday = ts.date() in HOLIDAYS_2025
        
        # Default to off-peak
        rate = offpeak_rate
        
        # Check if it's a peak period
        peak_period = plan["periods"]["peak"]
        if ts.hour in peak_period["hours"]:
            if ("weekday" in peak_period["days"] and is_weekday and not is_holiday) or \
               ("everyday" in peak_period["days"]):
                rate = peak_rate
        
        hourly_rates[i] = rate
        
    return hourly_rates


# --- NEW: Simulated Realistic RUCA Code Dictionary for NON-REAP Projects Only ---
# This mimics a real ZIP-to-RUCA database lookup (for now) that acts as an override/specific example list.
# RUCA codes 1-3 are "Metropolitan", 4-6 are "Micropolitan", 7-9 are "Small Town", 10 is "Rural".
# USDA generally considers RUCA >= 4 as eligible for many rural programs.
MOCK_RUCA_CODES = {
    # Urban Overrides (to be sure they are classified correctly)
    "90210": 1, "60613": 1, "10001": 1,
    "33109": 1, # Miami Beach
    "94102": 1, # San Francisco
    
    # Rural Overrides (for specific demo scenarios)
    "59718": 4, "95453": 7, "30680": 8,
    "59011": 10, "69201": 10, # Valentine, NE (very rural)
    "81419": 10,
}

# --- NEW: Dedicated RUCA Code Lookup Function ---
def get_ruca_code_from_zip(zip_code_str: str) -> tuple[int | None, str]:
    """
    Finds a 5-digit ZIP from a string and returns its estimated RUCA code.
    1. Checks for an explicit override in MOCK_RUCA_CODES.
    2. Falls back to a heuristic based on the first digit of the ZIP code.

    It intelligently finds the last 5-digit number in the string to avoid
    mistaking house numbers for ZIP codes.
    
    Returns (ruca_code, reason_string).
    """
    if not zip_code_str or not isinstance(zip_code_str, str):
        return "No address string provided."
    
    zip_code = None
    address_clean = zip_code_str.strip()
    ruca_code = None
    reason = ""

    # First, check if the entire cleaned string is just a ZIP code.
    if address_clean.isdigit() and len(address_clean) == 5:
        zip_code = address_clean
    else:
        # If it's a longer address, find all 5-digit numbers and take the last one.
        # The ZIP code in a US address is conventionally the final numerical component.
        all_five_digit_numbers = re.findall(r'\b\d{5}\b', address_clean)
        if all_five_digit_numbers:
            zip_code = all_five_digit_numbers[-1]

    if not zip_code:
        return None, "No valid 5-digit ZIP code could be extracted from the address."

    # Step 1: Check for a specific mock override first
    if zip_code in MOCK_RUCA_CODES:
        ruca_code = MOCK_RUCA_CODES[zip_code]
        reason = f" (using specific demo value for ZIP {zip_code})"
        return ruca_code, reason
    
    # Step 2: Heuristic Fallback based on the first digit
    first_digit = zip_code[0]
    if first_digit in ['3', '4', '5', '6', '7', '8']:
        ruca_code = 7  # Assume Small Town/Rural
        reason = f" (heuristic guess for rural region based on ZIP {zip_code})"
        return ruca_code, reason
    elif first_digit in ['0', '1', '2', '9']: # Generally more urbanized regions
        ruca_code = 1  # Assume Metro
        reason = f" (heuristic guess for urban region based on ZIP {zip_code})"
        return ruca_code, reason
    else:
        return False, f"Invalid ZIP code format: '{zip_code}'."


# --- NEW: REAP Eligibility Check with RUCA code ---
def is_reap_eligible(form_data: dict) -> tuple[bool, str]:
    """
    Checks REAP eligibility by combining business type and location (via RUCA code).
    """
    user_type = form_data.get("unified_business_type")
    
    # Rule 1: Check Business Type (remains the same)
    eligible_biz_types = ["Farm / Agriculture", "Rural Cooperative", "Commercial / Business"]
    if user_type not in eligible_biz_types:
        return False, f"Your business type ('{user_type}') is not eligible for REAP."

    # Rule 2: Check Location with Heuristic Fallback
    address_string = form_data.get("unified_address_zip", "") #.split(',')[-1].strip()[:5]
    ruca_code, reason = get_ruca_code_from_zip(address_string)

    # Step 3: Final check based on the determined RUCA code
    if ruca_code is not None and ruca_code >= 4:
        # Store eligibility status in session state for other functions to use
        return True, f"Your location **RUCA Code: {ruca_code}{reason}** appears to be in a REAP-eligible rural area."
    else:
        return False, f"Your location **RUCA Code: {ruca_code}{reason}** is in a metropolitan area and is not eligible for REAP."


# --- DETAILED REAP SCORING ENGINE (Replaces simplified formula) ---
def calculate_detailed_reap_score(form_data, ruca_code: int):
    """
    Calculates REAP score based on the multi-category "Scoring Breakdown by Field" PDF.
    This uses REAL user inputs from the entire flow, not just defaults.
    """
    score = 0
    max_possible_score = 0
    breakdown = []

    # Mapping of form_data keys to scoring criteria
    # This assumes form_data now contains all necessary keys from the deep dive screens
    biz_type = form_data.get("unified_business_type")
    reap_history = form_data.get("q7_reap_funding_history")
    project_type = form_data.get("q2_project_type_reap")
    technology = form_data.get("reap_specific_technology", form_data.get("q3_primary_technology"))
    ghg_emissions = form_data.get("q4_ghg_emissions")
    zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    is_ec_mock = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("energy community") > 0
    doc_score = form_data.get('mock_doc_score_reap', 0) # Still mocked for now
    
    # 1. Applicant Type/Prior History (Max 15 pts) - From REAP PDF page 3 & 4
    max_possible_score += 15
    applicant_pts = 0
    if reap_history == "First-time applicant":
        applicant_pts += 15
    elif reap_history == "Prior award (2+ years ago)":
        applicant_pts += 5
    else: # Recent award
        applicant_pts += 2
    # Add bonus for business type (e.g., Tribal, Rural Co-op) if applicable, but cap at 15
    if biz_type in ["Tribal Entity", "Rural Cooperative", "Farm / Agriculture"]:
        applicant_pts += 5
    applicant_pts = min(applicant_pts, 15)
    score += applicant_pts
    breakdown.append(f"Applicant Type & History: {applicant_pts}/15 pts")

    # 2. Project Priority (Max 15 pts)
    max_possible_score += 15
    project_priority_pts = 0
    if project_type == "Combined RES + EEI":
        project_priority_pts = 15
    elif project_type == "Energy Efficiency Improvement (EEI)":
        project_priority_pts = 12
    elif project_type == "Renewable Energy System (RES)":
        project_priority_pts = 8
    score += project_priority_pts
    breakdown.append(f"Project Priority: {project_priority_pts}/15 pts")

    # 3. Technology Impact (Varies 0-10 pts) - From REAP PDF page 3
    # Criteria: "Less common or 'underutilized' technologies may receive priority consideration.
    # Anaerobic digesters, geothermal, and biomass often score well!
    max_possible_score += 10
    tech_impact_pts = 0
    if technology in ["Anaerobic Digester", "Geothermal"]:
        tech_impact_pts = 10
    elif technology == "Battery Storage (with solar)":
        tech_impact_pts = 8 # Grid resiliency
    elif technology in ["Solar PV", "Wind Turbine"]:
        tech_impact_pts = 6 # Common, effective RES
    elif technology == "Lighting / HVAC Upgrade":
        tech_impact_pts = 5 # Common, effective EEI
    elif technology == "Other":
        tech_impact_pts = 2
    score += tech_impact_pts
    breakdown.append(f"Technology Impact: {tech_impact_pts}/10 pts")

    # 4. Environmental Benefit (Max 10 pts)
    max_possible_score += 10
    env_pts = 3
    if ghg_emissions == "Yes" or ghg_emissions is True:
        env_pts = 10
    score += env_pts
    breakdown.append(f"Environmental Benefit (GHG): {env_pts}/10 pts")

    # 5. Geographic Priority (Max 10 pts)
    max_possible_score += 10
    geo_pts = 0

    # RUCA-based scoring (as per USDA documentation)
    # Codes 4-10 are generally considered rural/non-metro for REAP.
    # We can add granularity: more points for more rural codes.
    if ruca_code >= 10: # Rural
        geo_pts = 8
    elif ruca_code >= 7: # Small town / isolated rural
        geo_pts = 6
    elif ruca_code >= 4: # Micropolitan / town adjacent
        geo_pts = 4
    
    # Add points for Energy Community status
    if is_ec_mock:
        geo_pts += 2 # Add a couple of points for EC, can be adjusted
    
    geo_pts = min(geo_pts, 10) # Cap at the maximum for this category
    score += geo_pts
    breakdown.append(f"Geographic Priority (Rural/EC): {geo_pts}/10 pts (RUCA Code: {ruca_code})")

    # 6. Document Score (Max 20 pts, from slider)
    max_possible_score += 20
    score += doc_score
    breakdown.append(f"Document Score (Simulated): {doc_score}/20 pts")

    # 7. Cost Effectiveness (Max 10 pts) - Stacking other incentives
    max_possible_score += 10
    cost_eff_pts = 0
    other_incentives_count = len([p for p in st.session_state.get("incentives_to_model", []) if p not in ['usda_reap_grant', 'itc_macrs']])
    if other_incentives_count > 0:
        cost_eff_pts = 5 + min(other_incentives_count, 5)   # 5 base points + 1 per extra incentive up to 10
    score += cost_eff_pts
    breakdown.append(f"Cost Effectiveness (Stacking): {cost_eff_pts}/10 pts")

    normalized_score = int((score / max_possible_score) * 100) if max_possible_score > 0 else 0
    return score, breakdown, normalized_score


# --- Incentive Eligibility Engine ---
def check_incentive_eligibility(form_data):
    """
    Iterates through all defined incentives and checks eligibility based on form_data.
    Returns a list of eligible incentive objects.
    """
    eligible_incentives = []
    
    # Add mock location and business flags to form_data for evaluation
    # In a real app, these would come from more robust checks
    zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    form_data['is_rural_mock'] = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("rural") > 0
    form_data['location_state_mock'] = "CA" if zip_for_check.startswith("9") else "Other"   # Very simple mock

    for incentive in INCENTIVE_PROGRAMS:
        is_eligible = True   # Assume eligible until a rule fails
        for rule in incentive["eligibility_rules"]:
            
            # --- NEW: Check for a custom function rule ---
            if "function" in rule:
                if rule["function"] == "is_reap_eligible":
                    # Call our dedicated REAP eligibility function
                    reap_is_eligible, _ = is_reap_eligible(form_data) # We only need the boolean result here
                    if reap_is_eligible != rule["expected_result"]:
                        is_eligible = False; break
                    
            else: # Original field-based rule logic
                field = rule["field"]
                condition = rule["condition"]
                required_value = rule["value"]
                
                user_value = form_data.get(field)
                
                # Rule Evaluation Logic ---
                if user_value is None:
                    is_eligible = False; break   # Can't evaluate if data is missing

                if condition == "is_one_of":
                    if user_value not in required_value: is_eligible = False; break
                elif condition == "is_true":
                    if not user_value: is_eligible = False; break
                elif condition == "is_greater_than":
                    if not float(user_value) > required_value: is_eligible = False; break
                elif condition == "is_equal_to":
                    if user_value != required_value: is_eligible = False; break
                # Add more conditions as needed (is_less_than, contains, etc.)

        if is_eligible:
            eligible_incentives.append(incentive)
            
    return eligible_incentives


# --- NEW for Week 2/Screen 6: Detailed MACRS & Bonus Depreciation Engine ---
def calculate_detailed_depreciation_benefit(
    depreciable_basis: float,
    placed_in_service_year: int,
    assumed_tax_rate: float = 0.24   # A reasonable default for commercial
) -> dict:
    """
    Calculates the detailed Year 1 tax benefit from Bonus and MACRS depreciation.
    Follows the logic from "Step 6" of the Order of Operations.
    """
    if depreciable_basis <= 0:
        return {
            "bonus_depreciation_value": 0.0,
            "macrs_year1_value": 0.0,
            "year_1_total_depreciation_tax_benefit": 0.0,
            "bonus_depreciation_rate": 0.0
        }

    # Bonus depreciation rates phase down over time
    bonus_rates = {2022: 1.00, 2023: 0.80, 2024: 0.60, 2025: 0.40, 2026: 0.20}
    # For years beyond 2026, the bonus is 0.
    bonus_dep_rate = bonus_rates.get(placed_in_service_year, 0.0)
    
    # 1. Calculate Bonus Depreciation
    bonus_depreciation_value = depreciable_basis * bonus_dep_rate
    
    # 2. Calculate Remaining Basis for standard MACRS
    remaining_basis_for_macrs = depreciable_basis - bonus_depreciation_value
    
    # 3. Apply Year 1 of the 5-year MACRS schedule to the remaining basis
    macrs_year1_rate = 0.20   # For a 5-year property, Year 1 is 20%
    macrs_year1_value = remaining_basis_for_macrs * macrs_year1_rate
    
    # 4. The total tax BENEFIT is the sum of depreciation values multiplied by the tax rate
    total_year1_depreciation_value = bonus_depreciation_value + macrs_year1_value
    year_1_tax_benefit = total_year1_depreciation_value * assumed_tax_rate
    
    return {
        "bonus_depreciation_value": bonus_depreciation_value,
        "macrs_year1_value": macrs_year1_value,
        "year_1_total_depreciation_tax_benefit": year_1_tax_benefit,
        "bonus_depreciation_rate": bonus_dep_rate
    }


# --- Master Financial Calculation Engine for Final Dashboard (Screen 6) ---
def perform_final_incentive_stack_calculations(form_data):
    """
    Orchestrates the full, compliant calculation following the Order of Operations
    and includes all user-selected grants.
    """
    results = {
        "total_project_cost": 0.0,
        "reap_grant_final": 0.0,
        "total_itc_value": 0.0,
        "federal_share_percent": 0.0,
        "is_fed_share_compliant": True,
        "correct_depreciable_basis": 0.0,
        "year_1_depreciation_tax_benefit": 0.0,
        "depreciation_details": {},  # To store the detailed depreciation breakdown for display
        "other_grant_values": {},   # To store results of other selected grants
        "total_grant_and_tax_benefits": 0.0,
        "final_net_cost": 0.0,
        "final_roi": 0.0,
        "final_payback": float('inf'),  # Default to infinity
        "cash_positive_note": ""   # Key to hold special messages
    }

    # Step 1: Establish Total Project Cost (CapEx)
    total_project_cost = float(form_data.get('system_cost_for_reap', form_data.get('calculator_system_cost_output', 0.0)))
    if total_project_cost <= 0:
        return results # Can't calculate without a project cost
    results["total_project_cost"] = total_project_cost

    # Step 2 & 3: Calculate REAP Grant and Total ITC (without adjustments first)
    # REAP Grant Amount (only for eligible projects)
    reap_grant_potential = 0.0 # Default to 0
    # Check the flag we set during the eligibility check.
    if st.session_state.form_data.get('is_reap_eligible_flag', False):
        # Only run the calculation if the user is eligible.
        reap_project_type = form_data.get("q2_project_type_reap", "Renewable Energy System (RES)")
        max_cap = REAP_GRANT_CAPS_BY_TECH.get(reap_project_type, 500000)
        reap_grant_potential = min(0.5 * total_project_cost, max_cap)
    
    # ITC
    base_itc_value = total_project_cost * BASE_ITC_RATE
    zip_for_check = form_data.get("unified_address_zip", "").split(',')[-1].strip()[:5]
    is_ec_mock = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("energy community") > 0
    itc_bonus_rate = 0.0
    if is_ec_mock: itc_bonus_rate += MOCK_NON_REAP_INCENTIVES_PREVIEW.get("bonus_energy_community_potential", 0.0)
    itc_bonus_value = total_project_cost * itc_bonus_rate
    total_itc_value = base_itc_value + itc_bonus_value
    results["total_itc_value"] = total_itc_value

    # Step 4: Federal Share Compliance Check (REAP + ITC only)
    federal_share = (reap_grant_potential + total_itc_value) / total_project_cost
    results["federal_share_percent"] = federal_share
    
    reap_grant_final = reap_grant_potential
    if federal_share > 0.50:
        results["is_fed_share_compliant"] = False
        max_allowed_from_reap = (0.50 * total_project_cost) - total_itc_value
        reap_grant_final = max(0, max_allowed_from_reap)
    results["reap_grant_final"] = reap_grant_final
    
    # Step 5: Calculate Correct Depreciable Basis
    itc_basis_reduction = 0.5 * total_itc_value
    correct_depreciable_basis = total_project_cost - itc_basis_reduction
    results["correct_depreciable_basis"] = correct_depreciable_basis

    # Step 6: Apply Detailed MACRS and Bonus Depreciation (for Commercial)
    depreciation_details = {}
    year_1_dep_benefit = 0.0
    if form_data.get("unified_business_type") in ["Commercial / Business", "Farm / Agriculture"]:
        # We need a "Placed in Service Year" - let's add it to the `form_data` over Screen 5
        # For now, we will default to 2024 for a robust calculation.
        placed_in_service_year = int(form_data.get("placed_in_service_year", 2024))
        
        depreciation_details = calculate_detailed_depreciation_benefit(
            depreciable_basis=correct_depreciable_basis,
            placed_in_service_year=placed_in_service_year
        )
        year_1_dep_benefit = depreciation_details.get("year_1_total_depreciation_tax_benefit", 0.0)
    
    results["year_1_depreciation_tax_benefit"] = year_1_dep_benefit
    results["depreciation_details"] = depreciation_details # Store the full breakdown

    # --- Step 7. Calculate other selected grants ---
    other_grant_values = {}
    selected_program_ids = st.session_state.get("incentives_to_model", [])
    for program in INCENTIVE_PROGRAMS:
        # We only calculate the non-core ones here. REAP, ITC, MACRS are handled above.
        if program['id'] in selected_program_ids and program['id'] not in ["usda_reap_grant", "itc_macrs"]:
            # Get the lambda function
            calc_func = program.get("calculation_logic")
            if not calc_func: continue

            # ROBUST DYNAMIC ARGUMENT MAPPING ---
            # Inspect the function to see what arguments it needs
            required_args = inspect.getfullargspec(calc_func).args
            
            # Build the args dictionary to pass to the function
            args_to_pass = {}
            all_inputs_found = True
            for arg_name in required_args:
                # The key in form_data is constructed as `program_id_arg_name`
                # But our lambda definition is generic. Let's adjust the key lookup.
                # The keys in form_data are like 'vapg_vapg_project_cost'. Let's find the base name.

                # A better way is to define keys in `incentive_definitions.py` consistently.
                # Our current key is f"{program['id']}_{inp['id']}". Let's assume the lambda arg matches inp['id'].

                # Find the input definition for this argument
                input_def = next((inp for inp in program.get("calculation_inputs", []) if inp['id'] == arg_name), None)
                if not input_def:
                    all_inputs_found = False; break
                
                form_key = f"{program['id']}_{arg_name}"
                user_value = form_data.get(form_key)
                
                if user_value is None:
                    all_inputs_found = False; break
                    
                # INTELLIGENT TYPE CASTING ---
                expected_type = input_def.get("data_type", "string") # Default to string if not specified
                
                try:
                    if expected_type == "float":
                        args_to_pass[arg_name] = float(user_value)
                    elif expected_type == "integer":
                        args_to_pass[arg_name] = int(user_value)
                    elif expected_type == "boolean":
                        # st.toggle/checkbox values are already bools, but this is a safe cast
                        args_to_pass[arg_name] = bool(user_value)
                    else: # "string"
                        args_to_pass[arg_name] = str(user_value)
                except (ValueError, TypeError):
                    st.error(f"Invalid input for '{input_def['label']}'. Expected a {expected_type}.")
                    all_inputs_found = False; break # Missing input
            
            if all_inputs_found:
                try:
                    value = calc_func(**args_to_pass) # Pass arguments as keyword arguments
                    other_grant_values[program['name']] = value
                except Exception as e:
                    other_grant_values[program['name']] = f"Calc Error: {e}"
            else:
                 other_grant_values[program['name']] = "Missing Inputs"
            
    results["other_grant_values"] = other_grant_values
    
    # Step 8: Calculate FINAL Annual Savings from the full dispatch model
    # The calculator results are used as the basis for the new & accurate savings value.
    calc_results = st.session_state.get("calculator_results_display", {})
    financials_from_calc = calc_results.get("financials", {})
    annual_savings_final = financials_from_calc.get("total_annual_savings", 0.0)

    # Step 9. Final Summary Calculations
    total_other_grants_value = sum(v for v in other_grant_values.values() if isinstance(v, (int, float)))
    
    total_benefits = reap_grant_final + total_itc_value + year_1_dep_benefit + total_other_grants_value
    results["total_grant_and_tax_benefits"] = total_benefits

    # After all benefits are calculated:
    total_benefits = results.get("total_grant_and_tax_benefits", 0)
    
    # Net cost considers all grants and tax benefits
    net_cost_final = total_project_cost - total_benefits
    results["final_net_cost"] = net_cost_final

    if annual_savings_final > 0:
        
        if net_cost_final > 0:
            # Standard case: There is a net cost to recover.
            results["final_roi"] = (annual_savings_final / net_cost_final) * 100
            results["final_payback"] = net_cost_final / annual_savings_final
        else:
            # Windfall case: Incentives meet or exceed project cost.
            # ROI is effectively infinite, and payback is immediate.
            results["final_roi"] = float('inf') # We'll represent this as "Immediate" or "Cash Positive" in the UI.
            results["final_payback"] = 0.0 # Payback period is 0 years.
            # Add a note for the UI to display.
            upfront_cash_positive = abs(net_cost_final)
            results["cash_positive_note"] = f"Project is cash-positive by ${upfront_cash_positive:,.0f} in Year 1 from incentives alone!"
    else:
        # No savings case: Payback is infinite, ROI is 0 or negative.
        results["final_roi"] = 0.0
        results["final_payback"] = float('inf')
    
    # --- NEW: Preparing data specifically for the Waterfall Chart ---
    waterfall_steps = {
        "Total Project Cost": total_project_cost,
        "REAP Grant": -reap_grant_final, # Negative because it reduces cost
        "Federal ITC": -total_itc_value,
        "Depreciation Benefit (Y1)": -year_1_dep_benefit
    }

    # Add other grants to the waterfall
    for grant_name, grant_value in results.get("other_grant_values", {}).items():
        if isinstance(grant_value, (int, float)) and grant_value > 0:
            # Shorten name for chart clarity if needed
            short_name = grant_name.replace(" Program", "").replace(" Grant", "")
            waterfall_steps[short_name] = -grant_value

    results["waterfall_chart_data"] = waterfall_steps
        
    return results