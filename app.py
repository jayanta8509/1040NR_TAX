from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import time
import os
from typing import Optional
from process import TaxProcessingWorkflow
# Import the function from mcp_functions
from welcome_message import get_client_welcome_message
from sub_client import get_individual_associated_clients

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Tax Filing Assistant API",
    description="AI-powered Tax Filing Assistant for 1040NR returns with intelligent validation",
    version="2.0.0"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaxWorkflowRequest(BaseModel):
    user_id: str
    client_id: str
    reference: str = "individual"  # "company" or "individual"
    human_response: Optional[str] = None  # None for first call, user's answer for subsequent calls


class WelcomeMessageRequest(BaseModel):
    user_id: str
    client_id: str  # str primary key
    reference: str  # "company" or "individual"

class subclient(BaseModel):
    sub_client_id: str  # str primary key
    reference: str  # "company" or "individual"

@app.post("/tax/workflow")
async def tax_workflow_endpoint(request: TaxWorkflowRequest):
    """
    Single unified endpoint for the entire tax filing workflow.
    
    **First Call (Start Workflow):**
    - Set human_response = None or omit it
    - Generates questions and saves to questions_{user_id}.json
    - Returns first question via ask_question
    
    **Subsequent Calls (Process Answers):**
    - Set human_response = user's answer
    - Validates the answer using validation_identification
    - If off-topic: Returns standard message and repeats question
    - If validation = True (wants update): Asks human_response as question
    - If validation = False (confirmed): Moves to next question
    - Returns next question or completion status
    
    Example First Call:
    {
        "user_id": "user123",
        "client_id": "TESTDEM1",
        "reference": "individual"
    }
    
    Example Subsequent Call:
    {
        "user_id": "user123",
        "client_id": "TESTDEM1",
        "reference": "individual",
        "human_response": "yes, that's correct"
    }
    """
    try:
        # Validation
        if not request.user_id or request.user_id.strip() == "":
            raise HTTPException(status_code=400, detail="User ID cannot be empty")
        
        if not request.client_id:
            raise HTTPException(status_code=400, detail="Client ID cannot be empty")
        
        if request.reference.lower() not in ["company", "individual"]:
            raise HTTPException(status_code=400, detail="Reference must be 'company' or 'individual'")

        # Create workflow instance
        workflow = TaxProcessingWorkflow(
            user_id=request.user_id,
            client_id=request.client_id,
            reference=request.reference.lower()
        )

        # Check if user is starting the workflow
        if request.human_response and request.human_response.strip().lower() == "start":
            # User said "start" - Initialize workflow, generate questions, ask first question
            logger.info(f"Starting workflow for user {request.user_id}")
            result = await workflow.start_workflow()
            logger.info(f"Successfully started workflow for user {request.user_id}")
        else:
            # User provided an answer - Process it with validation
            logger.info(f"Processing answer from user {request.user_id}: {request.human_response}")
            result = await workflow.process_next_question(request.human_response)
            logger.info(f"Successfully processed answer for user {request.user_id}")

        # Check if workflow is completed
        if result.get("status") == "completed":
            return {
                "status": "completed",
                "message": result.get("message"),
                "total_questions": result.get("total_questions"),
                "completed_questions": result.get("completed_questions"),
                "final_response": result.get("final_response"),  # AI's final acknowledgment
                "timestamp": time.time()
            }
        
        # Return current question (handles both in_progress and off_topic)
        # For off_topic, the message is in result.get("message") and needs to go in ai_response
        ai_response = result.get("message") if result.get("status") == "off_topic" else result.get("ai_response")
        
        return {
            "status": result.get("status"),
            "question_number": result.get("question_number"),
            "total_questions": result.get("total_questions"),
            "question": result.get("question"),
            "ai_response": ai_response,
            "completed": result.get("completed", 0),
            "validation_result": result.get("validation_result"),  # True = wants update, False = confirmed, None = first question
            "timestamp": time.time()
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in tax workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in tax workflow: {str(e)}")


@app.post("/welcome/message")
async def get_welcome_message_endpoint(request: WelcomeMessageRequest):
    """
    Get the welcome message for a client
    """
    try:
        logger.info(f"Received welcome message request for user {request.user_id}, client_id {request.client_id}")

        if not request.user_id or request.user_id.strip() == "":
            raise HTTPException(status_code=400, detail="User ID cannot be empty")

        if not request.client_id:
            raise HTTPException(status_code=400, detail="Client ID cannot be empty")

        if not request.reference or request.reference.strip() == "":
            raise HTTPException(status_code=400, detail="Reference cannot be empty")

        if request.reference.lower() not in ["company", "individual"]:
            raise HTTPException(status_code=400, detail="Reference must be 'company' or 'individual'")

        # Get the welcome message
        welcome_message = get_client_welcome_message(
            client_id=request.client_id,
            reference=request.reference.lower()
        )

        logger.info(f"Successfully processed welcome message for user {request.user_id}")
        return {
            "response": welcome_message,
            "status_code": 200,
            "timestamp": time.time(),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing welcome message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing welcome message: {str(e)}")

@app.post("/sub/client")
async def get_sub_client_endpoint(request: subclient):
    """
    Get the sub-client details
    """
    try:
        logger.info(f"Received sub-client request for {request.sub_client_id}, reference {request.reference}")

        if not request.sub_client_id:
            raise HTTPException(status_code=400, detail="Sub Client ID cannot be empty")

        if not request.reference or request.reference.strip() == "":
            raise HTTPException(status_code=400, detail="Reference cannot be empty")

        if request.reference.lower() not in ["company", "individual"]:
            raise HTTPException(status_code=400, detail="Reference must be 'company' or 'individual'")

        # Get the sub-client details
        subclient_details = get_individual_associated_clients(
            practice_id=request.sub_client_id,
            reference=request.reference.lower()
        )

        logger.info(f"Successfully processed sub-client for {request.sub_client_id}")
        return {
            "response": subclient_details,
            "status_code": 200,
            "timestamp": time.time(),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing sub-client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing sub-client: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Tax Filing Assistant API",
        "version": "2.0.0",
        "endpoint": "POST /tax/workflow",
        "description": "Single endpoint for complete tax filing workflow with intelligent validation and off-topic detection"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )