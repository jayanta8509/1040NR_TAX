# Comprehensive MCP Function Reference for Client.py

## All Available MCP Functions

### GET Functions (17 total)

**Basic Profile (5 functions):**
1. `get_client_full_legal_name(practice_id, reference)` → full_legal_name
2. `get_client_date_of_birth(practice_id, reference)` → date_of_birth
3. `get_client_current_us_address(practice_id, reference)` → address1, address2, city, state, zip, country
4. `get_client_occupation_and_us_income_source(practice_id, reference)` → occupation, source_of_us_income
5. `get_client_itin_number(practice_id, reference)` → itin

**Passport & Visa (2 functions):**
6. `get_individual_passport_details(practice_id, reference)` → passport_number, passport_country, passport_expiry
7. `get_individual_visa_details(practice_id, reference)` → visa_type, visa_issue_country

**US Presence (2 functions):**
8. `get_individual_us_entry_exit_dates(practice_id, reference)` → first_entry_date_us, last_exit_date_us
9. `get_individual_days_in_us(practice_id, reference)` → days_in_us_current_year, days_in_us_prev_year, days_in_us_prev2_years

**Treaty Claims (1 function):**
10. `get_individual_treaty_claim_details(practice_id, reference)` → treaty_claimed, treaty_country, treaty_article, treaty_income_type, treaty_exempt_amount, resident_of_treaty_country

**Income (1 function):**
11. `get_individual_income_amounts(practice_id, reference)` → w2_wages_amount, scholarship_1042s_amount, interest_amount, dividend_amount, capital_gains_amount, rental_income_amount, self_employment_eci_amount

**Withholding (1 function):**
12. `get_individual_withholding_amounts(practice_id, reference)` → federal_withholding_w2, federal_withholding_1042s, tax_withheld_1099

**Documents (1 function):**
13. `get_individual_document_flags(practice_id, reference)` → has_w2, has_1042s, has_1099, has_k1

**Deductions (1 function):**
14. `get_individual_itemized_deductions(practice_id, reference)` → itemized_state_local_tax, itemized_charity, itemized_casualty_losses

### UPDATE Functions (11 total)

1. `update_individual_identity_and_tax_id()` → first_name, middle_name, last_name, birth_date, ssn_itin_type, ssn_itin, language_id, country_residence_id, country_citizenship_id, filing_status
2. `update_client_primary_contact_info()` → address1, address2, city, state, zip_code, country_id, phone1, phone2, email1, email2
3. `update_client_occupation_and_income_source()` → occupation, source_of_us_income
4. `update_individual_passport_and_visa()` → passport_number, passport_country, passport_expiry, visa_type, visa_issue_country
5. `update_individual_us_presence()` → first_entry_date_us, last_exit_date_us, days_in_us_current_year, days_in_us_prev_year, days_in_us_prev2_years
6. `update_individual_treaty_details()` → treaty_claimed, treaty_country, treaty_article, treaty_income_type, treaty_exempt_amount, resident_of_treaty_country
7. `update_individual_income_amounts()` → w2_wages_amount, scholarship_1042s_amount, interest_amount, dividend_amount, capital_gains_amount, rental_income_amount, self_employment_eci_amount
8. `update_individual_withholding()` → federal_withholding_w2, federal_withholding_1042s, tax_withheld_1099
9. `update_individual_forms_flags()` → has_w2, has_1042s, has_1099, has_k1
10. `update_individual_deductions_and_education()` → itemized_state_local_tax, itemized_charity, itemized_casualty_losses, education_expenses, student_loan_interest, dependents_count
11. `get_master_languages_and_countries()` → languages[], countries[] (for lookups)

## Automatic Function Selection Logic

**Question contains** → **Use Function**
- "name" → `get_client_full_legal_name`
- "birth" or "DOB" or "date of birth" → `get_client_date_of_birth`
- "address" or "street" or "city" or "state" or "zip" → `get_client_current_us_address`
- "occupation" or "profession" → `get_client_occupation_and_us_income_source`
- "income source" → `get_client_occupation_and_us_income_source`
- "ITIN" → `get_client_itin_number`
- "passport" → `get_individual_passport_details`
- "visa" → `get_individual_visa_details`
- "entry" or "exit" or "US travel" → `get_individual_us_entry_exit_dates`
- "days in US" → `get_individual_days_in_us`
- "treaty" → `get_individual_treaty_claim_details`
- "W-2" or "wages" or "income amount" → `get_individual_income_amounts`
- "withholding" → `get_individual_withholding_amounts`
- "W-2 form" or "1042-S form" → `get_individual_document_flags`
- "deduction" or "charity" → `get_individual_itemized_deductions`
