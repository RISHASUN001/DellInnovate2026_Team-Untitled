# MCP Agent Architecture for SCS Case Management

## Overview

The MCP (Model Context Protocol) agent system enables AI-driven case management operations through a secure, approval-gated architecture. The LLM analyzes user requests, determines appropriate tools to call, executes them via the MCP service, and returns formatted results.

## Architecture Flow

```
User Request → Chatbot Service (Claude AI) → MCP Service (Tool Gateway) → MongoDB
                      ↓                               ↓
              Analyzes intent                  Executes tools
                      ↓                               ↓
           Identifies tool calls            Audit logging & validation
                      ↓                               ↓
          Formats response ← ← ← ← ← ← ← ← Returns results
```

## Components

### 1. **Chatbot Service** (Port 8002)
- **Technology:** FastAPI + Claude AI (via OpenRouter)
- **Responsibilities:**
  - Receives user messages
  - Analyzes intent using Claude AI with RAG (protocol search)
  - Parses tool calls from LLM responses
  - Calls MCP service to execute tools
  - Formats results for user

- **Endpoint:** `POST /chat`
  ```json
  {
    "message": "Add checklist item: Schedule parent meeting",
    "case_info": {"case_id": "CASE-1234", "category": "Family Conflict"},
    "user_id": "john_smith",
    "execute_tools": true
  }
  ```

- **Response:**
  ```json
  {
    "response": "I've added the checklist item...",
    "tool_calls": [{"tool": "add_checklist_item", "parameters": {...}}],
    "tool_results": [{"tool": "add_checklist_item", "success": true, "result": {...}}],
    "reasoning": "Based on SCS protocol...",
    "next_steps": "Follow up within 48 hours..."
  }
  ```

### 2. **MCP Service** (Port 8003)
- **Technology:** FastAPI + MongoDB (Motor driver)
- **Responsibilities:**
  - Tool execution gateway
  - Role-based access control (helpers can only modify assigned cases)
  - Audit logging (all operations logged to `mcp_audit_log` collection)
  - MongoDB CRUD operations

- **Collections Used:**
  - `scs_cases` - Case data
  - `scs_checklist` - Checklist items
  - `scs_reassignment_requests` - Reassignment requests
  - `scs_review_requests` - Review/escalation requests
  - `mcp_audit_log` - Audit trail

### 3. **MongoDB Database**
- **Cluster:** Atlas - dellinnovate
- **Collections:**
  - `scs_users` - User profiles
  - `scs_cases` - Case records
  - `scs_checklist` - Checklist items
  - `scs_case_history` - Risk score history
  - `scs_reassignment_requests` - Reassignment requests
  - `scs_review_requests` - Review requests
  - `mcp_audit_log` - Tool execution audit log
  - `counters` - Auto-increment ID generator

## Available MCP Tools

### Read Tools (No Approval Required)
1. **get_case** - Get full case details
   - Parameters: `case_id`
   
2. **list_cases_summary** - List cases (filtered)
   - Parameters: `category` (optional), `status` (optional)
   
3. **list_assigned_cases** - Get cases assigned to user
   - No parameters

4. **get_case_history** - Get case risk history
   - Parameters: `case_id`

### Write Tools (Validated & Logged)
5. **add_checklist_item** - Create new checklist item
   - Parameters: `case_id`, `label`, `is_mandatory` (optional)
   - Returns: `checklist_item_id`, `label`, `case_id`
   
6. **update_checklist_item_status** - Mark checklist item complete/incomplete
   - Parameters: `case_id`, `checklist_item_id`, `completed` (boolean), `comment`
   - Returns: `checklist_item_id`, `completed`, `comment_saved`
   
7. **request_reassignment** - Submit reassignment request
   - Parameters: `case_id`, `reason`, `requested_to` (optional)
   - Returns: `request_id`, `case_id`, `status: "pending"`
   
8. **submit_review_request** - Submit review/escalation request
   - Parameters: `case_id`, `review_type` ("escalation"/"closure"/"follow_up"/"general"), `reason`
   - Returns: `request_id`, `case_id`, `review_type`, `status: "pending"`
   
9. **add_case_note** - Add note to case
   - Parameters: `case_id`, `content`, `note_type` (optional: "general"/"outreach"/"protocol")
   - Returns: `case_id`, `note_type`, `saved: true`
   
10. **update_case_status** - Update case status
    - Parameters: `case_id`, `status` ("new"/"in_progress"/"in_review"/"outreach"/"followup"/"completed"/"closed")
    - Returns: `case_id`, `status`

## Example Usage Scenarios

### Scenario 1: Add Checklist Item
**User:** "Add checklist item: Schedule parent meeting for CASE-1234"

**Claude Analysis:**
- Intent: Create new checklist item
- Tool: `add_checklist_item`
- Parameters extracted from context

**Tool Execution:**
```json
{
  "tool": "add_checklist_item",
  "parameters": {
    "case_id": "CASE-1234",
    "label": "Schedule parent meeting",
    "is_mandatory": false
  }
}
```

**MCP Service:**
1. Validates user has write access to CASE-1234
2. Inserts into `scs_checklist` collection
3. Logs to `mcp_audit_log`
4. Returns: `{checklist_item_id: 42, label: "Schedule parent meeting", case_id: "CASE-1234"}`

**Chatbot Response:**
"✅ I've added the checklist item 'Schedule parent meeting' to CASE-1234. Make sure to complete this within the standard 48-hour protocol timeframe."

### Scenario 2: Request Reassignment
**User:** "This case is too complex for me, need to reassign to senior worker"

**Claude Analysis:**
- Intent: Request case reassignment
- Tool: `request_reassignment`
- Reasoning: Helper acknowledges need for escalation

**Tool Execution:**
```json
{
  "tool": "request_reassignment",
  "parameters": {
    "case_id": "CASE-5678",
    "reason": "Case complexity requires senior worker expertise - multiple family dynamics and high-risk signals",
    "requested_to": null
  }
}
```

**MCP Service:**
1. Validates helper is assigned to CASE-5678
2. Inserts into `scs_reassignment_requests` with status "pending"
3. Returns: `{request_id: 7, case_id: "CASE-5678", status: "pending"}`

**Chatbot Response:**
"✅ I've submitted your reassignment request for CASE-5678. An admin will review and assign to an appropriate senior worker. In the meantime, continue monitoring any urgent signals."

### Scenario 3: Submit Escalation Review
**User:** "Risk level has increased significantly, need to escalate CASE-9012"

**Claude Analysis:**
- Intent: Escalate case for review
- Tool: `submit_review_request`
- Review type: escalation

**Tool Execution:**
```json
{
  "tool": "submit_review_request",
  "parameters": {
    "case_id": "CASE-9012",
    "review_type": "escalation",
    "reason": "Risk score increased from 2 to 4 within 48 hours. New self-harm indicators detected."
  }
}
```

**MCP Service:**
1. Validates access to CASE-9012
2. Inserts into `scs_review_requests`
3. Updates case status to "in_review"
4. Returns: `{request_id: 12, case_id: "CASE-9012", review_type: "escalation", status: "pending"}`

**Chatbot Response:**
"✅ I've submitted an escalation review request for CASE-9012. The case status has been updated to 'in_review'. An admin will prioritize this for immediate assessment. Follow mandatory reporting protocols if there's imminent danger."

## Security & Access Control

### Role-Based Permissions
- **Admins:** Full access to all cases and tools
- **Helpers:** Can only modify their assigned cases (checked via `assigned_to` field)

### Validation Flow
1. Extract user from request headers (`X-User-Id`)
2. For write operations on cases:
   - Query `scs_cases` for case ownership
   - If helper role: Verify `assigned_to === user.user_id`
   - If admin role: Allow all operations
3. Log all operations to `mcp_audit_log`

### Audit Logging
Every tool execution is logged with:
- `tool_name` - Which tool was called
- `actor_id` - Who triggered the call
- `actor_role` - User's role
- `payload` - Tool parameters (truncated for PII safety)
- `result` - Tool execution result
- `case_id` - Which case was affected
- `created_at` - ISO 8601 timestamp

Query audit logs: `GET /audit-log?case_id=CASE-1234&limit=50` (Admin only)

## Testing the Agent

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Test Chatbot Integration
```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add checklist item: Contact school counselor",
    "case_info": {"case_id": "CASE-0001", "category": "Academic Stress"},
    "user_id": "john_smith",
    "execute_tools": true
  }'
```

### 3. Verify MongoDB Update
```bash
# Check checklist collection
db.scs_checklist.find({"case_id": "CASE-0001"}).sort({"created_at": -1}).limit(1)

# Check audit log
db.mcp_audit_log.find({"case_id": "CASE-0001"}).sort({"created_at": -1}).limit(1)
```

### 4. Test Direct MCP Calls
```bash
# Add checklist item
curl -X POST http://localhost:8003/tools/add_checklist_item \
  -H "Content-Type: application/json" \
  -H "X-User-Id: john_smith" \
  -d '{
    "case_id": "CASE-0001",
    "label": "Schedule parent meeting",
    "is_mandatory": false
  }'
```

## Configuration

### Environment Variables

#### MCP Service (.env)
```env
MONGODB_URI=mongodb+srv://...@cluster0.mongodb.net/
SCS_DB_NAME=dellinnovate
CHATBOT_SERVICE_URL=http://chatbot-service:8002
DEFAULT_USER_ID=sarah_l
DEFAULT_USER_ROLE=Admin
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
```

#### Chatbot Service (.env)
```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
MCP_SERVICE_URL=http://mcp-service:8003
```

## Troubleshooting

### Issue: Tool calls not executing
**Solution:** Check `execute_tools: true` in chat request and verify `case_info` includes `case_id`

### Issue: "Not your assigned case" error
**Solution:** Verify user has access to case (check `scs_cases.assigned_to` field)

### Issue: MongoDB connection errors
**Solution:** Verify MONGODB_URI is correct and Atlas IP whitelist includes 0.0.0.0/0

### Issue: LLM not identifying tools
**Solution:** Rephrase user message to be more explicit:
- ❌ "Can you help with this case?"
- ✅ "Add checklist item: Schedule parent meeting for CASE-1234"

## Future Enhancements
1. **Approval workflow** - Frontend UI for approving tool proposals before execution
2. **Batch operations** - Execute multiple tool calls in a single transaction
3. **Tool result summarization** - LLM reformats raw MongoDB results into natural language
4. **Real-time notifications** - WebSocket updates when tools complete
5. **Tool usage analytics** - Dashboard showing most-used tools and success rates
