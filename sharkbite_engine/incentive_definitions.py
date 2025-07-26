INCENTIVE_PROGRAMS = [
    # ==============================================================================
    # 1. CORE FEDERAL PROGRAMS (Already part of the main flow, defined here for consistency)
    # ==============================================================================
    {
        "id": "usda_reap_grant",
        "name": "USDA REAP Grant",
        "level": "Federal", "type": "Grant",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture", "Rural Cooperative", "Commercial / Business"]},
            {"field": "is_rural_mock", "condition": "is_true", "value": None}
        ],
        "calculation_inputs": [], # The main project cost is a primary input, not re-asked here
        "calculation_logic": lambda: "Handled by Final Dashboard's Order of Operations"
    },
    {
        "id": "itc_macrs",
        "name": "ITC & MACRS Depreciation",
        "level": "Federal", "type": "Tax Credit/Benefit",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Commercial / Business", "Farm / Agriculture"]}
        ],
        "calculation_inputs": [], # Handled by the master 'Order of Operations' logic
        "calculation_logic": lambda: "Handled by Final Dashboard's Order of Operations"
    },

    # ==============================================================================
    # 2. OTHER FEDERAL GRANT & LOAN PROGRAMS
    # ==============================================================================
    {
        "id": "vapg",
        "name": "Value Added Producer Grant (VAPG)",
        "level": "Federal", "type": "Matching Grant",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture", "Rural Cooperative"]}
        ],
        "calculation_inputs": [
            {"id": "vapg_project_cost", "label": "VAPG-Eligible Project Cost ($)", "type": "number_input"},
            # Match is 50%, so it's a fixed part of the formula.
        ],
        "calculation_logic": lambda vapg_project_cost: vapg_project_cost * 0.50 # Grant = Project Cost × 50%
    },
    {
        "id": "eqip",
        "name": "Environmental Quality Incentives Program (EQIP)",
        "level": "Federal", "type": "Incentive Payment",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]}
        ],
        "calculation_inputs": [
            {"id": "eqip_unit_practice_cost", "label": "Unit Practice Cost ($)", "type": "number_input"},
            {"id": "eqip_units_or_acres", "label": "Number of Units or Acres", "type": "number_input"},
            {"id": "eqip_payment_rate_percent", "label": "Payment Rate % (up to 90)", "type": "slider", "min": 0, "max": 90, "value": 75}
        ],
        "calculation_logic": lambda eqip_unit_practice_cost, eqip_units_or_acres, eqip_payment_rate_percent: \
            eqip_unit_practice_cost * eqip_units_or_acres * (eqip_payment_rate_percent / 100.0) # Incentive = (Unit Cost × Units) × Payment Rate %
    },
    {
        "id": "fsa_loan",
        "name": "FSA Loan Program",
        "level": "Federal", "type": "Loan",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]}
        ],
        "calculation_inputs": [
            {"id": "fsa_total_project_cost", "label": "Total Project Cost for FSA Loan ($)", "type": "number_input"},
            {"id": "fsa_applicant_contribution", "label": "Applicant Contribution ($)", "type": "number_input"},
            {"id": "fsa_ineligible_costs", "label": "Ineligible Costs ($)", "type": "number_input", "value": 0} # Default to 0
        ],
        "calculation_logic": lambda fsa_total_project_cost, fsa_applicant_contribution, fsa_ineligible_costs: \
            fsa_total_project_cost - fsa_applicant_contribution - fsa_ineligible_costs # Loan = Total Cost - Contribution - Ineligible
    },
    {
        "id": "tip",
        "name": "Transition Incentives Program (TIP)",
        "level": "Federal", "type": "Incentive Payment",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]} # For landowners transitioning land
        ],
        "calculation_inputs": [
            {"id": "tip_crp_rental_rate", "label": "CRP Rental Rate ($/acre)", "type": "number_input"},
            {"id": "tip_num_acres", "label": "Number of Acres", "type": "number_input"}
        ],
        "calculation_logic": lambda tip_crp_rental_rate, tip_num_acres: \
            tip_crp_rental_rate * tip_num_acres * 2 # Incentive = CRP Rate × Acres × 2
    },
    {
        "id": "usda_csp_nap_tap_ecp",
        "name": "USDA CSP/NAP/TAP/ECP",
        "level": "Federal", "type": "Payment",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]}
        ],
        "calculation_inputs": [
            # This is a complex one. We'll simplify for the UI. A user would likely know their specific program.
            # We will model the most common case: Payment = Score * Acres * Rate
            {"id": "usda_score", "label": "Conservation Score / Loss %", "type": "number_input"},
            {"id": "usda_acres", "label": "Number of Acres / Damage Value", "type": "number_input"},
            {"id": "usda_rate", "label": "Payment Rate ($)", "type": "number_input"}
        ],
        "calculation_logic": lambda usda_score, usda_acres, usda_rate: \
            usda_score * usda_acres * usda_rate # Payment = Score × Acres × Rate or Loss % × Damage
    },

    # ==============================================================================
    # 3. STATE & LOCAL PROGRAMS
    # ==============================================================================
    {
        "id": "ca_cusp",
        "name": "California Underserved and Small Producers (CUSP)",
        "level": "State", "state": "CA", "type": "Grant (Time & Materials)",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture", "Small Business"]},
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "cusp_hours_ta", "label": "Hours of Technical Assistance", "type": "number_input"},
            {"id": "cusp_hourly_rate", "label": "Hourly Rate ($)", "type": "number_input"}
        ],
        "calculation_logic": lambda cusp_hours_ta, cusp_hourly_rate: \
            cusp_hours_ta * cusp_hourly_rate # Incentive = Hours × Rate
    },
    {
        "id": "ca_hsp",
        "name": "Healthy Soils Program (HSP)",
        "level": "State", "state": "CA", "type": "Cost-share",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]},
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "hsp_cost_per_acre", "label": "HSP Cost per Acre ($)", "type": "number_input"},
            {"id": "hsp_num_acres", "label": "Number of Acres", "type": "number_input"},
            {"id": "hsp_cost_share_percent", "label": "Cost Share % (up to 75)", "type": "slider", "min": 0, "max": 75, "value": 75}
        ],
        "calculation_logic": lambda hsp_cost_per_acre, hsp_num_acres, hsp_cost_share_percent: \
            hsp_cost_per_acre * hsp_num_acres * (hsp_cost_share_percent / 100.0) # Incentive = (Cost per Acre × Acres) × Cost Share %
    },
    {
        "id": "ca_ammp",
        "name": "Alternative Manure Management Program (AMMP)",
        "level": "State", "state": "CA", "type": "Cost-share",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]}, # Livestock operations
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "ammp_equipment_cost", "label": "AMMP Equipment Cost ($)", "type": "number_input"},
            {"id": "ammp_installation_cost", "label": "AMMP Installation Cost ($)", "type": "number_input"},
            {"id": "ammp_cost_share_percent", "label": "Cost Share % (50-75)", "type": "slider", "min": 50, "max": 75, "value": 75}
        ],
        "calculation_logic": lambda ammp_equipment_cost, ammp_installation_cost, ammp_cost_share_percent: \
            (ammp_equipment_cost + ammp_installation_cost) * (ammp_cost_share_percent / 100.0) # Incentive = Equipment Cost × Cost Share %
    },
    {
        "id": "ca_sweep",
        "name": "State Water Efficiency and Enhancement Program (SWEEP)",
        "level": "State", "state": "CA", "type": "Reimbursement",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]},
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "sweep_equipment_cost", "label": "SWEEP Equipment Cost ($)", "type": "number_input"},
            {"id": "sweep_labor_cost", "label": "SWEEP Labor Cost ($)", "type": "number_input"},
            {"id": "sweep_reimbursement_percent", "label": "Reimbursement % (50-80)", "type": "slider", "min": 50, "max": 80, "value": 75}
        ],
        "calculation_logic": lambda sweep_equipment_cost, sweep_labor_cost, sweep_reimbursement_percent: \
            (sweep_equipment_cost + sweep_labor_cost) * (sweep_reimbursement_percent / 100.0) # Incentive = Total Cost × Reimbursement %
    },
    {
        "id": "ca_hrgp",
        "name": "Healthy Refrigeration Grant Program",
        "level": "State", "state": "CA", "type": "Reimbursement",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Small Business"]}, # Small food retailers
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "hrgp_equipment_cost", "label": "Refrigeration Equipment Cost ($)", "type": "number_input"},
            {"id": "hrgp_installation_cost", "label": "Installation Cost ($)", "type": "number_input"},
            {"id": "hrgp_reimbursement_percent", "label": "Reimbursement % (~75)", "type": "slider", "min": 0, "max": 100, "value": 75}
        ],
        "calculation_logic": lambda hrgp_equipment_cost, hrgp_installation_cost, hrgp_reimbursement_percent: \
            (hrgp_equipment_cost + hrgp_installation_cost) * (hrgp_reimbursement_percent / 100.0)
    },
    {
        "id": "ca_uagp",
        "name": "Urban Agriculture Grant Program",
        "level": "State", "state": "CA", "type": "Grant",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Nonprofit", "Farm / Agriculture"]}, # Urban farms, community orgs
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "uagp_proposed_budget", "label": "Proposed Budget for UAGP ($)", "type": "number_input", "value": 50000}
        ],
        "calculation_logic": lambda uagp_proposed_budget: min(uagp_proposed_budget, 100000) # Incentive = Proposed Budget (Cap $100K)
    },
    {
        "id": "local_irrigation_upgrade",
        "name": "County Irrigation Upgrade",
        "level": "Local", "type": "Incentive",
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Farm / Agriculture"]}
        ],
        "calculation_inputs": [
            {"id": "irr_upgrade_cost", "label": "Irrigation Upgrade Cost ($)", "type": "number_input"},
            {"id": "irr_reimbursement_rate", "label": "County Reimbursement Rate %", "type": "slider", "min": 0, "max": 100, "value": 50}
        ],
        "calculation_logic": lambda irr_upgrade_cost, irr_reimbursement_rate: \
            irr_upgrade_cost * (irr_reimbursement_rate / 100.0)
    },
    {
        "id": "local_community_block_grant",
        "name": "Community-Based Block Grant",
        "level": "Local", "type": "Grant",
        "eligibility_rules": [], # Assume broad eligibility for demo
        "calculation_inputs": [
            {"id": "cbbg_submitted_budget", "label": "Submitted Budget for Grant ($)", "type": "number_input"}
        ],
        "calculation_logic": lambda cbbg_submitted_budget: cbbg_submitted_budget # Grant = Submitted Budget
    }
]