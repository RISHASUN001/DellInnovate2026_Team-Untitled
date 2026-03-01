# MCP Agent Quick Start Guide

## Prerequisites
- Docker and Docker Compose installed
- MongoDB Atlas connection string in `.env` file
- OpenRouter API key configured

## Setup Steps

### 1. Update Environment Variables
Create/update `.env` file in project root:

```env
# MongoDB
MONGODB_URI=mongodb+srv://yash5902:gTIYTuF7FePJ8XUS@cluster0.1yrcnpc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
SCS_DB_NAME=dellinnovate

# OpenRouter (Claude AI)
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Service URLs
MCP_SERVICE_URL=http://mcp-service:8003
CHATBOT_SERVICE_URL=http://chatbot-service:8002
CASE_SERVICE_URL=http://case-service:8001
```

### 2. Install MCP Service Dependencies
```bash
cd mcp-service
pip install -r requirements.txt
```

### 3. Start Services
```bash
# From project root
docker-compose up -d

# Or build from scratch
docker-compose up --build -d
```

### 4. Verify Services Running
```bash
# Check MCP service
curl http://localhost:8003/health

# Check Chatbot service
curl http://localhost:8002/health

# Expected response: {"status": "healthy", "service": "mcp-service"}
```

## Testing the Agent

### Test 1: Add Checklist Item via Chatbot

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add checklist item: Schedule parent meeting",
    "case_info": {
      "case_id": "CASE-0001",
      "category": "Family Conflict"
    },
    "user_id": "john_smith",
    "execute_tools": true
  }' | jq
```

**Expected Response:**
```json
{
  "response": "I've added the checklist item 'Schedule parent meeting' to CASE-0001...",
  "tool_calls": [
    {
      "tool": "add_checklist_item",
      "parameters": {
        "case_id": "CASE-0001",
        "label": "Schedule parent meeting",
        "is_mandatory": false
      }
    }
  ],
  "tool_results": [
    {
      "tool": "add_checklist_item",
      "success": true,
      "result": {
        "checklist_item_id": 42,
        "label": "Schedule parent meeting",
        "case_id": "CASE-0001"
      }
    }
  ]
}
```

### Test 2: Request Reassignment

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to reassign CASE-0002 because it requires senior worker expertise",
    "case_info": {
      "case_id": "CASE-0002",
      "assigned_to": "john_smith"
    },
    "user_id": "john_smith",
    "execute_tools": true
  }' | jq
```

### Test 3: Submit Review Request (Escalation)

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "CASE-0003 risk level has increased, need to escalate for review",
    "case_info": {
      "case_id": "CASE-0003",
      "current_risk_score": 80
    },
    "user_id": "sarah_l",
    "execute_tools": true
  }' | jq
```

### Test 4: Update Checklist Item Status

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Mark checklist item 42 as complete for CASE-0001. Parent meeting was successful.",
    "case_info": {
      "case_id": "CASE-0001"
    },
    "user_id": "john_smith",
    "execute_tools": true
  }' | jq
```

## Verify MongoDB Updates

### Check Checklist Items
```bash
mongosh "mongodb+srv://cluster0.1yrcnpc.mongodb.net/dellinnovate" --apiVersion 1 --username yash5902

# In MongoDB shell:
db.scs_checklist.find({"case_id": "CASE-0001"}).sort({"created_at": -1}).limit(5)
```

### Check Audit Log
```bash
# Via MCP service endpoint (Admin only)
curl "http://localhost:8003/audit-log?case_id=CASE-0001&limit=10" \
  -H "X-User-Id: sarah_l" \
  -H "X-User-Role: Admin" | jq
```

### Check Reassignment Requests
```bash
mongosh "mongodb+srv://cluster0.1yrcnpc.mongodb.net/dellinnovate" --apiVersion 1 --username yash5902

# In MongoDB shell:
db.scs_reassignment_requests.find({}).sort({"created_at": -1}).limit(5)
```

### Check Review Requests
```bash
db.scs_review_requests.find({}).sort({"created_at": -1}).limit(5)
```

## Common Test Scenarios

### 1. Natural Language Request
**Input:** "Can you add a checklist item to schedule a parent meeting for case CASE-0001?"

**Expected:** LLM identifies `add_checklist_item` tool and extracts parameters

### 2. Multi-Step Request
**Input:** "Mark item 42 complete for CASE-0001 with note 'Meeting completed', then add a follow-up item"

**Expected:** LLM generates multiple tool calls in sequence

### 3. Escalation with Reasoning
**Input:** "Risk increased to 85%, multiple self-harm indicators. Need to escalate CASE-0005 immediately."

**Expected:** LLM calls `submit_review_request` with `review_type: "escalation"` and detailed reasoning

## Debugging

### Enable Debug Logging
```bash
# In docker-compose.yml, add environment variable:
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart mcp-service chatbot-service
```

### View MCP Service Logs
```bash
docker-compose logs -f mcp-service
```

### View Chatbot Service Logs
```bash
docker-compose logs -f chatbot-service
```

### Common Issues

#### 1. "Not your assigned case" error
**Cause:** User doesn't have access to case
**Solution:** Check `scs_cases.assigned_to` field matches `user_id` in request

#### 2. Tool not executing
**Cause:** `execute_tools: false` or missing `case_id`
**Solution:** Set `execute_tools: true` and include `case_info.case_id`

#### 3. MongoDB connection timeout
**Cause:** Network/IP whitelist issue
**Solution:** Add 0.0.0.0/0 to Atlas IP whitelist

#### 4. LLM not identifying tools
**Cause:** Ambiguous user message
**Solution:** Be more explicit in request:
- ❌ "Help with this case"
- ✅ "Add checklist item: Schedule parent meeting for CASE-1234"

## Frontend Integration

### Send request from Youth Dashboard
```javascript
// In scs_dashboard.jsx chatbot component
const sendMessage = async (message) => {
  const response = await fetch('http://localhost:8002/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      message: message,
      case_info: selectedCase,
      user_id: currentUser.user_id,
      execute_tools: true,
      conversation_history: chatHistory
    })
  });
  
  const data = await response.json();
  
  // Display tool results
  if (data.tool_results) {
    data.tool_results.forEach(result => {
      if (result.success) {
        showSuccessToast(`✅ ${result.tool} executed successfully`);
      } else {
        showErrorToast(`❌ ${result.tool} failed: ${result.error}`);
      }
    });
  }
  
  return data.response;
};
```

## Production Checklist
- [ ] Update MONGODB_URI with production credentials
- [ ] Set OPENROUTER_API_KEY from secure vault
- [ ] Configure ALLOWED_ORIGINS for production domain
- [ ] Enable HTTPS/TLS for all services
- [ ] Set up MongoDB backup schedule
- [ ] Configure rate limiting on chat endpoint
- [ ] Set up monitoring/alerting for tool failures
- [ ] Review and tune LLM system prompt
- [ ] Test all error scenarios
- [ ] Document all deployed tools

## Next Steps
1. Test all tools with various case scenarios
2. Add frontend UI for viewing tool execution history
3. Implement approval workflow (optional)
4. Set up monitoring dashboards
5. Train helpers on natural language commands
