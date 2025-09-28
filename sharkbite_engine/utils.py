from sharkbite_engine.incentive_definitions import INCENTIVE_PROGRAMS
from datetime import date
import numpy as np
import pandas as pd
import inspect  # To inspect function arguments
import streamlit as st

# --- Important Constants ---
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

# AVG_SUN_HOURS_FOR_AUTOSIZE = 5
# DERATE_FACTOR_FOR_AUTOSIZE = 0.75
# SOLAR_SYSTEM_COST_PER_KW = 2500
# BATTERY_UNIT_KWH = 13.5
# BATTERY_UNIT_COST = 12000
# CALCULATOR_SIMPLIFIED_MACRS_RATE = 0.26 # Flat MACRS @26% of (System + Battery Cost) for commercial

# --- NEW: Detailed TOU Schedule Configuration ---
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

# Mock Eligibility Check for Unified Intake
ELIGIBILITY_CHECKS_UNIFIED_INTAKE = {
    "55714": {"text": "This ZIP (mock) qualifies as RURAL and is in an ENERGY COMMUNITY! Potential 10% ITC bonus and strong REAP eligibility.", "type": "success"},
    "90210": {"text": "This ZIP (mock) is URBAN and likely NOT in a designated Energy Community for ITC bonus.", "type": "warning"},
    "default": {"text": "Enter a valid 5-digit ZIP from your address for specific eligibility insights.", "type": "info"}
}

# --- NEW: Static Tooltips / Helper Texts ---
# This dictionary will hold all static helper texts. It is more reliable and cost-effective than calling an LLM.
STATIC_TOOLTIPS = {
    # General Terms
    "ITC": "The Investment Tax Credit (ITC) is a dollar-for-dollar reduction in federal income taxes for a percentage of the cost of a renewable energy system.",
    "MACRS": "The Modified Accelerated Cost Recovery System (MACRS) is a tax depreciation system that allows businesses to recover the cost of property over a specified time, providing a significant tax benefit.",
    "REAP_GRANT": "The USDA Rural Energy for America Program (REAP) provides grants for renewable energy systems and energy efficiency improvements for rural small businesses and agricultural producers.",

    # California CORE Specific Tooltips (from your document)
    "CA_CORE_PROGRAM": "The CORE program provides upfront, point-of-sale vouchers to help cover the cost of zero-emission off-road equipment in California.",
    "CA_CORE_ENHANCEMENT": "Small businesses and projects in low-income or disadvantaged communities may receive up to 25% extra in voucher value.",
    "CA_CORE_NO_SCRAP": "You do not need to scrap old diesel equipment to qualify for the CORE voucher."
}


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


# --- DETAILED REAP SCORING ENGINE (Replaces simplified formula) ---
def calculate_detailed_reap_score(form_data):
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
    is_rural_mock = ELIGIBILITY_CHECKS_UNIFIED_INTAKE.get(zip_for_check, {}).get("text", "").lower().count("rural") > 0
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
    if is_rural_mock and is_ec_mock:
        geo_pts = 10
    elif is_rural_mock or is_ec_mock:
        geo_pts = 7
    score += geo_pts
    breakdown.append(f"Geographic Priority (Rural/EC): {geo_pts}/10 pts")

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


# --- NEW: TOU Rate Schedule Generator ---
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
    # REAP
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