import sys, os
import pytest
import streamlit as st
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from sharkbite_engine.claude_service import (
    get_ai_recommendations,
    analyze_financial_data_with_claude,
    get_core_equipment_recommendation,
    get_ai_ppa_analysis
)

MOCK_RECOMMENDATIONS_RESPONSE = {
    "text": """
* Consider applying for the **CALIFORNIA SWEEP GRANT**, as it is ideal for agricultural producers.
* To improve your project's resilience, model a 'Whole House Backup' battery option.
* Your **REAP GRANT** score could be improved by completing a technical energy audit.
    """,
    "usage": {"input_tokens": 150, "output_tokens": 75}
}

# A mock response from the Bedrock API
MOCK_FINANCIAL_ANALYSIS_RESPONSE = {
    "text": """
    ```json
    {
        "executive_summary": "This is a mock summary.",
        "key_opportunities": ["Opportunity 1"],
        "primary_risks": ["Risk 1"],
        "mitigation_strategies": ["Strategy 1"]
    }
    ```
    """,
    "usage": {"input_tokens": 100, "output_tokens": 50}
}

# Mock response for the CORE equipment function
MOCK_CORE_RESPONSE = {
    "text": """
    ```json
    {
        "recommended_equipment_type": "Construction & Agricultural Equipment",
        "base_voucher_amount": 500000,
        "enhancement_percent": 0.15,
        "total_voucher_amount": 575000,
        "explanation": "Based on the user's 'Farm / Agriculture' profile, this is the most suitable category."
    }
    ```
    """,
    "usage": {"input_tokens": 120, "output_tokens": 90}
}

# Mock response for the PPA analysis function
MOCK_PPA_RESPONSE = {
    "text": """
    ```json
    {
        "primary_trade_off": "PPA offers zero upfront cost, while ownership provides greater long-term savings.",
        "itc_impact": "The Federal ITC is a significant benefit for ownership, directly reducing net cost.",
        "future_load_impact": "Your future EV and heat pump loads will make solar savings even more valuable."
    }
    ```
    """,
    "usage": {"input_tokens": 200, "output_tokens": 110}
}

# --- Create a pytest fixture to clear the cache ---
@pytest.fixture(autouse=True)
def clear_streamlit_cache():
    """A fixture that automatically clears the Streamlit cache before each test."""
    st.cache_data.clear()
    yield

# =============================================================
# TEST FOR INCENTIVE RECOMMENDATION FUNCTION
# =============================================================

# Use the 'patch' decorator to replace the real API call with our mock
@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_ai_recommendations_success(mock_call_claude):
    """
    Tests the happy path for get_ai_recommendations, ensuring it correctly
    parses a well-formatted, multi-line string with bullet points.
    """
    # Configure the mock to return our predefined recommendations response
    mock_call_claude.return_value = MOCK_RECOMMENDATIONS_RESPONSE
    
    mock_user_inputs = {"location_zip": "93210", "user_type": "Farm / Agriculture"}
    
    # Call the function being tested
    result = get_ai_recommendations("Incentive Preview", mock_user_inputs)
    
    # Assertions
    mock_call_claude.assert_called_once()
    assert isinstance(result, list)
    assert len(result) == 3

    # Check that the parsing logic (stripping '*', capitalizing) worked correctly
    assert result[0] == "Consider applying for the **CALIFORNIA SWEEP GRANT**, as it is ideal for agricultural producers."
    assert result[1] == "To improve your project's resilience, model a 'Whole House Backup' battery option."


@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_ai_recommendations_api_error(mock_call_claude):
    """
    Tests the failure path for get_ai_recommendations, ensuring it returns
    an empty list when the API call returns an error.
    """
    # Configure the mock to simulate an API error
    mock_call_claude.return_value = {"error": "Access Denied"}
    
    result = get_ai_recommendations("Incentive Preview", {})
    
    # Assert that the function returns an empty list as a graceful fallback
    assert result == []

# =============================================================
# TEST FOR FINANCIAL ANALYSIS FUNCTION
# =============================================================

@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_comprehensive_ai_analysis_success(mock_call_claude):
    """
    Tests the success case for the financial analysis AI function.
    """
    
    # Configure the mock to return our predefined response
    mock_call_claude.return_value = MOCK_FINANCIAL_ANALYSIS_RESPONSE
    
    mock_project_data = {"total_project_cost": 100000}
    
    # Call the function we're testing
    result = analyze_financial_data_with_claude(mock_project_data)
    
    # Assertions: Check that the function behaved as expected
    mock_call_claude.assert_called_once() # Ensure the API was called
    assert "error" not in result
    assert result["executive_summary"] == "This is a mock summary."
    assert "Opportunity 1" in result["key_opportunities"]


@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_comprehensive_ai_analysis_bad_json(mock_call_claude):
    """
    Tests the failure case for the financial analysis AI function.
    An edge case: What if the API returns invalid JSON?
    """

    mock_call_claude.return_value = {"text": "This is not JSON.", "usage": {}}
    result = analyze_financial_data_with_claude({"total_project_cost": 100000})
    
    assert "error" in result
    assert "AI response was not in the expected format" in result["error"]
    #assert "was not in the expected JSON format" in result["error"]
    assert result["raw_response"] == "This is not JSON."

# =============================================================
# TEST FOR CORE EQUIPMENT RECOMMENDATION FUNCTION
# =============================================================

@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_core_equipment_recommendation_success(mock_call_claude):
    """
    Tests the happy path for CORE recommendations with a perfect JSON response.
    """

    mock_call_claude.return_value = MOCK_CORE_RESPONSE
    result = get_core_equipment_recommendation({"user_type": "Farm / Agriculture"})
    
    mock_call_claude.assert_called_once()
    assert "error" not in result
    assert result["recommended_equipment_type"] == "Construction & Agricultural Equipment"
    assert result["total_voucher_amount"] == 575000


@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_core_equipment_recommendation_incomplete_json(mock_call_claude):
    """
    Tests the guardrail for CORE recommendations when the JSON is missing required keys.
    """

    incomplete_response = {
        "text": """```json{"recommended_equipment_type": "Large Forklifts"}```""",
        "usage": {}
    }
    mock_call_claude.return_value = incomplete_response
    result = get_core_equipment_recommendation({"user_type": "Commercial / Business"})
    
    assert "error" in result
    assert "AI response was not in the expected format" in result["error"]

# ===============================================================
# TEST FOR PPA ANALYSIS FUNCTION
# ===============================================================

@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_ai_ppa_analysis_success(mock_call_claude):
    """
    Tests the happy path for PPA analysis with a perfect JSON response.
    """

    mock_call_claude.return_value = MOCK_PPA_RESPONSE

    mock_ppa_data = {
        "ownership_total_savings_25_yr": 50000,
        "ppa_total_cost_25_yr": 35000
    }
    mock_future_load = {
        "ev_charging_annual_kwh": 4000,
        "heat_pump_annual_kwh": 6000
    }
    
    result = get_ai_ppa_analysis(
        ppa_vs_ownership_data=mock_ppa_data,
        future_load_data=mock_future_load
    )
    
    mock_call_claude.assert_called_once()
    assert "error" not in result
    assert "PPA offers zero upfront cost" in result["primary_trade_off"]
    assert "future EV and heat pump loads" in result["future_load_impact"]


@patch('sharkbite_engine.claude_service.call_claude_on_bedrock')
def test_get_ai_ppa_analysis_bad_json(mock_call_claude):
    """
    Tests the failure path for PPA analysis when the response is not valid JSON.
    """
    
    mock_call_claude.return_value = {"text": "A simple string response.", "usage": {}}

    mock_ppa_data = {"ownership_total_savings_25_yr": 50000}
    mock_future_load = {"ev_charging_annual_kwh": 4000}

    result = get_ai_ppa_analysis(
        ppa_vs_ownership_data=mock_ppa_data,
        future_load_data=mock_future_load
    )
    
    assert "error" in result
    assert "AI response was not in the expected format" in result["error"]
    assert result["raw_response"] == "A simple string response."