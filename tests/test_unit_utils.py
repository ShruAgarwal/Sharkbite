import sys
import os
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from sharkbite_engine.utils import is_reap_eligible, calculate_autosized_system_kw

# Test REAP Eligibility based on business type
@pytest.mark.parametrize("business_type, expected", [
    ("Farm / Agriculture", True),
    ("Homeowner", False),
    ("Nonprofit", False),
    ("Commercial / Business", True)
])
def test_is_reap_eligible_business_type(business_type, expected):
    """
    Verifies REAP eligibility for different business types, using a known rural ZIP.
    """

    form_data = {"unified_business_type": business_type, "unified_address_zip": "59718"} # A known rural ZIP
    
    is_eligible, _ = is_reap_eligible(form_data)
    assert is_eligible == expected


# Test REAP Eligibility based on location (RUCA logic)
@pytest.mark.parametrize("zip_code, expected_eligibility, expected_reason", [
    ("59718", True, "appears to be in a REAP-eligible rural area"), # Bozeman, MT (Rural)
    ("90210", False, "is in a metropolitan area"), # Beverly Hills, CA (Urban)
    ("10001", False, "is in a metropolitan area"), # NYC (Urban - heuristic)
    ("69201", True, "appears to be in a REAP-eligible rural area"), # Valentine, NE (Rural - heuristic)
    ("123", False, "No valid 5-digit ZIP code could be extracted from the address."),
    ("ABCDE", False, "No valid 5-digit ZIP code could be extracted from the address")
])
def test_is_reap_eligible_location(zip_code, expected_eligibility, expected_reason):
    """
    Verifies REAP eligibility based on different ZIP codes, using an eligible business type.
    """

    form_data = {"unified_business_type": "Farm / Agriculture", "unified_address_zip": zip_code}
    is_eligible, reason = is_reap_eligible(form_data)
    assert is_eligible == expected_eligibility
    assert expected_reason in reason


def test_calculate_autosized_system_kw():
    """Unit test for the auto-sizing function."""
    assert calculate_autosized_system_kw(1200) == 10.7 # (1200 / (5 * 30 * 0.75))
    assert calculate_autosized_system_kw(0) == 0.0
    assert calculate_autosized_system_kw(-500) == 0.0