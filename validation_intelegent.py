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
    validation_indenty: bool


model = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.5,
    timeout=20
)
agent = create_agent(model, 
                  response_format=ToolStrategy(validation), 
                  system_prompt = """
You are an intelligent validation agent that analyzes conversational context to determine if a user wants to update information.

You will receive three pieces of information:
1. **Question**: The original question being asked to the user
2. **AI_agent_response**: The AI's response or confirmation request based on existing data
3. **Human_response**: The user's actual response to the AI

Your task is to analyze all three pieces of information together to understand the FULL CONTEXT and determine:
- Does the user want to UPDATE/CHANGE the existing information? (validation_indenty = True)
- Does the user want to KEEP the existing information as is? (validation_indenty = False)

**Guidelines for determining user intent:**

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
1. Always consider what the AI_agent_response is asking or confirming
2. Compare the human_response against what the AI mentioned
3. Look for contradictions or new information in the human_response
4. Pay attention to negation words (no, not, incorrect) followed by corrections
5. Consider the semantic meaning, not just keywords
6. If the user provides specific new data, they want to update

**Examples:**

Example 1:
Question: "What is your full name?"
AI_agent_response: "I see you already provided 'Alex test.' Is 'Alex test' your full legal name?"
Human_response: "no i want to change my name it should be 'Alex Jackson'"
→ validation_indenty = True (User explicitly wants to change and provides new name)

Example 2:
Question: "What is your date of birth?"
AI_agent_response: "Your date of birth is listed as 01/15/1990. Is this correct?"
Human_response: "yes, that's correct"
→ validation_indenty = False (User confirms existing information)

Example 3:
Question: "Do you have an ITIN?"
AI_agent_response: "I see you indicated 'Yes' for having an ITIN. Is this still accurate?"
Human_response: "no, I don't have one"
→ validation_indenty = True (User is changing from Yes to No)

Example 4:
Question: "What is your email address?"
AI_agent_response: "Your email is john@example.com. Should we keep this?"
Human_response: "actually it's john.doe@example.com"
→ validation_indenty = True (User provides corrected email)

Example 5:
Question: "What is your phone number?"
AI_agent_response: "We have your phone as (555) 123-4567. Is this still current?"
Human_response: "yes"
→ validation_indenty = False (User confirms existing data)

Analyze the context carefully and return your determination as a boolean value for validation_indenty.
""")




async def validation_identification(Question, AI_agent_rsponce, human_responce):
    """
    Analyzes the full context of question, AI response, and human response
    to determine if the user wants to update information.
    
    Args:
        Question: The original question asked to the user
        AI_agent_rsponce: The AI's response or confirmation request
        human_responce: The user's actual response
        
    Returns:
        validation object with validation_indenty (bool):
            True if user wants to update/change information
            False if user wants to keep existing information
    """
    # Format the context for the agent to analyze
    context_message = f"""
Please analyze the following conversation context:

**Question:** {Question}

**AI Agent Response:** {AI_agent_rsponce}

**Human Response:** {human_responce}

Based on the full context above, determine if the user wants to UPDATE the information (True) or KEEP it as is (False).
"""
    
    result = agent.invoke(
        {"messages": [{"role": "user", "content": context_message}]}
    )
    
    ans = result["structured_response"]
    return ans

if __name__ == "__main__":
    question = "Confirm your full legal name (first, middle, last) as it appears on your passport or official documents."
    AI_responce = "I see you already provided \"Alex test.\" Let me confirm: Is \"Alex test\" your full legal name (first, middle, last) as it appears on your passport or other official documents?"
    human_responce = "yes it is correct"
    output = asyncio.run(validation_identification(question, AI_responce, human_responce))
    print(output.validation_indenty)