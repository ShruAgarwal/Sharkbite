import streamlit as st
import requests
# import pandas as pd
# import math
from sharkbite_engine.utils import (
    AVG_SUN_HOURS_FOR_AUTOSIZE, DERATE_FACTOR_FOR_AUTOSIZE,
    SOLAR_SYSTEM_COST_PER_KW, BATTERY_UNIT_KWH, BATTERY_UNIT_COST,
    BASE_ITC_RATE, CALCULATOR_SIMPLIFIED_MACRS_RATE, LOAN_RATE
)

PVWATTS_API_ENDPOINT_V8 = "https://developer.nrel.gov/api/pvwatts/v8.json"
NREL_API_KEY_HOLDER = {"key": None}


@st.cache_data(ttl=3600)
def geocode_address_nominatim(address):
    if not address:
        return "Address not provided."
    try:
        geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
        headers = {'User-Agent': 'SharkbiteStreamlitApp/1.1'}
        response = requests.get(geo_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
        return f"Address '{address}' not found by Nominatim."
    except requests.exceptions.RequestException as e:
        return f"Geocoding API error: {e}"
    except Exception as e:
        return f"Geocoding parsing error: {e}"


@st.cache_data
def fetch_pvwatts_production_v8(lat, lon, system_capacity_kw,
                                azimuth=180, tilt=20, array_type=1, module_type=0, losses=14):

    api_key = NREL_API_KEY_HOLDER["key"]
    system_capacity_float = float(system_capacity_kw)
    if not api_key:
        return "NREL API Key is missing."
    if not all([lat is not None, lon is not None, system_capacity_kw is not None]):
        return "Latitude, longitude, or system capacity missing for PVWatts."
    if system_capacity_float <= 0 or system_capacity_float > 500000: # PVWatts limit
        return f"Invalid system capacity: {system_capacity_kw} kW. Must be > 0 and <= 500,000 kW."

    params = {
        "api_key": api_key,
        "lat": lat,
        "lon": lon,
        "system_capacity": system_capacity_kw,
        "azimuth": azimuth,
        "tilt": tilt,
        "array_type": array_type,
        "module_type": module_type,
        "losses": losses,
        "timeframe": "hourly" 
    }
    try:
        response = requests.get(PVWATTS_API_ENDPOINT_V8, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "outputs" in data and "ac_annual" in data["outputs"] and "ac_monthly" in data["outputs"]:
            return data["outputs"]["ac_annual"], data["outputs"]["ac_monthly"]
        else: # Handle API specific errors if any
            errors = data.get('errors', ['Unknown PVWatts API response error (v8).'])
            error_str = str(errors[0]) if isinstance(errors, list) and errors else str(errors)
            return f"PVWatts API response error: {error_str}"
    except requests.exceptions.RequestException as e:
        return f"PVWatts API call error: {e}"
    except Exception as e:
        return f"Unexpected error processing PVWatts (v8) data: {e}"


def calculate_solar_system_size_from_usage(monthly_usage_kwh, avg_sun_hours=AVG_SUN_HOURS_FOR_AUTOSIZE, derate_factor=DERATE_FACTOR_FOR_AUTOSIZE):
    if monthly_usage_kwh <= 0 or avg_sun_hours <=0 or derate_factor <=0:
        return 0
    return round(monthly_usage_kwh / (avg_sun_hours * 30 * derate_factor), 1)


def calculate_battery_storage(backup_pref, monthly_usage_kwh):
    battery_kwh = 0
    battery_units = 0
    if backup_pref == "Essentials Only":
        battery_kwh = BATTERY_UNIT_KWH
    elif backup_pref == "Whole House Backup":
        avg_daily_usage = monthly_usage_kwh / 30
        battery_kwh = avg_daily_usage * 1.5

    if battery_kwh > 0:
        battery_units = int((battery_kwh + BATTERY_UNIT_KWH - 1) // BATTERY_UNIT_KWH)
    
    battery_cost = battery_units * BATTERY_UNIT_COST
    avg_daily_load = monthly_usage_kwh / 30
    backup_duration_days = battery_kwh / avg_daily_load if avg_daily_load > 0 and battery_kwh > 0 else 0
    
    return battery_kwh, battery_units, battery_cost, backup_duration_days


# -------- Cash Flow --------
def calculate_financials(
    system_size_kw,
    battery_cost,
    ac_annual_kwh,
    user_business_type_val,
    monthly_usage_kwh,
    electricity_per_kwh_rate
):
    results = {
        "solar_system_cost": 0.0,
        "total_cost_with_battery": 0.0,
        "itc_amount_calculator": 0.0,
        "macrs_simplified_calculator": 0.0,
        "annual_savings_calculator": 0.0,
        "net_cost_calculator": 0.0,
        "roi_calculator_percent": 0.0,
        "payback_calculator_years": float('inf'), # Default to inf if no savings or positive cost
        "annual_solar_production_kwh": 0.0,
        "net_metering_credit_calculator": 0.0,
        "monthly_cashflow": 0.0
    }

    # --- Defensive Type Coercion and Validation for Inputs ---
    try:
        # Ensure all inputs that are part of calculations are floats or ints
        # System Size
        sys_size_kw = float(system_size_kw) if system_size_kw is not None else 0.0
        if sys_size_kw < 0: sys_size_kw = 0.0 # Cannot be negative

        # Battery Cost
        batt_cost = float(battery_cost) if battery_cost is not None else 0.0
        if batt_cost < 0: batt_cost = 0.0

        # Annual Solar Production
        ac_annual_kwh = float(ac_annual_kwh) if ac_annual_kwh is not None else 0.0
        if ac_annual_kwh < 0: ac_annual_kwh = 0.0
        results["annual_solar_production_kwh"] = ac_annual_kwh


        # Monthly Usage
        monthly_usage = float(monthly_usage_kwh) if monthly_usage_kwh is not None else 0.0
        if monthly_usage < 0: monthly_usage = 0.0
        total_annual_usage_kwh = monthly_usage * 12

        # Electricity Rate
        elec_rate = float(electricity_per_kwh_rate) if electricity_per_kwh_rate is not None else 0.0
        if elec_rate < 0: elec_rate = 0.0

    except (ValueError, TypeError) as e:
        # This error should ideally be caught before calling this function,
        # but as a safeguard:
        st.error(f"Input data error for financial calculation: {e}. Please check inputs.")
        return results

    # --- Calculations (as per the script/formulas, ensuring numeric operations) ---
    
    # Solar System Cost
    solar_system_cost = sys_size_kw * SOLAR_SYSTEM_COST_PER_KW
    results["solar_system_cost"] = solar_system_cost

    # Total Cost (Solar + Battery)
    total_cost_with_battery = solar_system_cost + batt_cost
    results["total_cost_with_battery"] = total_cost_with_battery

    # ITC Amount (on total cost with battery)
    itc_amount_val = total_cost_with_battery * BASE_ITC_RATE
    results["itc_amount_calculator"] = itc_amount_val

    # Simplified MACRS Benefit (for commercial)
    macrs_simplified_benefit = 0.0
    if user_business_type_val == "Commercial / Business": # Ensure this string matches exactly
        macrs_simplified_benefit = total_cost_with_battery * CALCULATOR_SIMPLIFIED_MACRS_RATE
    results["macrs_simplified_calculator"] = macrs_simplified_benefit

    # Net Metering Credit (Excess production * (rate * 0.75))
    excess_kwh_annual = ac_annual_kwh - total_annual_usage_kwh
    # Only apply credit if there's actual excess and rate is positive
    net_metering_credit = 0.0
    if excess_kwh_annual > 0 and elec_rate > 0:
        net_metering_credit = excess_kwh_annual * (elec_rate * DERATE_FACTOR_FOR_AUTOSIZE)
    results["net_metering_credit_calculator"] = net_metering_credit

    # Annual Savings from Solar
    # Value of solar produced that offsets usage, PLUS net metering credits
    kwh_offsetting_usage = min(ac_annual_kwh, total_annual_usage_kwh)
    savings_from_offset_usage = kwh_offsetting_usage * elec_rate
    total_annual_savings_value = savings_from_offset_usage + net_metering_credit
    results["annual_savings_calculator"] = total_annual_savings_value

    # Net Cost after these initial incentives
    net_cost_calculator = total_cost_with_battery - itc_amount_val
    if user_business_type_val == "Commercial / Business":
        net_cost_calculator -= macrs_simplified_benefit
    results["net_cost_calculator"] = net_cost_calculator
    
    # ROI and Payback
    if net_cost_calculator > 0 and total_annual_savings_value > 0:
        results["roi_calculator_percent"] = (total_annual_savings_value / net_cost_calculator) * 100.0
        results["payback_calculator_years"] = net_cost_calculator / total_annual_savings_value
    elif total_annual_savings_value > 0: # Net cost is zero or negative, instant payback/high ROI
        results["roi_calculator_percent"] = float('inf') # Or a very large number / "Immediate"
        results["payback_calculator_years"] = 0.0
    else: # No savings, so infinite payback and zero (or negative if cost > 0) ROI
        results["roi_calculator_percent"] = 0.0 if net_cost_calculator >= 0 else float('-inf')
        results["payback_calculator_years"] = float('inf')

    
    # Simplified interest-only payment for mock-up purposes
    monthly_payment = (net_cost_calculator * LOAN_RATE) / 12
    monthly_savings = total_annual_savings_value / 12
    monthly_cashflow = monthly_savings - monthly_payment
    results["monthly_cashflow"] = monthly_cashflow

    return results


def perform_solar_battery_calculations(inputs):
    """
    Takes a dictionary of inputs from the calculator screen and returns all calculated metrics.
    Inputs: address, monthly_kwh_usage, cost_per_kwh, system_size_kw, backup_pref, user_type
    """
    results = {
        "lat": None, "lon": None, "geo_error": None,
        "ac_annual": None, "ac_monthly": None, "pv_error": None,
        "battery_kwh": 0, "battery_units": 0, "battery_cost": 0, "backup_duration_days": 0,
        "financials": {} # To store results from calculate_initial_financials_for_calculator
    }

    # 1. Geocode
    # results["geo_error"]
    results["lat"], results["lon"] = geocode_address_nominatim(inputs.get("address"))

    if results["geo_error"]:
        return results # Stop if geocoding fails

    # 2. PVWatts
    # results["pv_error"]
    results["ac_annual"], results["ac_monthly"] = fetch_pvwatts_production_v8(
        results["lat"], results["lon"], inputs.get("system_size_kw", 0)
    )

    if results["pv_error"]:
        return results # Stop if PVWatts fails

    # 3. Battery Sizing
    results["battery_kwh"], results["battery_units"], results["battery_cost"], results["backup_duration_days"] = \
        calculate_battery_storage(
            inputs.get("backup_pref"), inputs.get("monthly_kwh_usage", 0)
        )

    # 4. Initial Financials (with simplified MACRS)
    results["financials"] = calculate_financials(
        inputs.get("system_size_kw", 0),
        results["battery_cost"],
        results["ac_annual"] if results["ac_annual"] is not None else 0,
        inputs.get("user_type"), # Pass user_type ("Homeowner" or "Commercial / Business")
        inputs.get("monthly_kwh_usage", 0),
        inputs.get("cost_per_kwh", 0),
    )
    return results

# def calculate_financials(system_size_kw, ac_annual_kwh, monthly_usage_kwh, cost_per_kwh_rate,
#                          battery_cost_val, user_business_type_val, include_macrs=True):
    
#     try:
#         system_size_kw = float(system_size_kw if system_size_kw is not None else 0.0)
#         battery_cost = float(battery_cost_val if battery_cost_val is not None else 0.0)
#         ac_annual_solar_kwh = float(ac_annual_kwh if ac_annual_kwh is not None else 0.0)
#         monthly_kwh_usage = float(monthly_usage_kwh if monthly_usage_kwh is not None else 0.0)
#         cost_per_kwh_rate = float(cost_per_kwh_rate if cost_per_kwh_rate is not None else 0.0)
#     except (ValueError, TypeError):
#         st.error('Could not convert values!')
#         # battery_cost = 0.0
#         # ac_annual_solar_kwh = 0.0
#         # monthly_kwh_usage = 0.0
#         # electricity_rate = 0.0


#     total_solar_system_cost = system_size_kw * SOLAR_SYSTEM_COST_PER_KW
#     total_system_and_battery_cost = total_solar_system_cost + battery_cost
    
#     federal_itc_amount = total_system_and_battery_cost * BASE_ITC_RATE
    
#     macrs_benefit = 0.0
#     if user_business_type_val == "Commercial / Business" and include_macrs:
#         # "MACRS Depreciation Benefit: 26% x (System Cost + Battery Cost)"
#         macrs_benefit = total_system_and_battery_cost * CALCULATOR_SIMPLIFIED_MACRS_RATE


#     # Net Metering Credit from formulas
#     total_annual_usage_kwh = monthly_kwh_usage * 12
#     excess_kwh_annual = ac_annual_solar_kwh - total_annual_usage_kwh
#     net_metering_credit_annual = max(0.0, excess_kwh_annual * (cost_per_kwh_rate * DERATE_FACTOR_FOR_AUTOSIZE))
    
#     annual_savings_from_solar = net_metering_credit_annual + (ac_annual_solar_kwh * cost_per_kwh_rate)
    
#     # Corrected Annual Savings: Value of solar produced that offsets usage, plus net metering credits
#     # kwh_offsetting_usage = min(ac_annual_kwh, total_annual_usage_kwh)
#     # savings_from_offset_usage = kwh_offsetting_usage * cost_per_kwh_rate
#     # total_annual_savings_value = savings_from_offset_usage + net_metering_credit_annual

#     net_cost_after_incentives = total_system_and_battery_cost - federal_itc_amount - macrs_benefit

#     # Let's use Annual Savings / Net Cost for a simple ROI
#     roi_percent = (annual_savings_from_solar / net_cost_after_incentives) * 100.0 if net_cost_after_incentives > 0 else float('inf') if annual_savings_from_solar > 0 else 0
    
#     # Payback Period (Years) = Net Cost After Incentives / Annual Savings
#     payback_years = net_cost_after_incentives / annual_savings_from_solar if annual_savings_from_solar > 0 else float('inf')


#     # Loan payment calculation is simplified in the script. A real one needs PITI.
#     # loan_rate = 0.06 # Example, should be input or config
#     # loan_term_years = 15
#     # monthly_payment_mock = (net_cost_after_incentives * loan_rate) / 12 # Highly simplified
#     # monthly_cash_flow = (annual_savings_from_solar / 12) - monthly_payment_mock
    
#     # For Week 1, let's just return the components
#     return {
#         "total_solar_system_cost": total_solar_system_cost,
#         "total_system_and_battery_cost": total_system_and_battery_cost,
#         "federal_itc_amount": federal_itc_amount,
#         "macrs_benefit": macrs_benefit,
#         "net_metering_credit_annual": net_metering_credit_annual,
#         "total_annual_savings_value": annual_savings_from_solar,
#         "net_cost_after_incentives": net_cost_after_incentives,
#         "roi_percent": roi_percent,
#         "payback_years": payback_years
#         # "monthly_cash_flow": monthly_cash_flow # Defer this for more robust loan modeling
#     }