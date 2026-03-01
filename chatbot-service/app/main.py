from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from .assistant import SCSAssistant
from .config import *

app = FastAPI(title="SCS Chatbot Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize assistant
assistant = SCSAssistant()

class ChatRequest(BaseModel):
    message: str
    case_info: Optional[Dict] = None
    conversation_history: List[Dict] = []

class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict]] = None
    reasoning: Optional[str] = None
    next_steps: Optional[str] = None

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Build messages for Claude
        messages = request.conversation_history + [
            {"role": "user", "content": request.message}
        ]
        
        # Get response with RAG
        response = assistant.chat(messages, request.case_info)
        
        # Parse response for tool calls
        if "```json" in response:
            # Extract JSON tool calls
            import json
            import re
            json_match = re.search(r'```json\n(.+?)\n```', response, re.DOTALL)
            if json_match:
                tool_data = json.loads(json_match.group(1))
                return ChatResponse(
                    response=response,
                    tool_calls=tool_data.get("tool_calls"),
                    reasoning=tool_data.get("reasoning"),
                    next_steps=tool_data.get("next_steps")
                )
        
        return ChatResponse(response=response)
        
    except Exception as e:
        import traceback
        print(f"\n❌ CHATBOT ERROR: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chatbot"}