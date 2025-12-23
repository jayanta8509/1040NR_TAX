from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import sys
import time
import redis
import json
from datetime import datetime, timedelta
from typing import Dict, Any

HOST= os.environ["HOST"] = os.getenv("HOST")
PORT= os.environ["PORT"] = os.getenv("PORT")
PASSWORD = os.environ["PASSWORD"] = os.getenv("PASSWORD")

# Redis Cloud connection for memory storage
redis_client = redis.Redis(
    host=HOST,
    port=PORT,
    decode_responses=True,
    username="default",
    password=PASSWORD,
)

# Test Redis connection
try:
    redis_client.ping()
    print("✅ Redis Cloud connected successfully")
except redis.ConnectionError as e:
    print(f"❌ Redis Cloud connection failed: {e}")
    print("⚠️  Falling back to memory-only mode")



def store_conversation_memory(user_id: str, messages: list, client_id: int = None, reference: str = None, metadata: dict = None):
    """Store conversation in Redis with 12-hour TTL including client_id and reference"""
    try:
        memory_data = {
            "messages": messages,
            "client_id": client_id,  # Store client_id
            "reference": reference,  # Store reference (company or individual)
            "metadata": metadata or {},
            "last_updated": datetime.utcnow().isoformat(),
            "user_id": user_id
        }

        # Store with 12-hour expiration (43200 seconds)
        redis_client.setex(
            f"conversation:{user_id}",
            43200,  # 12 hours in seconds
            json.dumps(memory_data)
        )
        print(f"💾 Stored conversation for user {user_id} with client_id={client_id}, reference={reference}")
    except Exception as e:
        print(f"❌ Error storing conversation: {e}")

def get_conversation_memory(user_id: str) -> dict:
    """Retrieve conversation from Redis"""
    try:
        data = redis_client.get(f"conversation:{user_id}")
        if data:
            return json.loads(data)
        return {"messages": [], "metadata": {}}
    except Exception as e:
        print(f"❌ Error retrieving conversation: {e}")
        return {"messages": [], "metadata": {}}


def clear_conversation_memory(user_id: str):
    """Clear conversation memory for a specific user"""
    try:
        redis_client.delete(f"conversation:{user_id}")
        print(f"🧹 Cleared conversation memory for user: {user_id}")
    except Exception as e:
        print(f"❌ Error clearing conversation: {e}")


def get_conversation_summary(user_id: str) -> str:
    """Get a summary of the conversation for continuity"""
    return f"Conversation thread: {user_id} - Tax Filing Assistant (1040NR)"


# Global MCP client and agent (singleton pattern to avoid TaskGroup errors)
_mcp_client = None
_agent = None
_client_lock = asyncio.Lock()


async def get_or_create_agent():
    """Get or create the global MCP client and agent (singleton pattern)"""
    global _mcp_client, _agent
    
    async with _client_lock:
        if _agent is None:
            print("🔧 Initializing MCP client and agent...")
            
            try:
                # Use the current Python interpreter (from virtual environment)
                python_executable = sys.executable
                print(f"📍 Using Python: {python_executable}")
                
                # Create MCP client
                _mcp_client = MultiServerMCPClient(
                    {
                        "Data_Fetch": {
                            "command": python_executable,  # Use full path to Python
                            "args": ["mcp_functions.py"],
                            "transport": "stdio",
                        }
                    },
                    {
                        "Data_Updater":{
                            "command": python_executable,  # Use full path to Python
                            "args": ["mcp_update_functions.py"],
                            "transport": "stdio",
                        }
                    }
                )
                
                os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
                
                # Get tools and create agent
                print("📡 Connecting to MCP server...")
                tools = await _mcp_client.get_tools()
                print(f"✅ Got {len(tools)} tools from MCP server")
                
                model = ChatOpenAI(model="gpt-4o-mini")
                _agent = create_agent(model, tools)
                
                print("✅ MCP client and agent initialized successfully")
            except Exception as e:
                print(f"❌ Error initializing MCP client: {e}")
                print(f"❌ Error type: {type(e).__name__}")
                import traceback
                print(f"❌ Full traceback:\n{traceback.format_exc()}")
                raise
        
        return _agent




async def process_question(agent, user_question, user_id="default_user", client_id=None, reference=None):
    """Send any user question to the agent with Redis memory and IDs"""
    print(f"\n🔍 Question: {user_question}")
    print(f"👤 User ID: {user_id}, Client ID: {client_id}, Reference: {reference}")
    print("🔄 Processing...")

    # Get existing conversation from Redis
    memory_data = get_conversation_memory(user_id)
    
    # Update or set client_id and reference in memory
    if client_id:
        memory_data['client_id'] = client_id
    if reference:
        memory_data['reference'] = reference

    # Build message history with new question
    messages = memory_data.get("messages", [])
    messages.append({"role": "user", "content": user_question})

    # Add IDs to the context for the agent
    system_context = f"""
    SESSION INFORMATION:
    - User ID: {user_id}
    - Client ID: {client_id}
    - Reference Type: {reference} (company or individual)
    
    IMPORTANT: When calling any MCP tools, you MUST pass these two parameters:
    - client_id: {client_id}
    - reference: {reference}
    """

    # Add conversation context to messages for the agent
    if len(messages) > 1:
        context_messages = messages[-6:]  # Keep last 6 messages for context
        full_messages = [
            {"role": "system", "content": system_context},
            *context_messages
        ]
    else:
        full_messages = [
            {"role": "system", "content": system_context},
            {"role": "user", "content": user_question}
        ]




# Redis Cloud connection for memory storage
redis_client = redis.Redis(
    host=HOST,
    port=PORT,
    decode_responses=True,
    username="default",
    password=PASSWORD,
)

# Test Redis connection
try:
    redis_client.ping()
    print("✅ Redis Cloud connected successfully")
except redis.ConnectionError as e:
    print(f"❌ Redis Cloud connection failed: {e}")
    print("⚠️  Falling back to memory-only mode")



def store_conversation_memory(user_id: str, messages: list, client_id: int = None, reference: str = None, metadata: dict = None):
    """Store conversation in Redis with 12-hour TTL including client_id and reference"""
    try:
        memory_data = {
            "messages": messages,
            "client_id": client_id,  # Store client_id
            "reference": reference,  # Store reference (company or individual)
            "metadata": metadata or {},
            "last_updated": datetime.utcnow().isoformat(),
            "user_id": user_id
        }

        # Store with 12-hour expiration (43200 seconds)
        redis_client.setex(
            f"conversation:{user_id}",
            43200,  # 12 hours in seconds
            json.dumps(memory_data)
        )
        print(f"💾 Stored conversation for user {user_id} with client_id={client_id}, reference={reference}")
    except Exception as e:
        print(f"❌ Error storing conversation: {e}")

def get_conversation_memory(user_id: str) -> dict:
    """Retrieve conversation from Redis"""
    try:
        data = redis_client.get(f"conversation:{user_id}")
        if data:
            return json.loads(data)
        return {"messages": [], "metadata": {}}
    except Exception as e:
        print(f"❌ Error retrieving conversation: {e}")
        return {"messages": [], "metadata": {}}


def clear_conversation_memory(user_id: str):
    """Clear conversation memory for a specific user"""
    try:
        redis_client.delete(f"conversation:{user_id}")
        print(f"🧹 Cleared conversation memory for user: {user_id}")
    except Exception as e:
        print(f"❌ Error clearing conversation: {e}")


def get_conversation_summary(user_id: str) -> str:
    """Get a summary of the conversation for continuity"""
    return f"Conversation thread: {user_id} - Tax Filing Assistant (1040NR)"


# Global MCP client and agent (singleton pattern to avoid TaskGroup errors)
_mcp_client = None
_agent = None
_client_lock = asyncio.Lock()


async def get_or_create_agent():
    """Get or create the global MCP client and agent (singleton pattern)"""
    global _mcp_client, _agent
    
    async with _client_lock:
        if _agent is None:
            print("🔧 Initializing MCP client and agent...")
            
            try:
                # Use the current Python interpreter (from virtual environment)
                python_executable = sys.executable
                print(f"📍 Using Python: {python_executable}")
                
                # Create MCP client
                _mcp_client = MultiServerMCPClient(
                    {
                        "Data_Fetch": {
                            "command": python_executable,  # Use full path to Python
                            "args": ["mcp_functions.py"],
                            "transport": "stdio",
                        },
                        "Data_Updater":{
                            "command": python_executable,  # Use full path to Python
                            "args": ["mcp_update_functions.py"],
                            "transport": "stdio",
                        }
                    }
                )
                
                os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
                
                # Get tools and create agent
                print("📡 Connecting to MCP server...")
                tools = await _mcp_client.get_tools()
                print(f"✅ Got {len(tools)} tools from MCP server")
                
                model = ChatOpenAI(model="gpt-5-mini")
                _agent = create_agent(model, tools)
                
                print("✅ MCP client and agent initialized successfully")
            except Exception as e:
                print(f"❌ Error initializing MCP client: {e}")
                print(f"❌ Error type: {type(e).__name__}")
                import traceback
                print(f"❌ Full traceback:\n{traceback.format_exc()}")
                raise
        
        return _agent




async def process_question(agent, user_question, user_id="default_user", client_id=None, reference=None):
    """Send any user question to the agent with Redis memory and IDs"""
    print(f"\n🔍 Question: {user_question}")
    print(f"👤 User ID: {user_id}, Client ID: {client_id}, Reference: {reference}")
    print("🔄 Processing...")

    # Get existing conversation from Redis
    memory_data = get_conversation_memory(user_id)
    
    # Update or set client_id and reference in memory
    if client_id:
        memory_data['client_id'] = client_id
    if reference:
        memory_data['reference'] = reference

    # Build message history with new question
    messages = memory_data.get("messages", [])
    messages.append({"role": "user", "content": user_question})

    # Add IDs to the context for the agent
    system_context = f"""
    SESSION INFORMATION:
    - User ID: {user_id}
    - Client ID: {client_id}
    - Reference Type: {reference} (company or individual)
    
    IMPORTANT: When calling any MCP tools, you MUST pass these two parameters:
    - client_id: {client_id}
    - reference: {reference}
    """

    # Add conversation context to messages for the agent
    if len(messages) > 1:
        context_messages = messages[-6:]  # Keep last 6 messages for context
        full_messages = [
            {"role": "system", "content": system_context},
            *context_messages
        ]
    else:
        full_messages = [
            {"role": "system", "content": system_context},
            {"role": "user", "content": user_question}
        ]

    # Get response from agent
    response = await agent.ainvoke({"messages": full_messages})

    # Extract and store response
    response_content = response['messages'][-1].content
    messages.append({"role": "assistant", "content": response_content})

    # Save updated conversation to Redis with 12-hour TTL including IDs
    store_conversation_memory(user_id, messages, client_id=client_id, reference=reference)

    return response_content


def get_workflow_state(user_id: str) -> dict:
    """Get the current workflow state for a user"""
    try:
        memory_data = get_conversation_memory(user_id)
        metadata = memory_data.get('metadata', {})
        workflow_state = metadata.get('workflow_state', {
            'current_task': 1,
            'current_subtask': 1,
            'completed_tasks': [],
            'completed_subtasks': [],
            'current_question_id': None
        })
        return workflow_state
    except Exception as e:
        print(f"Error getting workflow state: {e}")
        return {
            'current_task': 1,
            'current_subtask': 1,
            'completed_tasks': [],
            'completed_subtasks': [],
            'current_question_id': None
        }

def update_workflow_state(user_id: str, task: int = None, subtask: int = None,
                         question_id: str = None, completed_task: int = None,
                         completed_subtask: int = None):
    """Update the workflow state"""
    try:
        memory_data = get_conversation_memory(user_id)
        metadata = memory_data.get('metadata', {})
        workflow_state = metadata.get('workflow_state', {
            'current_task': 1,
            'current_subtask': 1,
            'completed_tasks': [],
            'completed_subtasks': [],
            'current_question_id': None
        })

        if task is not None:
            workflow_state['current_task'] = task
        if subtask is not None:
            workflow_state['current_subtask'] = subtask
        if question_id is not None:
            workflow_state['current_question_id'] = question_id
        if completed_task is not None and completed_task not in workflow_state['completed_tasks']:
            workflow_state['completed_tasks'].append(completed_task)
        if completed_subtask is not None and completed_subtask not in workflow_state['completed_subtasks']:
            workflow_state['completed_subtasks'].append(completed_subtask)

        metadata['workflow_state'] = workflow_state
        # Update the conversation memory with new metadata
        messages = memory_data.get("messages", [])
        client_id = memory_data.get('client_id')
        reference = memory_data.get('reference')
        store_conversation_memory(user_id, messages, client_id=client_id, reference=reference, metadata=metadata)

    except Exception as e:
        print(f"Error updating workflow state: {e}")


async def ask_question(question, style_preference=None, user_id="default_user", client_id=None, reference=None):
    """Function to directly ask a question with client_id and reference"""
    
    # Get recent conversation context
    recent_context = await get_recent_context(user_id)

    # Get workflow state
    workflow_state = get_workflow_state(user_id)

    # Get stored client_id and reference from memory if not provided
    memory_data = get_conversation_memory(user_id)
    if not client_id:
        client_id = memory_data.get('client_id', None)
    if not reference:
        reference = memory_data.get('reference', 'individual')

    # Include session context in the question
    contextual_question = f"""
    You are a friendly and professional Tax Filing Assistant helping with 1040NR tax returns for non-resident aliens.

    **Your Goal:**
    Answer the user's question by checking their stored information first, then providing a clear, direct response.

    **SESSION INFO:**
    - Client ID: {client_id}
    - Reference: {reference}

    {recent_context}

    **HOW TO RESPOND:**

    1. **Check First**: Use MCP tools to retrieve existing information before responding
    
    2. **Be Direct and Conversational**:
       - If information exists: "I see you already provided [X]. Is this still correct?"
       - If information is missing: "I don't have [X] on file. Please provide [specific request]."
       - If user wants to update: Use the update MCP tools to save the new information
    
    3. **Keep It Simple**:
       - NO task/subtask numbers (don't say "Task 1 — Subtask 1")
       - NO workflow position mentions
       - Just answer the question naturally
       - One question at a time

    **AVAILABLE MCP TOOLS:**

    📋 **Get Information:**
    - get_client_basic_profile(client_id, reference) → name, email, ITIN, filing status
    - get_client_primary_contact(client_id, reference) → address, phone, email
    - get_individual_identity_and_tax_id(client_id, reference) → name, DOB, ITIN, citizenship
    - get_individual_residency_and_citizenship(client_id, reference) → country of residence/citizenship
    - get_client_services_overview(client_id, reference) → occupation, income source

    💾 **Update Information (when user wants to change):**
    - update_individual_identity_and_tax_id() → update name, DOB, ITIN, filing status
    - update_client_primary_contact_info() → update address, contact details
    - update_client_occupation_and_income_source() → update occupation

    **RESPONSE EXAMPLES:**

    ❌ **DON'T SAY:**
    "Task 1 — Subtask 1 (Personal Information)
    
    I checked your stored profile and couldn't find a filing status on file..."

    ✅ **DO SAY:**
    "I checked your profile and see you haven't provided a filing status yet. What is your filing status for this tax year? (Single, Married filing jointly, Married filing separately, Head of household, or Qualifying widow(er))"

    ❌ **DON'T SAY:**
    "Task 1 — Subtask 1 (Personal Information)
    
    I do not have a record of your country of citizenship. I need to collect your country of citizenship to proceed. What is your country of citizenship?"

    ✅ **DO SAY:**
    "I don't have your country of citizenship on file. What is your country of citizenship?"

    **WHEN USER WANTS TO UPDATE:**
    If the user says "no, it should be..." or provides a correction:
    1. Use the appropriate update MCP tool
    2. Confirm: "Got it! I've updated [field] to [new value]. Is this correct?"

    **CRITICAL RULES:**
    ❌ NEVER mention task numbers, subtask numbers, or workflow positions
    ❌ NEVER ask for information that's already stored (check MCP tools first)
    ❌ NEVER share Client ID or Reference in your responses
    ✅ ALWAYS check existing data before asking
    ✅ ALWAYS be conversational and friendly
    ✅ ALWAYS use update tools when user wants to change information
    ❌ NEVER skip to add-on services before completing Task 1
    ✅ ALWAYS retrieve context before asking any question
    ✅ ALWAYS reference previous year's data when suggesting add-ons
    ✅ ALWAYS explain WHY you need each document
    ✅ ALWAYS track your position in the workflow

    **User's Question:** {question}

    Please use the appropriate MCP tools with the client_id and reference provided above.
    """

    # Get or create the global agent (singleton pattern)
    agent = await get_or_create_agent()
    
    # Process the question
    return await process_question(agent, contextual_question, user_id, client_id, reference)


async def get_recent_context(user_id: str) -> str:
    """Get recent conversation context for better follow-up handling using Redis"""
    try:
        # Get conversation from Redis
        memory_data = get_conversation_memory(user_id)
        messages = memory_data.get("messages", [])

        if messages:
            # Extract recent tax document and form discussions
            recent_forms = []
            recent_topics = []
            import re
            
            for msg in messages[-4:]:  # Look at last 4 messages
                if isinstance(msg, dict) and 'content' in msg:
                    content = msg['content']
                    
                    # Look for tax form names (FORM 1042-S, 1098, W-7, Schedule C, etc.)
                    form_patterns = re.findall(r'(?:FORM\s+)?(?:1042-S|1098|W-?7|Schedule\s+[A-Z]|1040NR|8843)', content, re.IGNORECASE)
                    recent_forms.extend(form_patterns)
                    
                    # Look for ITIN mentions
                    if re.search(r'ITIN|Individual Taxpayer Identification Number', content, re.IGNORECASE):
                        recent_topics.append("ITIN")
                    
                    # Look for tax year mentions
                    tax_years = re.findall(r'20\d{2}', content)
                    if tax_years:
                        recent_topics.append(f"Tax Year {tax_years[-1]}")

            context_parts = []
            if recent_forms:
                context_parts.append(f"Recently discussed forms: {', '.join(set(recent_forms))}")
            if recent_topics:
                context_parts.append(f"Topics: {', '.join(set(recent_topics))}")
            
            if context_parts:
                return f"RECENT CONTEXT: {'. '.join(context_parts)}. Use this context when the client refers to 'that form' or 'the document we discussed'."

        return ""

    except Exception as e:
        print(f"Error getting context: {e}")
        return ""


if __name__ == "__main__":
    answer = asyncio.run(ask_question(
                question="Confirm your full legal name (first, middle, last) as it appears on your passport or official documents.", 
                user_id="jayana34y5",
                client_id="TESTDEM1",  
                reference="individual"
            ))

    print(answer)