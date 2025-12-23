# 1040NR Tax Filing Workflow System

AI-powered conversational workflow for collecting and validating 1040NR tax filing information with intelligent question generation and response validation.

## 🎯 Overview

This system provides a complete workflow for guiding users through tax filing information collection using:
- **Automatic question generation** based on database schema
- **Intelligent validation** to detect user intent (update vs. confirm)
- **Step-by-step processing** with progress tracking
- **MCP integration** for database operations
- **Single API endpoint** for simplicity

## 🏗️ Architecture

```
┌─────────────────┐
│   FastAPI App   │  Single endpoint: /tax/workflow
└────────┬────────┘
         │
    ┌────▼────────────────────────────┐
    │  Tax Processing Workflow        │
    │  - Question generation          │
    │  - Progress tracking            │
    │  - Validation orchestration     │
    └────┬───────────────┬────────────┘
         │               │
    ┌────▼─────┐    ┌───▼──────────┐
    │ Question │    │  Validation  │
    │Generator │    │    Agent     │
    └────┬─────┘    └───┬──────────┘
         │              │
    ┌────▼──────────────▼────┐
    │   AI Client (ask_q)    │
    │   - Checks DB first    │
    │   - Asks questions     │
    │   - Updates data       │
    └────┬───────────────────┘
         │
    ┌────▼────────┐
    │ MCP Tools   │
    │ - Get data  │
    │ - Update    │
    └─────────────┘
```

## 📁 Project Structure

```
1040NR_TAX/
├── app.py                      # FastAPI application (single endpoint)
├── process.py                  # Workflow orchestration
├── question_generator.py       # Generates questions from MCP schema
├── validation_intelegent.py    # Validates user intent
├── client.py                   # AI agent for asking questions
├── mcp_functions.py           # Database GET operations
├── mcp_update_functions.py    # Database UPDATE operations
├── connection.py              # Database connection
├── API_DOCUMENTATION.md       # API usage guide
└── README.md                  # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- MySQL database
- OpenAI API key
- Redis (for conversation memory)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd 1040NR_TAX

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install fastapi uvicorn langchain langchain-openai python-dotenv mysql-connector-python redis

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

Create a `.env` file:

```env
OPENAI_API_KEY=your-openai-api-key
DB_HOST=your-mysql-host
DB_USER=your-mysql-user
DB_PASSWORD=your-mysql-password
DB_NAME=your-database-name
HOST=your-redis-host
PORT=your-redis-port
PASSWORD=your-redis-password
```

### Run the Application

```bash
python app.py
```

Server runs on: `http://localhost:8000`

API docs: `http://localhost:8000/docs`

## 📡 API Usage

### Single Endpoint: `POST /tax/workflow`

**Start Workflow:**
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

**Answer Questions:**
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

## 🔄 Workflow Process

1. **User sends "start"** → System generates questions and saves to JSON
2. **First question asked** → AI checks database and asks question
3. **User provides answer** → Validation agent analyzes intent
4. **If validation = True** (wants update) → Ask human_response as question
5. **If validation = False** (confirmed) → Move to next question
6. **Repeat** until all questions completed

## 🗃️ Data Fields Collected

Based on available MCP functions:

1. **Full Legal Name** - First, middle, last name
2. **Date of Birth** - Format: YYYY-MM-DD
3. **Current US Address** - Address, city, state, ZIP, country
4. **Occupation & Income Source** - Current occupation and US income source
5. **ITIN Information** - Whether ITIN exists and ITIN number

## 🧠 Intelligent Validation

The validation agent analyzes three inputs:
- **Question**: Original tax question
- **AI Response**: What the AI asked/confirmed
- **Human Response**: User's actual answer

**Returns:**
- `true` → User wants to UPDATE (e.g., "no, it should be...")
- `false` → User wants to KEEP (e.g., "yes, correct")

## 📊 Progress Tracking

For each user, the system creates:

```
questions_{user_id}.json    # Generated questions
progress_{user_id}.json     # User's progress and answers
```

## 🛠️ MCP Functions

### GET Functions
- `get_client_full_legal_name`
- `get_client_date_of_birth`
- `get_client_current_us_address`
- `get_client_occupation_and_us_income_source`
- `get_client_itin_exists`
- `get_client_itin_number`

### UPDATE Functions
- `update_client_full_legal_name`
- `update_client_date_of_birth`
- `update_client_current_us_address`
- `update_client_occupation_and_us_income_source`
- `update_client_itin_number`

## 🎨 Features

✅ **Single API endpoint** - Simple integration  
✅ **Automatic question generation** - Based on database schema  
✅ **Intelligent validation** - Detects update vs. confirm intent  
✅ **Progress persistence** - Resume from where you left off  
✅ **Database integration** - Checks existing data before asking  
✅ **Conversational AI** - Natural language responses  
✅ **No task/subtask formatting** - Clean, direct responses  

## 📝 Example Conversation

```
User: "start"
AI: "I checked your profile and see you haven't provided a filing status yet. 
     What is your filing status for this tax year?"

User: "Single"
AI: "Got it! I've updated your filing status to Single. Is this correct?"

User: "yes"
AI: "What is your date of birth? (MM/DD/YYYY)"

User: "05/15/1985"
AI: "Thank you! I've recorded your date of birth as 05/15/1985. Is this correct?"
```

## 🔧 Configuration

### Question Generator
Edit `question_generator.py` to customize questions based on your MCP functions.

### Validation Logic
Edit `validation_intelegent.py` to adjust validation sensitivity.

### AI Responses
Edit `client.py` prompt to customize AI response style.

## 📚 Documentation

- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [FastAPI Docs](http://localhost:8000/docs) - Interactive API documentation

## 🚢 Deployment

### Production Deployment

```bash
# Run with multiple workers
nohup uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4 > app.log 2>&1 &
```

### Docker Deployment

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🐛 Troubleshooting

**Questions not generating?**
- Check OpenAI API key in `.env`
- Verify `question_generator.py` is working

**Validation not working?**
- Check model name in `validation_intelegent.py`
- Ensure OpenAI API is accessible

**Database connection issues?**
- Verify MySQL credentials in `.env`
- Check `connection.py` configuration

**Redis connection failed?**
- Verify Redis credentials in `.env`
- Check if Redis server is running

## 📄 License

[Your License Here]

## 👥 Contributors

[Your Name/Team]

## 🤝 Support

For issues and questions, please open an issue on GitHub or contact [your-email@example.com]
