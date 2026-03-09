from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import httpx
import json
import re
import os
from .assistant import SCSAssistant
from .config import settings

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

# MCP Service URL - use environment variable or default to localhost for dev
MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:8007")

class ChatRequest(BaseModel):
    message: str
    case_info: Optional[Dict] = None
    conversation_history: List[Dict] = []
    user_id: str = "system"
    execute_tools: bool = True  # Whether to execute tools or just return proposed actions

class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None
    reasoning: Optional[str] = None
    next_steps: Optional[str] = None

async def execute_mcp_tools(tool_calls: List[Dict], case_id: str, user_id: str) -> List[Dict]:
    """Execute tools via MCP service"""
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            params = tool_call.get("parameters", {})
            
            # Always include case_id
            if case_id:
                params["case_id"] = case_id
            
            try:
                # Map tool names to MCP endpoints
                if tool_name == "add_checklist_item":
                    url = f"{MCP_SERVICE_URL}/tools/add_checklist_item"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "update_checklist_item_status":
                    url = f"{MCP_SERVICE_URL}/tools/update_checklist_item_status"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "request_reassignment":
                    url = f"{MCP_SERVICE_URL}/tools/request_reassignment"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "submit_review_request":
                    url = f"{MCP_SERVICE_URL}/tools/submit_review_request"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "add_case_note":
                    url = f"{MCP_SERVICE_URL}/tools/add_case_note"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "update_case_status":
                    url = f"{MCP_SERVICE_URL}/tools/update_case_status"
                    response = await client.post(
                        url,
                        json=params,
                        headers={"X-User-Id": user_id}
                    )
                elif tool_name == "get_case":
                    url = f"{MCP_SERVICE_URL}/tools/get_case/{params.get('case_id')}"
                    response = await client.get(
                        url,
                        headers={"X-User-Id": user_id}
                    )
                else:
                    results.append({
                        "tool": tool_name,
                        "success": False,
                        "error": f"Unknown tool: {tool_name}"
                    })
                    continue
                
                if response.status_code == 200:
                    results.append({
                        "tool": tool_name,
                        "success": True,
                        "result": response.json()
                    })
                else:
                    results.append({
                        "tool": tool_name,
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    })
                    
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
    
    return results

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
        tool_calls = None
        reasoning = None
        next_steps = None
        tool_results = None
        
        # Try to parse JSON from response (with or without code blocks)
        tool_data = None
        if "```json" in response:
            # Extract JSON from code block
            json_match = re.search(r'```json\n(.+?)\n```', response, re.DOTALL)
            if json_match:
                try:
                    tool_data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
        
        # If no code block or parsing failed, try parsing the entire response
        if not tool_data:
            try:
                tool_data = json.loads(response.strip())
            except json.JSONDecodeError:
                pass
        
        # Extract tool information if we successfully parsed JSON
        if tool_data:
            tool_calls = tool_data.get("tool_calls")
            reasoning = tool_data.get("reasoning")
            next_steps = tool_data.get("next_steps")
        
        # Execute tools if requested and case_info is provided
        if request.execute_tools and tool_calls and request.case_info:
            case_id = request.case_info.get("case_id") or request.case_info.get("code")
            if case_id:
                tool_results = await execute_mcp_tools(tool_calls, case_id, request.user_id)
                
                # Format results back into response
                if tool_results:
                    results_summary = "\n\n**Tool Execution Results:**\n"
                    for result in tool_results:
                        if result["success"]:
                            results_summary += f"✅ {result['tool']}: Success\n"
                        else:
                            results_summary += f"❌ {result['tool']}: {result.get('error', 'Failed')}\n"
                    
                    response += results_summary
        
        return ChatResponse(
            response=response,
            tool_calls=tool_calls,
            tool_results=tool_results,
            reasoning=reasoning,
            next_steps=next_steps
        )
        
    except Exception as e:
        import traceback
        print(f"\n❌ CHATBOT ERROR: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "chatbot"}

@app.get("/rag/status")
async def rag_status():
    """Get ChromaDB collection status"""
    count = assistant.rag.collection.count()
    return {
        "status": "ready",
        "collection_name": "scs_protocols",
        "document_count": count,
        "chroma_path": assistant.rag.chroma_path,
        "docs_path": assistant.rag.docs_path
    }

@app.post("/rag/clear-and-reingest")
async def clear_and_reingest():
    """Clear ChromaDB and re-ingest all documents with new embeddings"""
    try:
        print("\n🔄 Starting ChromaDB re-ingestion...")
        assistant.rag.clear_and_reingest()
        new_count = assistant.rag.collection.count()
        return {
            "status": "success",
            "message": f"Successfully cleared and re-ingested {new_count} documents",
            "document_count": new_count
        }
    except Exception as e:
        import traceback
        print(f"❌ Re-ingestion error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Re-ingestion failed: {str(e)}")

class RecommendationRequest(BaseModel):
    case_info: Dict

@app.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """Generate AI-powered recommendations for a specific case"""
    try:
        recommendations = assistant.generate_recommendations(request.case_info)
        return {
            "status": "success",
            "recommendations": recommendations,
            "case_id": request.case_info.get("code", "unknown")
        }
    except Exception as e:
        import traceback
        print(f"❌ Recommendations error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")

