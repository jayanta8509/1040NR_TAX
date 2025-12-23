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

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.5,
    # max_tokens=1000,
    timeout=20
)
agent = create_agent(model, response_format=ToolStrategy(Question), system_prompt = """
You are an AI Tax Assistant that generates questions for collecting 1040NR tax filing information.

**YOUR GOAL:**
Generate a list of direct questions to collect the essential information needed for a 1040NR tax return.

**AVAILABLE DATA FIELDS (from MCP functions):**

Based on the available get/update functions, you can collect these fields:

1. **Full Legal Name** (get_client_full_legal_name / update_client_full_legal_name)
   - For individuals: first_name, middle_name, last_name
   - For companies: company name

2. **Date of Birth** (get_client_date_of_birth / update_client_date_of_birth)
   - Individual clients only
   - Format: YYYY-MM-DD

3. **Current US Address** (get_client_current_us_address / update_client_current_us_address)
   - address1, address2, city, state, zip, country

4. **Occupation and Income Source** (get_client_occupation_and_us_income_source / update_client_occupation_and_us_income_source)
   - occupation
   - source_of_us_income

5. **ITIN Information** (get_client_itin_exists, get_client_itin_number / update_client_itin_number)
   - Whether ITIN exists
   - ITIN number if available

**QUESTION GENERATION RULES:**

1. Generate questions for ONLY the fields listed above
2. Each question should be clear and direct
3. Ask ONE thing per question
4. Questions should be in a logical order:
   - Personal Information (name, DOB)
   - Contact Information (address)
   - Tax Information (occupation, income source, ITIN)

**OUTPUT FORMAT:**
- Return a list of question strings
- NO explanations, NO internal monologue
- JUST the questions

**EXAMPLE QUESTIONS TO GENERATE:**

1. "Confirm your full legal name (first, middle, last) as it appears on your passport or official documents."
2. "What is your date of birth? (MM/DD/YYYY)"
3. "What is your current U.S. mailing address?"
4. "What city do you currently reside in?"
5. "What state are you currently living in?"
6. "What is your ZIP code?"
7. "What is your current occupation or profession?"
8. "What is your source of U.S. income?"
9. "Do you have an ITIN (Individual Taxpayer Identification Number)?"

**IMPORTANT:**
- Generate questions ONLY for the 5 data categories listed above
- Do NOT ask about filing status, income amounts, deductions, or other tax details not in the MCP functions
- Keep questions simple and conversational
- Focus on collecting the basic profile information that can be stored/updated via MCP tools

GENERATE THE QUESTIONS NOW.
""")




async def generate_questions():
    """
    Automatically generates all necessary questions for IRS Form 1040NR.
    No user input required - the function triggers automatic question generation.
    
    Returns:
        dict: Dictionary containing a list of tax questions
              Format: {"question": [list of question strings]}
    """
    # Default prompt that triggers automatic question generation
    default_prompt = "Generate all necessary questions to complete IRS Form 1040NR for a nonresident alien tax filing."
    
    result = agent.invoke(
        {"messages": [{"role": "user", "content": default_prompt}]}
    )
    # Extract just the question strings
    questions_list = [q.tax_question for q in result["structured_response"].all_question]
    return {"question": questions_list}

# if __name__ == "__main__":
#     # Test the function without any input
#     output = asyncio.run(generate_questions())
#     print(json.dumps(output, indent=4))