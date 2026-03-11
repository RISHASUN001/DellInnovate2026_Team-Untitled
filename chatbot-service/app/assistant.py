import os
import json
import re
from typing import List, Dict, Optional
from openai import OpenAI
from .rag import RAGSystem
from .config import settings

class SCSAssistant:
    def __init__(self):
        # Use OpenRouter with OpenAI-compatible client
        self.client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        self.model = settings.openrouter_model
        
        # Initialize RAG system (auto-ingests if empty)
        print("Initializing SCS Assistant with RAG...")
        self.rag = RAGSystem(docs_path=settings.docs_dir, chroma_path=settings.chroma_persist_dir)
        print("✓ SCS Assistant ready!")
        
        # Define available tools - ONLY bulk checklist tool
        self.available_tools = {
            "add_checklist_items": {
                "description": "Add multiple checklist items (ALWAYS USE THIS for ANY checklist request)",
                "parameters": {
                    "case_id": "string (required)",
                    "items": "array of {label: string, is_mandatory: boolean} (required)"
                }
            },
            "update_checklist_item_status": {
                "description": "Update checklist item status",
                "parameters": {"case_id": "string", "checklist_item_id": "integer", "completed": "boolean", "comment": "string"}
            },
            "add_case_note": {
                "description": "Add note to case",
                "parameters": {"case_id": "string", "content": "string", "note_type": "string (optional)"}
            },
            "request_reassignment": {
                "description": "Request case reassignment",
                "parameters": {"case_id": "string", "reason": "string (max 50 words)"}
            },
            "submit_review_request": {
                "description": "Submit case for review",
                "parameters": {"case_id": "string", "review_type": "string", "reason": "string (max  50 words)"}
            },
            "update_case_status": {
                "description": "Update case status",
                "parameters": {"case_id": "string", "status": "string"}
            }
        }
        
        self.system_prompt = """You are the SCS (Singapore Children's Society) Case Assistant.

You are STRICTLY limited to:
- Official SCS protocols
- Documents retrieved from ChromaDB (RAG context)
- Case data from MongoDB tools

You MUST NOT:
- Provide general advice unrelated to SCS
- Reference external frameworks unless explicitly found in retrieved documents
- Speculate beyond retrieved protocol context
- Drift outside SCS Singapore operational scope

--------------------------------------------------
PRIMARY ROLE
--------------------------------------------------
1. Provide concise, protocol-grounded recommendations for SCS youth workers.
2. Suggest clear, specific actions aligned to retrieved SCS documents.
3. Support checklist creation, reassignment, escalation, review workflows.
4. Maintain trauma-informed, youth-centered, Singapore-specific context.

--------------------------------------------------
STRICT RESPONSE RULES
--------------------------------------------------

ADVISORY RESPONSES:
- Maximum 500 words.
- Must reference retrieved SCS protocol documents explicitly.
- Must clearly state which document/source is being referenced.
- Must remain specific to SCS Singapore operations.
- No generic or global social work advice.

CHECKLIST ITEMS:
- Must be specific to the case context.
- Must reflect SCS protocols retrieved from ChromaDB.
- Must be short, action-based, and step-oriented.
- No vague or generic tasks.
- Example format:
  "Contact school counsellor to verify attendance records (within 48 hours)."

REASSIGNMENT / REVIEW REQUESTS:
- Maximum 50 words.
- Direct, professional, to-the-point.
- Must reflect case reasoning.
- No emotional or unnecessary explanation.

CASE NOTES:
- Clear, factual, objective.
- Under 120 words.

--------------------------------------------------
RAG ENFORCEMENT
--------------------------------------------------
You MUST base recommendations only on:
1. Retrieved RAG context (ChromaDB)
2. Attached case context
3. Previous conversation history

If RAG context is insufficient:
- State clearly: "Insufficient protocol context retrieved."
- Ask a clarifying question.
- DO NOT invent guidance.

--------------------------------------------------
CRITICAL TOOL USAGE RULES
--------------------------------------------------

For ANY checklist request ("create checklist", "add checklist", "get me checklist items", etc.):
✓ ALWAYS AND ONLY use: "add_checklist_items" (bulk operation)
✗ NEVER use: "add_checklist_item" (singular - THIS TOOL DOES NOT EXIST)
✗ NEVER use: "create_checklist", "get_checklist", or any other variation

Available Tools:
{
  "add_checklist_items": {
    "description": "Add multiple checklist items (ALWAYS USE THIS for ANY checklist request)",
    "parameters": {
      "case_id": "string (required)",
      "items": "array of {label: string, is_mandatory: boolean} (required)"
    }
  },
  "update_checklist_item_status": {...},
  "add_case_note": {...},
  "request_reassignment": {...},
  "submit_review_request": {...},
  "update_case_status": {...}
}

Checklist Item Format:
- Keep labels SHORT: 5-6 words maximum
- Action-based and clear
- No protocol references in text
- is_mandatory defaults to FALSE (only TRUE for critical safety steps)
- Examples:
  ✓ {"label": "Contact school counsellor", "is_mandatory": false}
  ✓ {"label": "Schedule parent meeting", "is_mandatory": false}
  ✗ {"label": "Per protocol 3.2, contact school for assessment", "is_mandatory": false}

General Tool Principles:
- Use WRITE tools only when user explicitly requests an action
- Do NOT automatically create items unless user asks
- Keep all reasons under 50 words

--------------------------------------------------
CONTEXT AWARENESS
--------------------------------------------------
You MUST:
- Understand previous conversation messages.
- Avoid repeating prior actions.
- Ensure new checklist items are not duplicates.
- Ensure that new checlist items are maximum 5 to 6 words long.
- Ensure that the new checklist items do not include refereces, but rather are action-based and general in nature.
- Maintain case continuity.


--------------------------------------------------
RESPONSE FORMAT
--------------------------------------------------

For TOOL CALLS (Return ONLY valid JSON, no markdown blocks):
{
  "tool_calls": [
    {
      "tool": "add_checklist_items",
      "parameters": {
        "case_id": "CASE-XXX",
        "items": [
          {"label": "Contact school counsellor", "is_mandatory": false},
          {"label": "Schedule parent meeting", "is_mandatory": false}
        ]
      }
    }
  ],
  "reasoning": "Based on SCS protocol for [category]",
  "next_steps": "Monitor response within 48 hours"
}

For ADVISORY GUIDANCE (no tools):
- Write clear, natural prose
- Reference specific protocol documents
- Stay under 500 words
- DO NOT mention: ChromaDB, RAG, tool names, retrieval processes, database operations
- DO NOT use JSON or code blocks

When giving advisory guidance:
- Provide structured sections:
  1. Protocol Reference
  2. Assessment
  3. Recommended Actions
  4. Risk Considerations
- Stay under 500 words total.

--------------------------------------------------
CRITICAL SAFETY & SECURITY RULES
--------------------------------------------------
1. If request unrelated to SCS Singapore youth casework:
   "This assistant is restricted to SCS Singapore case management and protocol guidance."

2. NEVER expose internal operations to frontend:
   - Do NOT mention: ChromaDB, RAG, vector search, get_context_cases, retrieval, embedding
   - Do NOT mention: tool names, database operations, technical implementation details
   - User sees only clean, professional guidance
"""

    def get_context_from_rag(self, query: str, case_info: Optional[Dict] = None) -> str:
        """Retrieve relevant protocol context - INTERNAL ONLY"""
        enhanced_query = query
        if case_info:
            enhanced_query = f"Case: {case_info.get('category', '')} Risk Level {case_info.get('riskLevel', '')}. Query: {query}"
        
        results = self.rag.retrieve(enhanced_query, n_results=3)
        
        context = "**Retrieved SCS Protocol References:**\n\n"
        for i, result in enumerate(results, 1):
            context += f"**Source {i}** (from {result['metadata']['source']}):\n"
            context += f"{result['content']}\n\n"
        
        return context
    
    def _normalize_tool_name(self, tool_name: str, parameters: dict) -> str:
        """Force all checklist operations to use bulk tool"""
        tool_lower = tool_name.lower()
        
        # ANY checklist-related tool MUST use add_checklist_items
        if "checklist" in tool_lower and any(word in tool_lower for word in ["create", "add", "get", "make", "generate"]):
            # Convert single item to bulk format if needed
            if "label" in parameters and "items" not in parameters:
                parameters["items"] = [{
                    "label": parameters.pop("label"),
                    "is_mandatory": parameters.pop("is_mandatory", False)
                }]
            return "add_checklist_items"
        
        # Direct match
        if tool_name in self.available_tools:
            return tool_name
        
        return tool_name
    
    def _parse_tool_calls(self, content: str) -> Optional[Dict]:
        """Extract and validate tool calls, ensuring only bulk checklist tool is used"""
        # Quick check if content looks like it contains tool calls
        if "tool_calls" not in content.lower():
            return None
        
        try:
            # Try to extract JSON from markdown blocks or direct JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Only try to parse as JSON if it starts with {
                if not content.strip().startswith('{'):
                    return None
                parsed = json.loads(content)
            
            if "tool_calls" not in parsed:
                return None
            
            valid_tool_calls = []
            for tc in parsed["tool_calls"]:
                if "tool" not in tc or "parameters" not in tc:
                    continue
                
                # Normalize tool name (converts any checklist variant to bulk)
                normalized_tool = self._normalize_tool_name(tc["tool"], tc["parameters"])
                
                if normalized_tool not in self.available_tools:
                    print(f"Warning: Invalid tool '{tc['tool']}' -> '{normalized_tool}', skipping")
                    continue
                
                # Ensure is_mandatory defaults to false
                if normalized_tool == "add_checklist_items" and "items" in tc["parameters"]:
                    for item in tc["parameters"]["items"]:
                        if "is_mandatory" not in item:
                            item["is_mandatory"] = False
                
                valid_tool_calls.append({
                    "tool": normalized_tool,
                    "parameters": tc["parameters"]
                })
            
            if not valid_tool_calls:
                return None
            
            return {
                "tool_calls": valid_tool_calls,
                "reasoning": parsed.get("reasoning", ""),
                "next_steps": parsed.get("next_steps", "")
            }
        except (json.JSONDecodeError, AttributeError):
            # Normal for advisory responses - not an error
            return None
    
    def chat(self, messages: List[Dict], case_info: Optional[Dict] = None) -> str:
        """Process chat with RAG context - NEVER leak internal operations to frontend"""
        last_user_message = messages[-1]['content'] if messages else ""
        
        # Get RAG context INTERNALLY - never mention this to user
        rag_context = self.get_context_from_rag(last_user_message, case_info)
        
        # Add case context if attached
        case_context = ""
        if case_info:
            case_context = f"\n\n**Current Case Context:**\n- Case ID: {case_info.get('code')}\n- Category: {case_info.get('category')}\n- Risk Level: {case_info.get('riskLevel')}/5\n- Status: {case_info.get('status')}\n- Key Signals: {', '.join(case_info.get('signals', [])[:3])}\n\n"
        
        # Build full prompt
        full_system_prompt = self.system_prompt + case_context + rag_context
        
        # Convert messages format for OpenAI-compatible API
        formatted_messages = [
            {"role": "system", "content": full_system_prompt}
        ] + messages
        
        # Call LLM via OpenRouter
        response = self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            max_tokens=2000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # Try to parse tool calls
        tool_calls = self._parse_tool_calls(content)
        
        # If tool calls found, return as JSON
        if tool_calls:
            return json.dumps(tool_calls, indent=2)
        
        # Otherwise clean up response - remove any internal references
        clean_content = content
        # Remove markdown code blocks
        clean_content = re.sub(r'```(?:json)?\s*.*?```', '', clean_content, flags=re.DOTALL)
        # Remove any mentions of internal processes (case-insensitive)
        internal_terms = ['chromadb', 'rag', 'retrieval', 'get_context', 'vector', 'embedding', 'tool_call', 'mcp']
        for term in internal_terms:
            clean_content = re.sub(rf'\b{term}\b', '', clean_content, flags=re.IGNORECASE)
        
        return clean_content.strip()
    
    def generate_recommendations(self, case_info: Dict) -> List[str]:
        """Generate action recommendations - NEVER expose internal operations"""
        
        # Build query based on case details
        query = f"Action recommendations for {case_info.get('category', 'general')} cases with risk level {case_info.get('riskLevel', 'unknown')}"
        
        # Get protocol context INTERNALLY (never mention to user)
        rag_context = self.get_context_from_rag(query, case_info)
        
        # Build case summary for LLM
        case_summary = f"""
Case ID: {case_info.get('code', 'Unknown')}
Category: {case_info.get('category', 'Unknown')}
Risk Level: {case_info.get('riskLevel', 0)}/5
Status: {case_info.get('status', 'Unknown')}
Risk Score: {case_info.get('current_risk_score', 0)}%

Key Case Signals:
{chr(10).join(f"- {signal}" for signal in case_info.get('signals', []))}
"""
        
        # Create prompt - emphasize NO internal references
        prompt = f"""{rag_context}

{case_summary}

Based on the SCS protocols above, provide 3-5 actionable recommendations for the youth worker.

REQUIREMENTS:
- Each recommendation: 10-15 words maximum
- Action-oriented and specific to this case
- Based on protocol documents provided
- Practical and immediately applicable
- NO mention of: ChromaDB, RAG, retrieval, databases, tools, or technical processes

Format as numbered list with ONLY the recommendations:
1. [First recommendation]
2. [Second recommendation]
3. [Third recommendation]

NO additional text, explanations, or technical references.
"""
        
        # Call LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an SCS protocol expert. Provide concise recommendations. NEVER mention ChromaDB, RAG, retrieval processes, or any technical implementation details."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        # Parse and filter response
        content = response.choices[0].message.content
        recommendations = []
        
        lines = content.strip().split('\n')
        for line in lines:
            match = re.match(r'^\d+[\.)]\s*(.+)$', line.strip())
            if match:
                rec = match.group(1).strip()
                # Filter out any internal process mentions
                if not any(term in rec.lower() for term in ['chromadb', 'rag', 'retrieval', 'get_context', 'vector', 'tool', 'mcp']):
                    recommendations.append(rec)
        
        return recommendations[:5]