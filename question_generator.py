import os
import asyncio
import json
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langchain.agents.structured_output import ToolStrategy
from dotenv import load_dotenv

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

class taxQuestion(BaseModel):
    tax_question: str

class Question(BaseModel):
    all_question: list[taxQuestion]

# OPTIMIZATION 1: Use faster model with optimized parameters
model = ChatOpenAI(
    model="gpt-4o-mini",  # Much faster than gpt-5-mini
    temperature=0.3,      # Lower temperature for faster, more deterministic output
    max_tokens=2000,      # Set explicit limit to prevent over-generation
    timeout=30,           # Add timeout to prevent hanging
    streaming=False,      # Disable streaming for batch processing
    request_timeout=30    # Request-level timeout
)

# OPTIMIZATION 2: System prompt based on actual MCP functions
SIMPLIFIED_PROMPT = """Generate consolidated tax questions for 1040NR filing based on available MCP functions.

**AVAILABLE MCP FUNCTIONS (17 GET functions):**

1. **get_client_full_legal_name** → first_name, middle_name, last_name (or company name)
2. **get_client_date_of_birth** → birth_date
3. **get_client_current_us_address** → address1, address2, city, state, zip, country
4. **get_client_occupation_and_us_income_source** → occupation, source_of_us_income
5. **get_client_itin_number** → itin
6. **get_individual_passport_details** → passport_number, passport_country, passport_expiry
7. **get_individual_visa_details** → visa_type, visa_issue_country
8. **get_individual_us_entry_exit_dates** → first_entry_date_us, last_exit_date_us
9. **get_individual_days_in_us** → days_in_us_current_year, days_in_us_prev_year, days_in_us_prev2_years
10. **get_individual_treaty_claim_details** → treaty_claimed, treaty_country, treaty_article, treaty_income_type, treaty_exempt_amount, resident_of_treaty_country
11. **get_individual_income_amounts** → w2_wages_amount, scholarship_1042s_amount, interest_amount, dividend_amount, capital_gains_amount, rental_income_amount, self_employment_eci_amount
12. **get_individual_withholding_amounts** → federal_withholding_w2, federal_withholding_1042s, tax_withheld_1099
13. **get_individual_document_flags** → has_w2, has_1042s, has_1099, has_k1
14. **get_individual_itemized_deductions** → itemized_state_local_tax, itemized_charity, itemized_casualty_losses
15. **get_individual_education_items** → education_expenses, student_loan_interest
16. **get_individual_dependents_count** → dependents_count
17. **get_individual_refund_method** → refund_method
18. **get_individual_bank_details_last4** → bank_routing, bank_account_last4

**CONSOLIDATION RULES:**
- Combine related fields from the SAME MCP function into ONE question
- Each MCP function should generate 1-2 questions maximum
- Use natural language that groups related data points
- Avoid asking separately for fields that are fetched together

**QUESTION GENERATION PATTERN:**

For each MCP function:
- If function returns 1-2 fields → 1 question
- If function returns 3-6 fields → 1-2 questions (group logically)
- If function returns 7+ fields → 2-3 questions (group by category)

**EXAMPLES:**

✅ GOOD (Consolidated):
- "What is your full legal name?" (covers first_name, middle_name, last_name)
- "What is your passport number, issuing country, and expiration date?" (covers all passport fields)
- "What are your W-2 wages, scholarship/fellowship (1042-S), and interest income amounts?" (groups income types)

❌ BAD (Repetitive):
- "What is your first name?"
- "What is your middle name?"
- "What is your last name?"

**GENERATE 18-25 CONSOLIDATED QUESTIONS covering all MCP functions listed above.**"""

agent = create_agent(
    model, 
    response_format=ToolStrategy(Question), 
    system_prompt=SIMPLIFIED_PROMPT
)

async def generate_questions():
    """
    Generates all necessary questions for IRS Form 1040NR based on MCP functions.
    Optimized for ~20 second execution time.
    
    Returns:
        dict: Dictionary containing a list of tax questions
    """
    # OPTIMIZATION 3: Shorter, more direct prompt
    prompt = "Generate 18-25 consolidated 1040NR questions based on the 18 MCP functions. One question per function, combining related fields."
    
    # OPTIMIZATION 4: Use asyncio with timeout
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                agent.invoke,
                {"messages": [{"role": "user", "content": prompt}]}
            ),
            timeout=25  # 25 second timeout
        )
        
        questions_list = [q.tax_question for q in result["structured_response"].all_question]
        return {"question": questions_list}
    
    except asyncio.TimeoutError:
        print("⚠️ Request timed out. Using fallback questions.")
        return generate_fallback_questions()

def generate_fallback_questions():
    """Fallback questions based on actual MCP functions - consolidated and non-repetitive"""
    return {"question": [
        # 1. get_client_full_legal_name
        "What is your full legal name? (First, Middle, Last)",
        
        # 2. get_client_date_of_birth
        "What is your date of birth? (MM/DD/YYYY)",
        
        # 3. get_client_current_us_address
        "What is your complete current US address? (Street, Apt/Unit, City, State, ZIP, Country)",
        
        # 4. get_client_occupation_and_us_income_source
        "What is your current occupation and source of US income?",
        
        # 5. get_client_itin_number
        "Do you have an ITIN? If yes, what is it?",
        
        # 6. get_individual_passport_details
        "What is your passport number, issuing country, and expiration date?",
        
        # 7. get_individual_visa_details
        "What is your visa type and which country issued it?",
        
        # 8. get_individual_us_entry_exit_dates
        "What was your first entry date to the US and your last exit date? (MM/DD/YYYY for both)",
        
        # 9. get_individual_days_in_us
        "How many days were you physically present in the US during the current tax year, previous year, and two years ago?",
        
        # 10. get_individual_treaty_claim_details (split into 2 questions for clarity)
        "Are you claiming tax treaty benefits? If yes, which country and treaty article?",
        "If claiming treaty benefits, what type of income is covered, what is the exempt amount, and are you a resident of the treaty country?",
        
        # 11. get_individual_income_amounts (split into 2 questions)
        "What were your W-2 wages and scholarship/fellowship amounts from Form 1042-S?",
        "What were your other income amounts: interest, dividends, capital gains, rental income, and self-employment income (ECI)?",
        
        # 12. get_individual_withholding_amounts
        "How much federal tax was withheld from your W-2, 1042-S, and 1099 forms?",
        
        # 13. get_individual_document_flags
        "Which of the following tax forms do you have: W-2, 1042-S, 1099, or K-1?",
        
        # 14. get_individual_itemized_deductions
        "What are your itemized deduction amounts for state/local taxes, charitable contributions, and casualty losses?",
        
        # 15. get_individual_education_items
        "What are your education-related expenses and student loan interest amounts?",
        
        # 16. get_individual_dependents_count
        "How many dependents do you have?",
        
        # 17. get_individual_refund_method
        "What is your preferred refund method: check or ACH (direct deposit)?",
        
        # 18. get_individual_bank_details_last4
        "If choosing direct deposit, what is your bank routing number and the last 4 digits of your account number?"
    ]}

# OPTIMIZATION 5: Add caching capability
_cached_questions = None

async def generate_questions_cached():
    """Generate questions with caching for repeated calls"""
    global _cached_questions
    if _cached_questions is None:
        _cached_questions = await generate_questions()
    return _cached_questions

# if __name__ == "__main__":
#     import time
    
#     start = time.time()
#     output = asyncio.run(generate_questions())
#     elapsed = time.time() - start
    
#     print(f"✅ Generated {len(output['question'])} questions in {elapsed:.2f} seconds")
#     print(json.dumps(output, indent=2))