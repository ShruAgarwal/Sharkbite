import numpy as np
import sys
import os
import pytest
from unittest.mock import patch

# --- CONFIGURATION ---
# Add project root to path to allow importing from `sharkbite_engine` folder
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from sharkbite_engine.solar_calculator_logic import (
    NREL_API_KEY_HOLDER,
    run_hourly_dispatch_simulation,
    calculate_final_financials,
    fetch_pvwatts_hourly_production,
    synthesize_hourly_load_profile
)
from sharkbite_engine.utils import (
    INVERTER_EFF, 
    BASE_ITC_RATE,
    NET_METER_CREDIT_FACTOR,
    MACRS_TAX_RATE
)

# ============ TEST DATA & FIXTURES ============
@pytest.fixture
def profiles():
    """
    Defines 3 distinct user profiles for testing.
    """
    return {
        "Profile_A_Ag_Large": {
            "type": "Farm / Agriculture",
            "zip": "93210", # Coalinga, CA (Likely REAP eligible)
            "system_size_kw": 50.0, # Large system edge case
            "battery_kwh": 0.0, # No battery
            "monthly_kwh": 8000,
            "rate_plan": "Ag Rate AG-4B"
        },
        "Profile_B_Commercial_Battery": {
            "type": "Commercial / Business",
            "zip": "90210", # Beverly Hills (Urban, likely no REAP)
            "system_size_kw": 20.0,
            "battery_kwh": 25.0, # Whole house backup size
            "monthly_kwh": 3000,
            "rate_plan": "Residential E-TOU-C" # Using Res plan for office scenario
        },
        "Profile_C_Homeowner_Small": {
            "type": "Homeowner",
            "zip": "59718", # Bozeman, MT
            "system_size_kw": 4.0, # Small system edge case
            "battery_kwh": 10.0, # Essentials backup
            "monthly_kwh": 500,
            "rate_plan": "Residential E-TOU-C"
        }
    }

@pytest.fixture
def seasonal_load_profile():
    """
    Generates a synthetic 8760 hourly load profile with seasonal variation.
    High Winter (Heating), Low Spring, High Summer (AC).
    """
    # Simple sine wave approximation for temp-based load
    hours = np.arange(8760)
    # Peak in Jan (0) and July (approx 4380)
    base_load = 1.0
    seasonal_factor = 0.5 * np.cos((hours - 4380) / 8760 * 2 * np.pi) 
    # Add daily variation (Day higher than night)
    daily_factor = 0.3 * np.sin(hours / 24 * 2 * np.pi)
    
    return np.abs(base_load + seasonal_factor + daily_factor)

@pytest.fixture
def bell_curve_solar_profile():
    """
    Generates a single day 'bell curve' of solar production, padded to 8760.
    Used for calculating exact battery charge/discharge behavior.
    """
    # 24 hour array
    day_profile = np.array([0,0,0,0,0,0, 0.1, 0.5, 2.0, 4.0, 5.0, 5.5, 5.0, 4.0, 2.0, 0.5, 0.1, 0,0,0,0,0,0,0])
    return np.tile(day_profile, 365)


# ======================= 1. DISPATCH LOGIC TESTS =======================
def test_dispatch_logic_commercial_large_export(profiles):
    """
    Profile A: Large 50kW system, No Battery.
    Verifies that when Production > Load, the excess is correctly logged as Export.
    """
    profile = profiles["Profile_A_Ag_Large"]
    
    # Create massive solar spike to force export
    hourly_solar = np.zeros(8760)
    hourly_solar[12] = 60.0 # Noon spike of 60kW
    
    # Create small load
    hourly_load = np.zeros(8760)
    hourly_load[12] = 10.0 # 10kW load
    
    # Inverter clipping check: System is 50kW.
    # Solar input is 60kW. Inverter output AC should be capped at 50kW (assuming logic handles it).
    # Logic note: source code takes inverter_size_kw input.
    
    results = run_hourly_dispatch_simulation(
        hourly_load=hourly_load,
        hourly_solar=hourly_solar,
        battery_kwh=0, # No battery
        inverter_size_kw=profile["system_size_kw"], # 50kW
        min_battery_reserve_pct=0,
        self_consumption_priority=False,
        tou_enabled=False,
        peak_hours=[]
    )
    
    # Expected: 
    # Solar DC = 60. Inverter Cap = 50. 
    # AC Available = 50.
    # Load = 10.
    # Export = 50 - 10 = 40.
    
    # Note: If logic uses DC input for production without clipping in the array passed, 
    # we need to ensure the inverter_size argument does the clipping.
    # Based on source: `inverter_output_ac = np.minimum(hourly_solar, inverter_size_kw)`
    
    assert results['hourly_export'][12] == 40.0
    assert results['hourly_import'][12] == 0.0
    assert results['hourly_solar_to_load'][12] == 10.0


@pytest.mark.parametrize("self_consumption_priority, expected_export_gt", [
    (False, 8.0), # When False, it should export the excess solar.
    (True, -1.0)  # When True, it should NOT export as the battery is not yet full.
])
def test_dispatch_battery_cycle_efficiency_corrected(self_consumption_priority, expected_export_gt):
    """
    Tests battery charging and verifies export behavior based on self-consumption priority.
    - When priority is False, excess solar is exported.
    - When priority is True, excess solar is curtailed (not exported) because the
      battery is not yet 100% full, and the logic prioritizes on-site use.
    """
    
    # Setup: 10kW Inverter. Solar 10kW for 2 hours. Battery 10kWh.
    hourly_solar = np.zeros(8760)
    hourly_solar[0] = 10.0 
    hourly_solar[1] = 10.0 
    
    hourly_load = np.zeros(8760) # No load, purely charging
    
    results = run_hourly_dispatch_simulation(
        hourly_load=hourly_load,
        hourly_solar=hourly_solar,
        battery_kwh=10.0,
        inverter_size_kw=10.0,
        min_battery_reserve_pct=0,
        self_consumption_priority=self_consumption_priority,
        tou_enabled=False,
        peak_hours=[]
    )
    
    export_h1 = results['hourly_export'][1]

    if expected_export_gt > 0:
        # Assert that we see the expected export
        assert export_h1 > expected_export_gt
    else:
        # Assert that there is zero export, as per the self-consumption logic
        assert export_h1 == 0.0


def test_dispatch_min_reserve_limit_corrected():
    """
    Replaces the failed 'min_reserve_limit' test.
    Accounts for the fact that the battery must be charged with losses 
    before it can discharge.
    """
    # 1. Charge Phase
    hourly_solar = np.zeros(8760)
    hourly_solar[0] = 100.0 # Massive spike to fill battery
    
    # 2. Discharge Phase
    hourly_load = np.zeros(8760)
    hourly_load[5] = 100.0 # Huge load later
    
    battery_kwh = 10.0
    reserve_pct = 50 # 50% Reserve = 5.0 kWh floor
    
    results = run_hourly_dispatch_simulation(
        hourly_load=hourly_load,
        hourly_solar=hourly_solar,
        battery_kwh=battery_kwh,
        inverter_size_kw=100.0,
        min_battery_reserve_pct=reserve_pct,
        self_consumption_priority=True,
        tou_enabled=False,
        peak_hours=[]
    )
    
    # Math Walkthrough:
    # Hour 0: Solar 100. Battery 10.
    # Charge = 10. 
    # SOC becomes: 0 + (10 * 0.9 [battery_eff]) = 9.0 kWh.
    # The battery is NOT 100% full. It is at 9.0 kWh.
    
    # Hour 5: Load 100.
    # Reserve limit = 5.0 kWh.
    # Available to discharge = 9.0 (current SOC) - 5.0 (Reserve) = 4.0 kWh.
    
    # Logic: `discharge_amount = min(discharge_available, L / INVERTER_EFF)`
    # `discharge_amount = min(4.0, 100/0.96) = 4.0`.
    
    # Battery to Load (AC output) = discharge_amount * INVERTER_EFF
    # 4.0 * 0.96 = 3.84 kWh.
    
    actual_battery_output = results['hourly_battery_to_load'][5]

    # Assert using the imported variable
    expected_output = 4.0 * INVERTER_EFF
    
    # Assert with tight tolerance now that we did the math
    assert actual_battery_output == pytest.approx(expected_output, abs=0.01)
    
    # Verify Import = Load - Battery Output
    # 100 - 3.84 = 96.16
    assert results['hourly_import'][5] == pytest.approx(96.16, abs=0.01)


# ======================= 2. VALIDATION & FINANCIAL TESTS =======================
def test_pvwatts_api_integration_mocked():
    """
    Verifies that the PVWatts fetching function correctly parses a known
    JSON structure (mocked) and handles errors.
    """

    mock_response_json = {
        "outputs": {
            "ac": [0.0, 0.1, 0.5, 1.0], # Shortened for test
            "solrad_annual": 5.5
        }
    }
    
    with patch('requests.get') as mock_get:
        # Success case
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response_json
        
        # We also need to mock NREL_API_KEY_HOLDER in the logic file implicitly
        # or pass the key validation check.
        # Assuming code handles key presence, we call the function.
        
        # NOTE: The function `fetch_pvwatts_hourly_production` expects 8760 points usually,
        # but for unit testing parsing, we verify it returns what the JSON gave. 
        NREL_API_KEY_HOLDER['key'] = "TEST_KEY"
        result = fetch_pvwatts_hourly_production(34.0, -118.0, 5.0)
        
        # Verify it extracts the 'ac' list
        assert result == [0.0, 0.1, 0.5, 1.0]


def test_financials_seasonal_impact():
    """
    Validates that accurate Rate Plan data affects savings.
    Summer peaks should generate more savings if production aligns with it.
    """
    # Create 1 day of data repeated
    # Peak is 4PM-9PM (Hours 16-20).
    # Solar generates during day (Hours 8-18).
    # Overlap is Hours 16-18.
    
    dispatch_results = {
        'hourly_solar_to_load': np.zeros(8760),
        'hourly_battery_to_load': np.zeros(8760),
        'hourly_import': np.zeros(8760),
        'hourly_export': np.zeros(8760)
    }
    
    # Inject 1000 kWh of solar self-consumption specifically during Summer Peak hours (e.g. Hour 17)
    # Summer Peak Rate (e.g. $0.55) vs Winter Offpeak ($0.35)
    dispatch_results['hourly_solar_to_load'][17] = 1000.0 # High value single hour for clarity
    
    # Setup Rates: High Rate vs Low Rate scenarios
    rates_high = np.zeros(8760)
    rates_high[17] = 0.60
    
    rates_low = np.zeros(8760)
    rates_low[17] = 0.20
    
    flat_load = np.zeros(8760)
    
    # Calculate A (High Rates)
    res_high = calculate_final_financials(
        capex=10000, 
        dispatch_results=dispatch_results, 
        hourly_rates=rates_high, 
        hourly_load=flat_load, 
        user_type="Homeowner"
    )
    
    # Calculate B (Low Rates)
    res_low = calculate_final_financials(
        capex=10000, 
        dispatch_results=dispatch_results, 
        hourly_rates=rates_low, 
        hourly_load=flat_load, 
        user_type="Homeowner"
    )
    
    # Verify Savings
    # High: 1000 * 0.60 = 600
    # Low: 1000 * 0.20 = 200
    assert res_high['total_annual_savings'] > res_low['total_annual_savings']
    assert res_high['total_annual_savings'] == pytest.approx(600.0)


# ======================= 3. EDGE CASE TESTS =======================
@pytest.mark.parametrize("profile_key", ["Profile_A_Ag_Large", "Profile_B_Commercial_Battery"])
def test_edge_case_zero_battery_high_export(profiles, profile_key):
    """
    Verifies that the MACRS benefit is correctly applied ONLY to commercial
    user types, while other financial metrics like ITC and savings are
    calculated for all applicable profiles.
    Verifies simple Net Metering logic (Export Revenue).
    Edge case: 50kW system, 0 Battery.
    """

    profile = profiles[profile_key]
    capex_value = 100000
    
    dispatch = {
        'hourly_solar_to_load': np.zeros(8760),
        'hourly_battery_to_load': np.zeros(8760),
        'hourly_import': np.zeros(8760),
        # 10,000 kWh exported
        'hourly_export': np.full(8760, 10000/8760) 
    }
    
    rates = np.full(8760, 0.10) # Flat $0.10/kWh retail
    
    results = calculate_final_financials(
        capex=capex_value,
        dispatch_results=dispatch,
        hourly_rates=rates,
        hourly_load=np.zeros(8760),
        user_type=profile["type"]
    )
    
    # 1. Verify metrics that apply to ALL profiles
    # Savings should come entirely from Export Revenue.
    # Export Revenue = 10,000 kWh * Rate (0.10) * NEM_FACTOR (0.75)
    expected_savings = 10000 * 0.10 * NET_METER_CREDIT_FACTOR
    assert results['total_annual_savings'] == pytest.approx(expected_savings, abs=1.0)

    # ITC Calculation
    expected_itc = capex_value * BASE_ITC_RATE
    assert results['itc_amount'] == expected_itc

    # 2. Conditionally verify the MACRS benefit
    if profile["type"] == "Commercial / Business":
        
        # Basis = CapEx - (0.5 * ITC)
        macrs_basis = capex_value - (0.5 * expected_itc)
        # Benefit = Basis * 0.85 (simplified factor) * Tax Rate
        expected_macrs_benefit = macrs_basis * 0.85 * MACRS_TAX_RATE
        assert results['macrs_benefit'] == pytest.approx(expected_macrs_benefit, abs=1.0)
    else:
        # For any other user type, MACRS must be zero.
        assert results['macrs_benefit'] == 0


def test_load_profile_generation():
    """
    Tests that load profiles are generated correctly for different user types.
    """
    # Commercial vs Homeowner shapes
    # Test valid input
    load_home = synthesize_hourly_load_profile(3650, "Homeowner")
    assert len(load_home) == 8760
    assert np.sum(load_home) == pytest.approx(3650.0, abs=1.0)
    
    # Test flat fallback for 0 usage
    load_zero = synthesize_hourly_load_profile(0, "Homeowner")
    assert np.sum(load_zero) == 0