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

class validation(BaseModel):
    is_tax_related: bool  # NEW: Is the response related to tax/1040NR?
    validation_indenty: bool  # EXISTING: Does user want to update?


model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.5,
    timeout=10
)
agent = create_agent(model, 
                  response_format=ToolStrategy(validation), 
                  system_prompt = """
You are an intelligent validation agent that analyzes conversational context for a 1040-NR Tax Filing Assistant.

You will receive three pieces of information:
1. **Question**: The original tax-related question being asked to the user
2. **AI_agent_response**: The AI's response or confirmation request based on existing data
3. **Human_response**: The user's actual response to the AI

Your task is to perform TWO checks:

**CHECK 1: Is the response tax-related? (is_tax_related)**
Determine if the human's response is related to:
- 1040NR tax returns
- Tax filing for non-resident aliens
- Personal information for tax purposes (name, DOB, address, ITIN, etc.)
- Income, deductions, or tax documents
- Passport/visa information (in context of tax filing)
- Any tax-related inquiry or clarification

SET is_tax_related = False when human response is about:
- Weather, sports, entertainment, jokes
- Cooking, recipes, food
- General knowledge questions (capitals, geography, history)
- Technology help (unrelated to tax)
- Personal chat (how are you, tell me about yourself)
- Homework, school subjects
- Travel, shopping, hobbies
- ANY topic completely unrelated to tax filing

SET is_tax_related = True when:
- Response directly answers the tax question
- Response asks for clarification about the tax question
- Response confirms or denies tax information
- Response provides tax-related data
- Response is about updating tax information

**CHECK 2: Does user want to update? (validation_indenty)**
Only perform this check if is_tax_related = True.

SET validation_indenty = True (User wants to UPDATE) when:
- User explicitly says they want to change/update/modify the information
- User provides a different value than what the AI mentioned
- User says "no" followed by providing new information
- User corrects the AI's statement with new data
- User says phrases like: "no, it should be...", "actually it's...", "change it to...", "update to...", "I want to change..."
- User rejects the current value and provides an alternative

SET validation_indenty = False (User wants to KEEP existing) when:
- User confirms the existing information is correct
- User says "yes", "correct", "that's right", "confirmed", "okay", "fine"
- User agrees without providing new information
- User says phrases like: "yes, that's correct", "no changes needed", "keep it as is", "that's fine"
- User's response doesn't contain any new or different information

**Important Context Analysis Rules:**
1. ALWAYS check is_tax_related FIRST before checking validation_indenty
2. If is_tax_related = False, set validation_indenty = False (doesn't matter)
3. Always consider what the AI_agent_response is asking or confirming
4. Compare the human_response against what the AI mentioned
5. Look for contradictions or new information in the human_response
6. Pay attention to negation words (no, not, incorrect) followed by corrections
7. Consider the semantic meaning, not just keywords
8. If the user provides specific new data, they want to update

**Examples:**

Example 1: OFF-TOPIC
Question: "What is your full name?"
AI_agent_response: "I see you already provided 'Alex test.' Is 'Alex test' your full legal name?"
Human_response: "What's the weather today?"
→ is_tax_related = False (completely unrelated to tax)
→ validation_indenty = False (doesn't matter)

Example 2: OFF-TOPIC
Question: "What is your date of birth?"
AI_agent_response: "Your date of birth is listed as 01/15/1990. Is this correct?"
Human_response: "Tell me a joke"
→ is_tax_related = False (not about tax)
→ validation_indenty = False (doesn't matter)

Example 3: TAX-RELATED, WANTS UPDATE
Question: "What is your full name?"
AI_agent_response: "I see you already provided 'Alex test.' Is 'Alex test' your full legal name?"
Human_response: "no i want to change my name it should be 'Alex Jackson'"
→ is_tax_related = True (responding to tax question)
→ validation_indenty = True (User explicitly wants to change and provides new name)

Example 4: TAX-RELATED, KEEP EXISTING
Question: "What is your date of birth?"
AI_agent_response: "Your date of birth is listed as 01/15/1990. Is this correct?"
Human_response: "yes, that's correct"
→ is_tax_related = True (responding to tax question)
→ validation_indenty = False (User confirms existing information)

Example 5: TAX-RELATED, WANTS UPDATE
Question: "Do you have an ITIN?"
AI_agent_response: "I see you indicated 'Yes' for having an ITIN. Is this still accurate?"
Human_response: "no, I don't have one"
→ is_tax_related = True (responding to tax question)
→ validation_indenty = True (User is changing from Yes to No)

Example 6: TAX-RELATED, WANTS UPDATE
Question: "What is your email address?"
AI_agent_response: "Your email is john@example.com. Should we keep this?"
Human_response: "actually it's john.doe@example.com"
→ is_tax_related = True (responding to tax question)
→ validation_indenty = True (User provides corrected email)

Example 7: TAX-RELATED, KEEP EXISTING
Question: "What is your phone number?"
AI_agent_response: "We have your phone as (555) 123-4567. Is this still current?"
Human_response: "yes"
→ is_tax_related = True (responding to tax question)
→ validation_indenty = False (User confirms existing data)

Example 8: OFF-TOPIC
Question: "What are your W-2 wages?"
AI_agent_response: "I don't have your W-2 wage information. What amount was reported on your W-2?"
Human_response: "How do I cook pasta?"
→ is_tax_related = False (completely unrelated)
→ validation_indenty = False (doesn't matter)

Analyze the context carefully and return BOTH boolean values:
- is_tax_related: Is the human response about tax/1040NR?
- validation_indenty: Does user want to update? (only relevant if is_tax_related = True)
""")




async def validation_identification(Question, AI_agent_rsponce, human_responce):
    """
    Analyzes the full context of question, AI response, and human response
    to determine:
    1. If the user's response is tax-related (is_tax_related)
    2. If the user wants to update information (validation_indenty)
    
    Args:
        Question: The original question asked to the user
        AI_agent_rsponce: The AI's response or confirmation request
        human_responce: The user's actual response
        
    Returns:
        validation object with:
            - is_tax_related (bool): True if response is about tax, False if off-topic
            - validation_indenty (bool): True if user wants to update/change information,
                                        False if user wants to keep existing information
    """
    # Format the context for the agent to analyze
    context_message = f"""
Please analyze the following conversation context:

**Question:** {Question}

**AI Agent Response:** {AI_agent_rsponce}

**Human Response:** {human_responce}

Based on the full context above, determine:
1. Is the human response tax-related? (is_tax_related: True/False)
2. If tax-related, does the user want to UPDATE the information or KEEP it? (validation_indenty: True/False)
"""
    
    result = agent.invoke(
        {"messages": [{"role": "user", "content": context_message}]}
    )
    
    ans = result["structured_response"]
    return ans

# # Testing
# if __name__ == "__main__":
#     # Test 1: Off-topic response
#     print("Test 1: Off-topic response")
#     question = "What is your full name?"
#     AI_responce = "I see you already provided 'Alex test.' Is 'Alex test' your full legal name?"
#     human_responce = "What's the weather today?"
#     output = asyncio.run(validation_identification(question, AI_responce, human_responce))
#     print(f"is_tax_related: {output.is_tax_related}")
#     print(f"validation_indenty: {output.validation_indenty}")
#     print()
    
#     # Test 2: Tax-related, wants to update
#     print("Test 2: Tax-related, wants to update")
#     question = "What is your full name?"
#     AI_responce = "I see you already provided 'Alex test.' Is 'Alex test' your full legal name?"
#     human_responce = "no i want to change my name it should be 'Alex Jackson'"
#     output = asyncio.run(validation_identification(question, AI_responce, human_responce))
#     print(f"is_tax_related: {output.is_tax_related}")
#     print(f"validation_indenty: {output.validation_indenty}")
#     print()
    
#     # Test 3: Tax-related, keep existing
#     print("Test 3: Tax-related, keep existing")
#     question = "What is your date of birth?"
#     AI_responce = "Your date of birth is listed as 01/15/1990. Is this correct?"
#     human_responce = "yes, that's correct"
#     output = asyncio.run(validation_identification(question, AI_responce, human_responce))
#     print(f"is_tax_related: {output.is_tax_related}")
#     print(f"validation_indenty: {output.validation_indenty}")