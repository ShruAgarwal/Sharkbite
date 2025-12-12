import requests
import numpy as np
import pandas as pd
import streamlit as st
from sharkbite_engine.utils import (
    SOLAR_SYSTEM_COST_PER_KW, DEFAULT_DC_AC_RATIO,
    BASE_ITC_RATE, INVERTER_EFF, LOAN_RATE,
    NET_METER_CREDIT_FACTOR, MACRS_TAX_RATE,
    generate_hourly_rate_schedule
)

PVWATTS_API_ENDPOINT_V8 = "https://developer.nrel.gov/api/pvwatts/v8.json"
NREL_API_KEY_HOLDER = {"key": None}


@st.cache_data(ttl=3600)
def geocode_address_nominatim(address):
    """
    Returns (lat, lon, error_message_or_none).
    Handles ambiguity between 5-digit house numbers and ZIP codes.
    """

    if not address:
        return "Address not provided."
    
    base_url = f"https://nominatim.openstreetmap.org/search?format=json"
    headers = {'User-Agent': 'SharkbiteStreamlitApp/2.3'}
    
    # Check if the input is ONLY a 5-digit number (a ZIP code).
    address_clean = address.strip()
    if address_clean.isdigit() and len(address_clean) == 5:
        # If it's just a ZIP, use the specific 'postalcode' parameter to avoid ambiguity.
        geo_url = f"{base_url}&postalcode={address_clean}&country=US"
    else:
        # For any other format (full address), use the general query parameter 'q'.
        # This lets Nominatim's powerful parser handle the full string correctly.
        geo_url = f"{base_url}&q={address}"

    try:
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
def fetch_pvwatts_hourly_production(lat, lon, system_capacity_kw,
                                azimuth=180, tilt=20, array_type=1, module_type=0, losses=14):

    api_key = NREL_API_KEY_HOLDER["key"]
    system_capacity_float = float(system_capacity_kw)
    if not api_key:
        return "NREL API Key is missing."
    if not all([lat is not None, lon is not None, system_capacity_kw is not None]):
        return "Latitude, longitude, or system capacity missing for PVWatts."
    if system_capacity_float <= 0:
        # Gracefully handle 0 kW system size without an API call
        return [0.0] * 8760, None
    
    if system_capacity_float > 500000: # PVWatts limit
        return f"Invalid system capacity: {system_capacity_kw} kW. Must be > 0 and <= 500,000 kW."

    params = {
        "api_key": api_key,
        "lat": lat,
        "lon": lon,
        "system_capacity": system_capacity_float,
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
        if "outputs" in data and "ac" in data["outputs"]:
            return data["outputs"]["ac"]  # <--- hourly AC system production
        else: # Handle API specific errors if any
            errors = data.get('errors', ['Unknown PVWatts API response error (v8).'])
            error_msg = str(errors[0]) if isinstance(errors, list) and errors else str(errors)
            return f"PVWatts API response error: {error_msg}" 
        
    except requests.exceptions.RequestException as e:
        return f"PVWatts API call error: {e}"
    except Exception as e:
        return f"Unexpected error processing PVWatts (v8) data: {e}"
    

# --- Battery Sizing Logic ---
def get_battery_specs(backup_pref: str):
    """
    Returns battery kWh and cost based on user preference.
    """
    # This logic is simpler and more aligned now
    if backup_pref == "Essentials Only (10 kWh)":
        return 10.0 # 10 kWh, $12k
    elif backup_pref == "Whole House Backup (25 kWh)":
        return 25.0 # 25 kWh, $25k
    else: # No Backup
        return 0.0


# --- This generates a flat load profile for now ---
def synthesize_hourly_load_profile(annual_kwh, user_type):
    if annual_kwh <= 0 and user_type == "Homeowner":
        return [0.0] * 8760
    return [annual_kwh / 8760.0] * 8760


# --- BATTERY DISPATCH ALGORITHM ---
def run_hourly_dispatch_simulation(
    hourly_load,
    hourly_solar,
    battery_kwh,
    inverter_size_kw,
    min_battery_reserve_pct,
    self_consumption_priority,
    tou_enabled,
    peak_hours, # Default PG&E-like peak rates: 4 PM to 9 PM == range(16, 21)
    battery_eff=0.90
):
    """
    Simulates hourly energy flow with a TOU-aware, self-consumption priority.
    This logic is adapted directly from `dispatch` function.
    """
    soc = 0.0 # State of Charge in kWh
    import_kwh = np.zeros(8760)
    export_kwh = np.zeros(8760)
    solar_to_load = np.zeros(8760)
    solar_to_battery = np.zeros(8760)
    battery_to_load = np.zeros(8760)
    
    min_soc_kwh = battery_kwh * (min_battery_reserve_pct / 100.0)
    
    # Calculates what the inverter can actually output to AC (clipping)
    inverter_output_ac = np.minimum(hourly_solar, inverter_size_kw)
    # Clipped DC power is "free" energy available to a DC-coupled battery
    clipped_dc_power = np.maximum(0, hourly_solar - inverter_size_kw)

    for hour in range(8760):
        L = hourly_load[hour]
        S_ac = inverter_output_ac[hour]
        S_clipped = clipped_dc_power[hour]
        is_peak_hour = hour % 24 in peak_hours
        
        # 1. Charge from "free" clipped DC power first
        available_solar_for_charge = S_clipped + (S_ac * INVERTER_EFF)
        if available_solar_for_charge > 0 and soc < battery_kwh:
            charge = min(available_solar_for_charge, battery_kwh - soc)
            soc += charge * battery_eff
            solar_to_battery[hour] = charge / INVERTER_EFF # Record power drawn from solar
            S_ac -= charge / INVERTER_EFF
        
        # 2. Solar AC directly serves on-site load
        to_load = min(L, S_ac)
        solar_to_load[hour] = to_load
        L -= to_load
        S_ac -= to_load

        # 3. Handle remaining AC solar: Charge battery earlier and then (compare with remaining battery power) to export
        if S_ac > 0:
            # --- SELF-CONSUMPTION LOGIC ---
            # If any solar is still left after charging and battery is full, decide whether to export
            if soc >= battery_kwh and self_consumption_priority:
                export_kwh[hour] = S_ac
                # If self_consumption_priority is True, remaining S_ac is NOT curtailed (discarded)
                
            if not self_consumption_priority:
                export_kwh[hour] = S_ac
                # If NOT prioritizing self-consumption, export any remaining solar.

                
        # 4. Battery Discharging to meet remaining load
        if L > 0 and soc > min_soc_kwh:
            discharge_decision = False # Should we discharge in this hour?

            if tou_enabled and is_peak_hour:
                # Always discharge during peak hours if there's a load
                discharge_decision = True

            # Off-peak: Only discharge if the user's goal is self-consumption
            if tou_enabled and self_consumption_priority and not is_peak_hour:
                discharge_decision = True
                # If self_consumption_priority is False, we do nothing (pass)
                # and save the battery for the peak!

            if not tou_enabled and self_consumption_priority:
                # If there's no TOU, the only goal is self-consumption. Always discharge to meet load.
                discharge_decision = True

            if discharge_decision:
                discharge_available = soc - min_soc_kwh
                discharge_amount = min(discharge_available, L / INVERTER_EFF)
                soc -= discharge_amount
                battery_to_load[hour] = discharge_amount * INVERTER_EFF
                L -= discharge_amount * INVERTER_EFF
    
        # 5. Grid Import (Last Resort)
        if L > 0:
            import_kwh[hour] = L

    # --- FINAL KPI CALCULATIONS ---
    total_solar_production = np.sum(hourly_solar)
    total_load = np.sum(hourly_load)
    
    # Total self-consumption is the sum of solar that went to load and solar that went to battery
    total_self_consumed_solar = np.sum(solar_to_load) + np.sum(solar_to_battery)
    
    # Total energy provided by the on-site system is self-consumed solar + what the battery discharged
    total_onsite_supply = np.sum(solar_to_load) + np.sum(battery_to_load)
    
    self_consumption_rate = (total_self_consumed_solar / total_solar_production) * 100 if total_solar_production > 0 else 0
    grid_independence_rate = (total_onsite_supply / total_load) * 100 if total_load > 0 else 0
    
    annual_import = np.sum(import_kwh)
    annual_export = np.sum(export_kwh)
        
    return {
        "annual_import_kwh": annual_import,
        "annual_export_kwh": annual_export,
        "hourly_import": import_kwh,
        "hourly_export": export_kwh,
        # Pass hourly series for detailed financial calculation
        "hourly_solar": hourly_solar,
        "hourly_load": hourly_load,
        "hourly_solar_to_load": solar_to_load,
        "hourly_battery_to_load": battery_to_load,
        "self_consumption_rate_percent": self_consumption_rate * 100,
        "grid_independence_rate_percent": min(grid_independence_rate, 100.0),
        "net_grid_interaction_kwh": annual_import - annual_export
    }


def calculate_future_electrification_load(ev_miles=0, ev_efficiency=4.0, heat_pump_btu=0, heat_pump_cop=3.0):
    """
    Calculates the additional annual kWh load from future electrification.
    """

    additional_kwh = 0.0
    try:
        if ev_miles > 0 and ev_efficiency > 0:
            additional_kwh += float(ev_miles) / float(ev_efficiency)
        if heat_pump_btu > 0 and heat_pump_cop > 0:
            # Conversion: 1 kWh = 3412 BTU
            kwh_for_heat_pump = (float(heat_pump_btu) / 3412.0) / float(heat_pump_cop)
            additional_kwh += kwh_for_heat_pump
    except (ValueError, TypeError):
        return 0.0 # Return 0 if inputs are invalid
    return additional_kwh


def calculate_final_financials(
    capex, dispatch_results, hourly_rates, hourly_load, user_type
):
    """
    Calculates final financials based on hourly dispatch results and TOU rates.
    This logic is adapted from the `financials` and `monthly_cashflow` functions.
    """

    # Define hourly rates based on TOU settings
    # Create an index for the full year to map hours
    hourly_index = pd.to_datetime(np.arange(8760), unit='h', origin=pd.Timestamp('2025-01-01'))

    # Unpack hourly arrays from dispatch results
    hourly_solar_to_load = dispatch_results['hourly_solar_to_load']
    hourly_battery_to_load = dispatch_results['hourly_battery_to_load']
    hourly_import = dispatch_results['hourly_import']
    hourly_export = dispatch_results['hourly_export']

    # --- Revenue Shift: Calculate savings based on avoided costs and export revenue ---
    # 1. Cost Avoided by Solar (Direct Self-Consumption)
    cost_avoided_by_solar = np.sum(hourly_solar_to_load * hourly_rates)

    # 2. Cost Avoided by Battery (TOU/Self-Consumption)
    cost_avoided_by_battery = np.sum(hourly_battery_to_load * hourly_rates)

    annual_export_revenue = np.sum(hourly_export * hourly_rates * NET_METER_CREDIT_FACTOR)

    # Total Annual Savings is the sum of these three value streams
    total_annual_savings = cost_avoided_by_solar + cost_avoided_by_battery + annual_export_revenue
    
    # Incentives
    itc_val = capex * BASE_ITC_RATE
    macrs_val = 0
    if user_type == "Commercial / Business":
        macrs_basis = capex - 0.5 * itc_val
        macrs_val = macrs_basis * 0.85 * MACRS_TAX_RATE

    net_cost = capex - itc_val - macrs_val
    payback = net_cost / total_annual_savings if total_annual_savings > 0 else float('inf')
    
    # Using the 25-year ROI formula
    roi_25_yr = ((total_annual_savings * 25 - net_cost) / net_cost) * 100 if net_cost > 0 else float('inf')

    # --- Builds Monthly Cash Flow DataFrame ---
    # Convert numpy arrays to pandas Series with a DatetimeIndex for easy resampling
    import_series = pd.Series(hourly_import, index=hourly_index)
    export_series = pd.Series(hourly_export, index=hourly_index)
    rates_series = pd.Series(hourly_rates, index=hourly_index)
    
    monthly_df = pd.DataFrame({
        "Import_kWh": import_series.resample("ME").sum(),
        "Export_kWh": export_series.resample("ME").sum(),
        "Remaining Grid Import Cost ($)": (import_series * rates_series).resample("ME").sum(),
        "Net Export Revenue ($)": (export_series * rates_series * NET_METER_CREDIT_FACTOR).resample("ME").sum()
    })

    monthly_df["Original Bill Cost ($)"] = pd.Series(hourly_load * hourly_rates, index=hourly_index).resample("ME").sum()
    monthly_df["Cost Avoided by Solar ($)"] = pd.Series(hourly_solar_to_load * hourly_rates, index=hourly_index).resample("ME").sum()
    monthly_df["Cost Avoided by Battery ($)"] = pd.Series(hourly_battery_to_load * hourly_rates, index=hourly_index).resample("ME").sum()
    monthly_df["New Bill ($)"] = monthly_df["Remaining Grid Import Cost ($)"] - monthly_df["Net Export Revenue ($)"]
    monthly_df["Monthly Savings ($)"] = monthly_df["Original Bill Cost ($)"] - monthly_df["New Bill ($)"]
    
    # Monthly Cashflow
    # Simplified loan payment for cash flow chart
    monthly_payment = (net_cost * LOAN_RATE) / 12 if net_cost > 0 else 0
    monthly_df["Loan_Payment_$"] = -monthly_payment   # Negative cash flow
    monthly_df["Net_Cash_Flow_$"] = monthly_df["Monthly Savings ($)"] - monthly_payment
    monthly_df.index = monthly_df.index.strftime('%b')   # Format index to 'Jan', 'Feb', etc.

    return {
        "total_annual_savings": total_annual_savings,
        "savings_from_battery_tou_shifting": cost_avoided_by_battery,
        "total_capex": capex,
        "itc_amount": itc_val,
        "macrs_benefit": macrs_val,
        "net_cost": net_cost,
        "payback_years": payback,
        "roi_percent_25_yr": roi_25_yr,
        "monthly_cash_flow_df": monthly_df
    }


def perform_solar_battery_calculations(inputs):
    """
    Main orchestrator for the calculator screen.
    Incorporates Future Load and Self-Consumption logic.
    Takes a dictionary of inputs from the calculator screen and returns all calculated metrics.
    Inputs: address, monthly_kwh_usage, cost_per_kwh, system_size_kw, backup_pref, user_type
    """
    results = {
        "lat": None, "lon": None,
        "geo_error": None, "ac_annual": None,
        "ac_monthly": None, "pv_error": None,
        "battery_kwh": 0, "battery_units": 0,
        "battery_cost": 0, "backup_duration_days": 0,
        "future_load_kwh": 0.0, "dispatch_results": {},
        "financials": {} # To store results from calculate_initial_financials_for_calculator
    }

    # 1. Geocode
    results["lat"], results["lon"] = geocode_address_nominatim(inputs.get("address"))
    if results["geo_error"]:
        return results # Stop if geocoding fails
    
    # 2. Battery Sizing (Get specs first)
    battery_kwh = get_battery_specs(inputs.get("backup_pref"))
    results.update({"battery_kwh": battery_kwh})

    # 3. Hourly PVWatts
    # Utilizes user input to calculate inverter size from generated solar power
    inverter_size_kw_ac = inputs.get("inverter_size_kw", 0)

    hourly_solar = fetch_pvwatts_hourly_production(results["lat"], results["lon"], inputs.get("system_size_kw",0))
    if results["pv_error"]:
        return results  # Stop if PVWatts fails
    
    # Calculate annual and monthly summaries from the hourly data
    ac_annual_kwh = sum(hourly_solar) if hourly_solar else 0

    # The annual production is the SUM of the hourly production list
    results["ac_annual"] = ac_annual_kwh
    results["ac_monthly"] = None # We can reconstruct monthly from hourly if needed, but annual is key
    # Create monthly summary (this is a simplified way, more accurate would be to use calendar days)
    # monthly_solar_production = [sum(hourly_solar[i:i + 730]) for i in range(0, len(hourly_solar), 730)]
    # results["ac_monthly"] = monthly_solar_production[:12] # Ensure it's 12 months

    hourly_solar_dc = np.array(hourly_solar) * DEFAULT_DC_AC_RATIO  # Estimate DC production
    st.session_state.hourly_solar_production_for_dispatch = hourly_solar

    # 4.1 Future Load and Total Projected Usage
    future_load_kwh = calculate_future_electrification_load(
        inputs.get("ev_annual_miles"), inputs.get("ev_efficiency_mi_kwh"),
        inputs.get("heat_pump_btu_yr"), inputs.get("heat_pump_cop")
    )
    results["future_load_kwh"] = future_load_kwh

    # Use the annual usage calculated in the UI for the load profile
    annual_kwh_est = inputs.get('annual_kwh_est', 0)
    total_projected_annual_kwh = annual_kwh_est + future_load_kwh
    st.session_state.form_data['total_projected_annual_kwh'] = total_projected_annual_kwh

    # 4.2 Synthesize HOURLY load profile
    hourly_load = synthesize_hourly_load_profile(total_projected_annual_kwh, inputs.get("user_type"))
    st.session_state.hourly_load_for_dispatch = hourly_load

    # 5. Generate Accurate Hourly Rate Schedule (`rate_plan` is now a key user input)
    selected_rate_plan = inputs.get("rate_plan", "Residential E-TOU-C")
    hourly_rates = generate_hourly_rate_schedule(selected_rate_plan)

    # 6. Run Self-Consumption Dispatch Algorithm
    tou_enabled_input = inputs.get("tou_enabled") # Pass TOU checkbox
    dispatch_results = run_hourly_dispatch_simulation(
        hourly_load=hourly_load,
        hourly_solar=hourly_solar_dc,
        inverter_size_kw=inverter_size_kw_ac,
        battery_kwh=battery_kwh,
        min_battery_reserve_pct=inputs.get("min_battery_reserve_pct", 0), # <-- New user input
        self_consumption_priority=inputs.get("self_consumption_priority"), # <-- New user input
        tou_enabled=tou_enabled_input,
        peak_hours=hourly_rates
    )
    results.update(dispatch_results)

    # 7. Calculate financials using the new dispatch results
    solar_system_cost = inputs.get("system_size_kw", 0) * SOLAR_SYSTEM_COST_PER_KW
    battery_cost = battery_kwh * inputs.get("calc_battery_cost", 0)
    results.update({
        "pv_system_cost": solar_system_cost,
        "battery_cost": battery_cost
    })
    total_capex = solar_system_cost + battery_cost

    results["financials"] = calculate_final_financials(
        capex=total_capex,
        dispatch_results=dispatch_results,
        hourly_load=hourly_load,
        hourly_rates=hourly_rates, # <-- PASSING THE DYNAMIC TOU RATE SCHEDULE
        user_type=inputs.get("user_type")
    )

    # Add backup duration for display
    avg_daily_load = total_projected_annual_kwh / 365
    results["backup_duration_days"] = battery_kwh / avg_daily_load if avg_daily_load > 0 else 0

    return results