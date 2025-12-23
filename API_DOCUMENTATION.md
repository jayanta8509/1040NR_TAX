# Single Endpoint Tax Workflow API

## Overview

**One endpoint does everything:** `POST /tax/workflow`

This single endpoint handles:
1. ✅ Question generation and saving to JSON
2. ✅ First question via `ask_question`
3. ✅ Answer validation via `validation_identification`
4. ✅ Smart flow control (update vs. next question)
5. ✅ Progress tracking

## How to Use

### First Call (Start Workflow)

**Set `human_response` to "start"**

```bash
curl -X POST http://localhost:8000/tax/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "client_id": "TESTDEM1",
    "reference": "individual",
    "human_response": "start"
  }'
```

**Response:**
```json
{
    "status": "started",
    "question_number": 1,
    "total_questions": 12,
    "question": "Confirm your full legal name...",
    "ai_response": "I see you provided 'John Doe'. Is this correct?",
    "completed": 0,
    "validation_result": null,
    "timestamp": 1703345678.123
}
```

### Subsequent Calls (Answer Questions)

**Include `human_response` with user's answer**

```bash
curl -X POST http://localhost:8000/tax/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "client_id": "TESTDEM1",
    "reference": "individual",
    "human_response": "yes, that is correct"
  }'
```

**Response (User Confirmed - Next Question):**
```json
{
    "status": "in_progress",
    "question_number": 2,
    "total_questions": 12,
    "question": "What is your date of birth?",
    "ai_response": "Please provide your date of birth...",
    "completed": 1,
    "validation_result": false,
    "timestamp": 1703345678.123
}
```

**Response (User Wants Update - Same Question):**
```json
{
    "status": "in_progress",
    "question_number": 1,
    "total_questions": 12,
    "question": "no, it should be Jane Smith",
    "ai_response": "I've updated your name to Jane Smith. Is this correct?",
    "completed": 0,
    "validation_result": true,
    "timestamp": 1703345678.123
}
```

**Response (Completed):**
```json
{
    "status": "completed",
    "message": "🎉 All questions have been completed!",
    "total_questions": 12,
    "completed_questions": 12,
    "timestamp": 1703345678.123
}
```

## Complete Example Flow

```python
import requests

BASE_URL = "http://localhost:8000"
user_id = "john_123"
client_id = "TESTDEM1"

# Step 1: Start workflow with "start"
response = requests.post(f"{BASE_URL}/tax/workflow", json={
    "user_id": user_id,
    "client_id": client_id,
    "reference": "individual",
    "human_response": "start"
})
data = response.json()
print(f"Q1: {data['ai_response']}")

# Step 2: Answer question
response = requests.post(f"{BASE_URL}/tax/workflow", json={
    "user_id": user_id,
    "client_id": client_id,
    "reference": "individual",
    "human_response": "yes, correct"
})
data = response.json()

if data['status'] == 'completed':
    print("Done!")
else:
    print(f"Q{data['question_number']}: {data['ai_response']}")
    
# Step 3: User wants to update
response = requests.post(f"{BASE_URL}/tax/workflow", json={
    "user_id": user_id,
    "client_id": client_id,
    "reference": "individual",
    "human_response": "no, it should be 05/15/1985"
})
data = response.json()
print(f"Validation: {data['validation_result']}")  # True = wants update
print(f"AI: {data['ai_response']}")

# Continue until status == 'completed'
```

## Validation Logic

The endpoint automatically determines user intent:

| User Says | validation_result | Action |
|-----------|------------------|--------|
| "yes", "correct", "that's right" | `false` | ✅ Move to next question |
| "no, it should be...", "change to..." | `true` | 🔄 Ask human_response as question |

## Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | Unique user identifier |
| `client_id` | string | Yes | Client ID for database queries |
| `reference` | string | Yes | "individual" or "company" |
| `human_response` | string | No | User's answer (omit for first call) |

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "started", "in_progress", or "completed" |
| `question_number` | int | Current question number |
| `total_questions` | int | Total number of questions |
| `question` | string | The question being asked |
| `ai_response` | string | AI agent's response |
| `completed` | int | Number of completed questions |
| `validation_result` | bool/null | true=update, false=confirmed, null=first |
| `timestamp` | float | Unix timestamp |

## Run the API

```bash
python app.py
```

Server: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

## That's It!

Just one endpoint. Call it with `human_response: "start"` to begin, then keep calling it with user's answers until `status == "completed"`.
