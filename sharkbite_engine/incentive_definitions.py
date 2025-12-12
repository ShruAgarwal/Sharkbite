# Structured definitions for the full suite of grants
INCENTIVE_PROGRAMS = [
    # ==========================================================================================
    # 1. CORE FEDERAL PROGRAMS (Already part of the main flow, defined here for consistency)
    # ==========================================================================================
    {
        "id": "usda_reap_grant",
        "name": "USDA REAP Grant",
        "level": "Federal", "type": "Grant",
        "eligibility_rules": [
            # This special rule calls a dedicated function in our utils.py
            # The function itself will check both business type and location.
            {"function": "is_reap_eligible", "expected_result": True}
        ],
        "calculation_inputs": [], # The main project cost is a primary input, not re-asked here
        "calculation_logic": lambda: "Handled by Final Dashboard's Order of Operations",
        "range_tooltip": "The USDA Rural Energy for America Program (REAP) provides grants to support renewable energy systems and improve energy efficiency for small businesses and agricultural producers in rural areas. Grant can cover up to 50% of project costs.",
        "formula_text": "min(50% * Project Cost, Tech Cap) - Federal Share Adjustment"
    },
    {
        "id": "itc_macrs",
        "name": "ITC & MACRS Depreciation",
        "level": "Federal", "type": "Tax Credit/Benefit",

        # The ITC itself is available to almost everyone who owns a system.
        # MACRS is the part that is limited to businesses/farms, but we handle that
        # in the final calculation, not in the initial eligibility check.
        "eligibility_rules": [
            # The only real rule is that a system must exist.
            {"field": "calculator_refined_system_size_kw", "condition": "is_greater_than", "value": 0}
        ],
        "calculation_inputs": [], # Handled by the master 'Order of Operations' logic
        "calculation_logic": lambda: "Handled by Final Dashboard's Order of Operations",
        "range_tooltip": "ITC is 30% of project cost, with potential bonuses. MACRS is for businesses.",
        "formula_text": "(30% + Bonuses) * Project Cost + Detailed Depreciation Benefit"
    },

    # =======================================================
    # 2. OTHER FEDERAL GRANT & LOAN PROGRAMS
    # =======================================================
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
        "calculation_logic": lambda vapg_project_cost: vapg_project_cost * 0.50, # Grant = Project Cost × 50%

        "range_tooltip": "Matching grant for 50% of eligible costs.",
        "formula_text": "VAPG-Eligible Project Cost * 50%"
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
            eqip_unit_practice_cost * eqip_units_or_acres * (eqip_payment_rate_percent / 100.0), # Incentive = (Unit Cost × Units) × Payment Rate %
        
        "range_tooltip": "Payment Rate can be up to 90% for underserved producers.",
        "formula_text": "(Unit Cost * Units) * Payment Rate %"
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
            fsa_total_project_cost - fsa_applicant_contribution - fsa_ineligible_costs, # Loan = Total Cost - Contribution - Ineligible
        
        "range_tooltip": "Loan amount is based on project need after contributions.",
        "formula_text": "Total Project Cost - Applicant Contribution - Ineligible Costs"
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
            tip_crp_rental_rate * tip_num_acres * 2, # Incentive = CRP Rate × Acres × 2
        
        "range_tooltip": "Payment is for two years of the CRP rental rate.",
        "formula_text": "CRP Rate * Acres * 2"
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
            usda_score * usda_acres * usda_rate, # Payment = Score × Acres × Rate or Loss % × Damage

        "range_tooltip": "Payment based on conservation score, acreage, and rate.",
        "formula_text": "Score * Acres * Rate or (Loss % * Damage)"
    },

    # =====================================
    # 3. STATE & LOCAL PROGRAMS
    # =====================================
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
            cusp_hours_ta * cusp_hourly_rate, # Incentive = Hours × Rate
        
        "range_tooltip": "Grant based on hours of technical assistance.",
        "formula_text": "Hours of Assistance * Hourly Rate"
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
            hsp_cost_per_acre * hsp_num_acres * (hsp_cost_share_percent / 100.0), # Incentive = (Cost per Acre × Acres) × Cost Share %

        "range_tooltip": "Cost-share is typically around 75%.",
        "formula_text": "(Cost per Acre * Acres) * Cost Share %"
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
            (ammp_equipment_cost + ammp_installation_cost) * (ammp_cost_share_percent / 100.0), # Incentive = Equipment Cost × Cost Share %
        
        "range_tooltip": "Cost-share is typically between 50-75%.",
        "formula_text": "(Equipment + Installation Cost) * Cost Share %"
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
            (sweep_equipment_cost + sweep_labor_cost) * (sweep_reimbursement_percent / 100.0), # Incentive = Total Cost × Reimbursement %
        
        "range_tooltip": "Reimbursement is typically between 50-80%.",
        "formula_text": "(Equipment Cost + Labor Cost) * Reimbursement %"
    },
    {
        "id": "ca_hrgp",
        "name": "Healthy Refrigeration Grant Program",
        "level": "State", "state": "CA", "type": "Reimbursement",

        # This program funds energy-efficient refrigeration units in corner stores, small businesses, &
        # food donation programs in low-income areas to stock California-grown fresh produce,
        # nuts, dairy, meat, eggs, minimally processed, and culturally appropriate foods.
        "eligibility_rules": [
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Small Business"]},
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            {"id": "hrgp_equipment_cost", "label": "Refrigeration Equipment Cost ($)", "type": "number_input"},
            {"id": "hrgp_installation_cost", "label": "Installation Cost ($)", "type": "number_input"},
            {"id": "hrgp_reimbursement_percent", "label": "Reimbursement % (~75)", "type": "slider", "min": 0, "max": 100, "value": 75}
        ],
        "calculation_logic": lambda hrgp_equipment_cost, hrgp_installation_cost, hrgp_reimbursement_percent: \
            (hrgp_equipment_cost + hrgp_installation_cost) * (hrgp_reimbursement_percent / 100.0),
        
        "range_tooltip": "Reimbursement is typically around 75%.",
        "formula_text": "(Equipment + Installation Cost) * Reimbursement %"
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
        "calculation_logic": lambda uagp_proposed_budget: min(uagp_proposed_budget, 100000), # Incentive = Proposed Budget (Cap $100K)
        
        "range_tooltip": "Grant amount is based on scope of your proposed budget, up to a $100k cap.",
        "formula_text": "min(Proposed Budget, $100,000)"
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
            irr_upgrade_cost * (irr_reimbursement_rate / 100.0),
        
        "range_tooltip": "Varies by county, but can reimburse up to 50% or more of upgrade costs.",
        "formula_text": "Irrigation Upgrade Cost * County Reimbursement Rate %"
    },
    {
        "id": "local_community_block_grant",
        "name": "Community-Based Block Grant",
        "level": "Local", "type": "Grant",
        "eligibility_rules": [], # Assume broad eligibility for demo
        "calculation_inputs": [
            {"id": "cbbg_submitted_budget", "label": "Submitted Budget for Grant ($)", "type": "number_input"}
        ],
        "calculation_logic": lambda cbbg_submitted_budget: cbbg_submitted_budget, # Grant = Submitted Budget
        
        "range_tooltip": "Grant amount is typically based on the submitted budget, subject to approval.",
        "formula_text": "Grant Value = Submitted Budget Cost"
    },

    # ================================================================================================
    # 4. California CORE (Clean Off-Road Equipment Voucher) Incentive Program For Off-Road Vehicles
    # Agency -- California Air Resources Board (CARB) & CALSTART
    # ================================================================================================
    {
        "id": "ca_core",
        "name": "California CORE (Clean Off-Road Equipment) Voucher Program",
        "level": "State", "state": "CA", "type": "Point-of-Sale Voucher",
        "eligibility_rules": [
            # Applicant Type: Small business or public agency (FY 2024-25 eligibility)
            # Assuming these map to SB/public agency
            {"field": "unified_business_type", "condition": "is_one_of", "value": ["Commercial / Business", "Farm / Agriculture", "Small Business"]},
            # Project Location: Must be in California
            {"field": "location_state_mock", "condition": "is_equal_to", "value": "CA"}
        ],
        "calculation_inputs": [
            # Input for Equipment Type to determine Base Voucher
            {
                "id": "core_equipment_type", "label": "CORE-Eligible Equipment Type", "type": "selectbox",
                "options": [
                    "Truck and Trailer-mounted TRUs",
                    "Airport Cargo Loaders",
                    "Wide-body Aircraft Tugs",
                    "Mobile Power Units / Ground Power Units",
                    "Construction & Agricultural Equipment",
                    "Large Forklifts / Freight / Harbor Craft"
                ],
                "data_type": "string"  # Specify the expected data type
            },
            # Inputs for Enhancements
            {
                "id": "core_is_disadvantaged_community", "label": "Is equipment deployed in a disadvantaged/low-income community?",
                "type": "toggle", "value": False,
                "data_type": "boolean"
            },
            {
                "id": "core_is_small_business", "label": "Is your organization a certified small business?",
                "type": "toggle", "value": True, # Default to true since it's a primary user type
                "data_type": "boolean" 
            }
        ],
        "calculation_logic": lambda core_equipment_type, core_is_disadvantaged_community, core_is_small_business: \
            (
                {
                    "Truck and Trailer-mounted TRUs": 65000,
                    "Airport Cargo Loaders": 100000,
                    "Wide-body Aircraft Tugs": 200000,
                    "Mobile Power Units / Ground Power Units": 300000,
                    "Construction & Agricultural Equipment": 500000,
                    "Large Forklifts / Freight / Harbor Craft": 1000000
                }.get(core_equipment_type, 0)
            ) * (
                1 +
                (0.10 if core_is_disadvantaged_community else 0) +
                (0.15 if core_is_small_business else 0)
            ),
        
        "range_tooltip": "Base voucher up to $1M, with bonuses up to 25%.",
        "formula_text": "Base Voucher * (1 + Bonus %)"
    }
]