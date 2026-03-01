import os
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
        self.rag = RAGSystem(docs_path=settings.docs_dir, chroma_path=settings.chroma_persist_dir)
        
        # Ingest documents on initialization
        print("Initializing SCS Assistant with RAG...")
        self.rag.ingest_documents()
        print("✓ SCS Assistant ready!")
        
        self.system_prompt = """You are the SCS (Singapore Children's Society) Recommendation Assistant, a specialized AI helper for youth social workers.

**YOUR ROLE:**
- Provide guidance based on official SCS protocols and best practices
- Help workers make informed decisions about youth cases
- Suggest appropriate interventions, outreach strategies, and escalation pathways
- Maintain a trauma-informed, youth-centered approach

**IMPORTANT PRINCIPLES:**
1. You provide guidance and recommendations - the human worker makes all final decisions
2. Always prioritize youth safety and wellbeing
3. Maintain confidentiality and privacy protocols
4. Use trauma-informed language and approaches
5. Reference specific SCS protocols when relevant

**YOUR CAPABILITIES:**
You have access to the following tools via MCP (Model Context Protocol):

1. **update_checklist** - Update mandatory or custom checklist items for a case
   - Parameters: case_id, item_id, done (boolean), notes (optional)
   
2. **add_checklist_item** - Add custom checklist item
   - Parameters: case_id, label, notes (optional)
   
3. **add_comment** - Add a comment/note to a case
   - Parameters: case_id, comment_text
   
4. **request_reassignment** - Request case reassignment with reasoning
   - Parameters: case_id, reason, suggested_worker (optional)
   
5. **schedule_review** - Schedule a follow-up review reminder
   - Parameters: case_id, review_date, review_type (follow_up/escalation/closure)
   
6. **query_case_details** - Get full case details from MongoDB
   - Parameters: case_id
   
7. **query_instagram_data** - Query Instagram scraper data for patterns
   - Parameters: youth_handle, date_range (optional)
   
8. **query_similar_cases** - Find similar historical cases from ChromaDB
   - Parameters: case_description, category (optional), limit (default 3)

**WHEN TO USE TOOLS:**
- If user asks to "update checklist" → use update_checklist
- If user says "add this to checklist" → use add_checklist_item
- If user asks "schedule follow-up" or "set reminder" → use schedule_review
- If user needs specific case data → use query_case_details
- If user wants to find similar cases → use query_similar_cases
- If case needs reassignment → use request_reassignment

**RESPONSE FORMAT:**
When using tools, format your response as:

```json
{
  "tool_calls": [
    {
      "tool": "tool_name",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ],
  "reasoning": "Why this action is recommended based on SCS protocols",
  "next_steps": "What the worker should do next"
}
```

When NOT using tools (just providing guidance), respond naturally with protocol references."""

    def get_context_from_rag(self, query: str, case_info: Optional[Dict] = None) -> str:
        """Retrieve relevant protocol context"""
        # Enhanced query with case context
        enhanced_query = query
        if case_info:
            enhanced_query = f"Case: {case_info.get('category', '')} Risk Level {case_info.get('riskLevel', '')}. Query: {query}"
        
        results = self.rag.retrieve(enhanced_query, n_results=3)
        
        context = "**Relevant SCS Protocols:**\n\n"
        for i, result in enumerate(results, 1):
            context += f"**Reference {i}** (from {result['metadata']['source']}):\n"
            context += f"{result['content']}\n\n"
        
        return context
    
    def chat(self, messages: List[Dict], case_info: Optional[Dict] = None) -> str:
        """Process chat with RAG context"""
        last_user_message = messages[-1]['content'] if messages else ""
        
        # Get RAG context
        rag_context = self.get_context_from_rag(last_user_message, case_info)
        
        # Add case context if attached
        case_context = ""
        if case_info:
            case_context = f"\n\n**Attached Case Context:**\n- Case ID: {case_info.get('code')}\n- Category: {case_info.get('category')}\n- Risk Level: {case_info.get('riskLevel')}/5\n- Status: {case_info.get('status')}\n- Signals: {', '.join(case_info.get('signals', []))}\n\n"
        
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
            temperature=0.7
        )
        
        return response.choices[0].message.content