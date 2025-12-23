import os
import json
import asyncio
from datetime import datetime
from question_generator import generate_questions
from client import ask_question
from validation_intelegent import validation_identification


class TaxProcessingWorkflow:
    """
    Manages the tax filing workflow:
    1. Generate questions and save to JSON
    2. Process questions step-by-step
    3. Validate user responses
    4. Track progress per user
    """
    
    def __init__(self, user_id: str, client_id: str = None, reference: str = "individual"):
        self.user_id = user_id
        self.client_id = client_id
        self.reference = reference
        self.questions_file = f"questions_{user_id}.json"
        self.progress_file = f"progress_{user_id}.json"
        
    async def initialize_questions(self):
        """
        Generate all questions and save to JSON file.
        Only generates if file doesn't exist.
        """
        if not os.path.exists(self.questions_file):
            print(f"📝 Generating questions for user {self.user_id}...")
            questions_data = await generate_questions()
            
            # Structure the questions with metadata
            structured_questions = {
                "user_id": self.user_id,
                "generated_at": datetime.now().isoformat(),
                "questions": questions_data.get("question", []),
                "total_questions": len(questions_data.get("question", []))
            }
            
            # Save to JSON file
            with open(self.questions_file, 'w', encoding='utf-8') as f:
                json.dump(structured_questions, f, indent=4, ensure_ascii=False)
            
            print(f"✅ Generated {structured_questions['total_questions']} questions")
            print(f"💾 Saved to {self.questions_file}")
            
            return structured_questions
        else:
            print(f"📂 Loading existing questions from {self.questions_file}")
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def load_progress(self):
        """Load user's progress from JSON file"""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "user_id": self.user_id,
                "current_question_index": 0,
                "completed_questions": [],
                "answers": {},
                "last_updated": datetime.now().isoformat()
            }
    
    def save_progress(self, progress_data):
        """Save user's progress to JSON file"""
        progress_data["last_updated"] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=4, ensure_ascii=False)
        print(f"💾 Progress saved to {self.progress_file}")
    
    async def process_next_question(self, human_response: str):
        """
        Process the next question in the workflow.
        
        Args:
            human_response: The user's response to the current question
            
        Returns:
            dict: Contains the AI's next question or completion status
        """
        # Load questions and progress
        questions_data = await self.initialize_questions()
        progress = self.load_progress()
        
        questions = questions_data.get("questions", [])
        current_index = progress.get("current_question_index", 0)
        
        validation_wants_update = None
        
        # Check if we have a current question to validate
        if current_index > 0 and current_index <= len(questions):
            # Get the previous question and AI response
            prev_question = questions[current_index - 1]
            prev_ai_response = progress.get("last_ai_response", "")
            
            # Check if this is the last question
            is_last_question = (current_index == len(questions))
            
            if is_last_question:
                # For the last question, just process the answer without validation
                print(f"📝 Processing final answer for last question...")
                
                # Save the answer
                if "answers" not in progress:
                    progress["answers"] = {}
                
                progress["answers"][f"question_{current_index - 1}"] = {
                    "question": prev_question,
                    "ai_response": prev_ai_response,
                    "human_response": human_response,
                    "wants_update": False,  # No validation for last question
                    "timestamp": datetime.now().isoformat()
                }
                
                # Mark as completed
                if current_index - 1 not in progress["completed_questions"]:
                    progress["completed_questions"].append(current_index - 1)
                
                # Ask the AI to acknowledge the final answer
                ai_response = await ask_question(
                    question=human_response,
                    user_id=self.user_id,
                    client_id=self.client_id,
                    reference=self.reference
                )
                
                # Save and mark as completed
                progress["last_ai_response"] = ai_response
                self.save_progress(progress)
                
                return {
                    "status": "completed",
                    "message": "🎉 All questions have been completed!",
                    "total_questions": len(questions),
                    "completed_questions": len(progress["completed_questions"]),
                    "final_response": ai_response  # Include AI's final acknowledgment
                }
            else:
                # Not the last question - validate normally
                print(f"🔍 Validating user response...")
                validation_result = await validation_identification(
                    Question=prev_question,
                    AI_agent_rsponce=prev_ai_response,
                    human_responce=human_response
                )
                
                wants_to_update = validation_result.validation_indenty
                validation_wants_update = wants_to_update
                print(f"📊 Validation result: {'UPDATE' if wants_to_update else 'KEEP'}")
                
                # Save the answer
                if "answers" not in progress:
                    progress["answers"] = {}
                
                progress["answers"][f"question_{current_index - 1}"] = {
                    "question": prev_question,
                    "ai_response": prev_ai_response,
                    "human_response": human_response,
                    "wants_update": wants_to_update,
                    "timestamp": datetime.now().isoformat()
                }
                
                if wants_to_update:
                    # User wants to update, ask the human_response as a question
                    print(f"🔄 User wants to update information, asking human response as question")
                    
                    ai_response = await ask_question(
                        question=human_response,  # Ask the human response as the question
                        user_id=self.user_id,
                        client_id=self.client_id,
                        reference=self.reference
                    )
                    
                    # Save the AI response but don't increment question index
                    progress["last_ai_response"] = ai_response
                    self.save_progress(progress)
                    
                    return {
                        "status": "in_progress",
                        "question_number": current_index,  # Same question number
                        "total_questions": len(questions),
                        "question": human_response,  # The human response becomes the question
                        "ai_response": ai_response,
                        "completed": len(progress["completed_questions"]),
                        "validation_result": True  # User wants to update
                    }
                else:
                    # User confirmed, mark as completed and move to next
                    if current_index - 1 not in progress["completed_questions"]:
                        progress["completed_questions"].append(current_index - 1)
                    # Move to next question
                    current_index = progress.get("current_question_index", 0)
        
        # Check if all questions are completed (shouldn't reach here after last question)
        if current_index >= len(questions):
            self.save_progress(progress)
            return {
                "status": "completed",
                "message": "🎉 All questions have been completed!",
                "total_questions": len(questions),
                "completed_questions": len(progress["completed_questions"])
            }
        
        # Get the next question
        current_question = questions[current_index]
        print(f"\n📋 Question {current_index + 1}/{len(questions)}: {current_question}")
        
        # Ask the AI agent to process this question
        ai_response = await ask_question(
            question=current_question,
            user_id=self.user_id,
            client_id=self.client_id,
            reference=self.reference
        )
        
        # Save the AI response for next validation
        progress["last_ai_response"] = ai_response
        progress["current_question_index"] = current_index + 1
        self.save_progress(progress)
        
        return {
            "status": "in_progress",
            "question_number": current_index + 1,
            "total_questions": len(questions),
            "question": current_question,
            "ai_response": ai_response,
            "completed": len(progress["completed_questions"]),
            "validation_result": validation_wants_update  # None for first question, True/False after
        }
    
    async def start_workflow(self):
        """
        Start the workflow from the beginning or resume from saved progress.
        
        Returns:
            dict: The first question or current question based on progress
        """
        # Initialize questions
        questions_data = await self.initialize_questions()
        progress = self.load_progress()
        
        questions = questions_data.get("questions", [])
        current_index = progress.get("current_question_index", 0)
        
        if current_index >= len(questions):
            return {
                "status": "completed",
                "message": "🎉 All questions have been completed!",
                "total_questions": len(questions),
                "completed_questions": len(progress["completed_questions"])
            }
        
        # Get the current question
        current_question = questions[current_index]
        print(f"\n📋 Question {current_index + 1}/{len(questions)}: {current_question}")
        
        # Ask the AI agent
        ai_response = await ask_question(
            question=current_question,
            user_id=self.user_id,
            client_id=self.client_id,
            reference=self.reference
        )
        
        # Save progress
        progress["last_ai_response"] = ai_response
        progress["current_question_index"] = current_index + 1
        self.save_progress(progress)
        
        return {
            "status": "started",
            "question_number": current_index + 1,
            "total_questions": len(questions),
            "question": current_question,
            "ai_response": ai_response,
            "completed": len(progress["completed_questions"])
        }
    
    def get_progress_summary(self):
        """Get a summary of the current progress"""
        progress = self.load_progress()
        
        return {
            "user_id": self.user_id,
            "current_question": progress.get("current_question_index", 0),
            "completed_questions": len(progress.get("completed_questions", [])),
            "total_answers": len(progress.get("answers", {})),
            "last_updated": progress.get("last_updated", "Never")
        }


# Convenience functions for easy usage
async def start_tax_workflow(user_id: str, client_id: str = None, reference: str = "individual"):
    """
    Start a new tax workflow for a user.
    
    Args:
        user_id: Unique identifier for the user
        client_id: Client ID for database queries
        reference: "individual" or "company"
        
    Returns:
        dict: First question and AI response
    """
    workflow = TaxProcessingWorkflow(user_id, client_id, reference)
    return await workflow.start_workflow()


async def process_user_answer(user_id: str, human_response: str, client_id: str = None, reference: str = "individual"):
    """
    Process a user's answer and get the next question.
    
    Args:
        user_id: Unique identifier for the user
        human_response: The user's response to the current question
        client_id: Client ID for database queries
        reference: "individual" or "company"
        
    Returns:
        dict: Next question and AI response, or completion status
    """
    workflow = TaxProcessingWorkflow(user_id, client_id, reference)
    return await workflow.process_next_question(human_response)


async def get_user_progress(user_id: str):
    """
    Get the current progress for a user.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        dict: Progress summary
    """
    workflow = TaxProcessingWorkflow(user_id)
    return workflow.get_progress_summary()


# Example usage
if __name__ == "__main__":
    async def main():
        # Example workflow
        user_id = "test_user_123"
        client_id = "TESTDEM1"
        reference = "individual"
        
        print("=" * 60)
        print("🚀 Starting Tax Filing Workflow")
        print("=" * 60)
        
        # Start the workflow
        result = await start_tax_workflow(user_id, client_id, reference)
        print(f"\n✅ Status: {result['status']}")
        print(f"📝 Question: {result.get('question', '')}")
        print(f"🤖 AI Response: {result.get('ai_response', '')}")
        
        # Simulate user responses
        print("\n" + "=" * 60)
        print("💬 Simulating user response...")
        print("=" * 60)
        
        # Example: User confirms the information
        user_answer = "yes, that's correct"
        result = await process_user_answer(user_id, user_answer, client_id, reference)
        
        if result['status'] == 'in_progress':
            print(f"\n✅ Status: {result['status']}")
            print(f"📝 Next Question: {result.get('question', '')}")
            print(f"🤖 AI Response: {result.get('ai_response', '')}")
            print(f"📊 Progress: {result['completed']}/{result['total_questions']} completed")
        else:
            print(f"\n🎉 {result.get('message', 'Workflow completed!')}")
        
        # Get progress summary
        print("\n" + "=" * 60)
        print("📊 Progress Summary")
        print("=" * 60)
        progress = await get_user_progress(user_id)
        print(json.dumps(progress, indent=2))
    
    asyncio.run(main())
