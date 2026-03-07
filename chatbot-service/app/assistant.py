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
        
        # Initialize RAG system (auto-ingests if empty)
        print("Initializing SCS Assistant with RAG...")
        self.rag = RAGSystem(docs_path=settings.docs_dir, chroma_path=settings.chroma_persist_dir)
        print("✓ SCS Assistant ready!")
        
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
TOOL USAGE PRINCIPLES
--------------------------------------------------
- Use WRITE tools only when user explicitly requests an action.
- Do NOT automatically create checklist items unless user asks.
- When creating checklist items, ensure they logically follow prior case context.
- When requesting reassignment or review, keep reason under 50 words.

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

When giving advisory guidance:
- Provide structured sections:
  1. Protocol Reference
  2. Assessment
  3. Recommended Actions
  4. Risk Considerations
- Stay under 500 words total.

--------------------------------------------------
CRITICAL SAFETY RULE
--------------------------------------------------
If the request is unrelated to SCS Singapore youth casework:
Respond with:
"This assistant is restricted to SCS Singapore case management and protocol guidance."
"""

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
            temperature=0.3
        )
        
        return response.choices[0].message.content
    
    def generate_recommendations(self, case_info: Dict) -> List[str]:
        """Generate concise action recommendations for a case based on chromaDB protocols"""
        
        # Build a query based on case details
        query = f"Protocols for {case_info.get('category', 'general')} cases with risk level {case_info.get('riskLevel', 'unknown')}"
        
        # Get relevant protocol context from chromaDB
        rag_context = self.get_context_from_rag(query, case_info)
        
        # Build case summary for LLM
        case_summary = f"""
Case ID: {case_info.get('code', 'Unknown')}
Category: {case_info.get('category', 'Unknown')}
Risk Level: {case_info.get('riskLevel', 0)}/5 ({case_info.get('risk_label', 'Unknown')})
Status: {case_info.get('status', 'Unknown')}
Risk Score: {case_info.get('current_risk_score', 0)}%

AI Explanation Signals:
{chr(10).join(f"- {signal}" for signal in case_info.get('signals', []))}
"""
        
        # Create prompt for recommendations
        prompt = f"""{rag_context}

{case_summary}

Based on the SCS protocols above and the case details, provide exactly 3-5 short, actionable recommendations for the youth worker handling this case. 

Each recommendation should be:
- Specific to this case context
- Grounded in the retrieved protocols
- Action-oriented and concise (max 15 words each)
- Practical and immediately applicable

Format your response as a numbered list with ONLY the recommendations, no additional text or explanations:
1. [First recommendation]
2. [Second recommendation]
3. [Third recommendation]
etc.
"""
        
        # Call LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert at SCS protocols. Provide concise, actionable recommendations based solely on retrieved protocol documents."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        
        # Parse the response into a list
        content = response.choices[0].message.content
        recommendations = []
        
        # Extract numbered recommendations
        import re
        lines = content.strip().split('\n')
        for line in lines:
            # Match patterns like "1. ", "1) ", etc.
            match = re.match(r'^\d+[\.)]\s*(.+)$', line.strip())
            if match:
                recommendations.append(match.group(1).strip())
        
        return recommendations[:5]  # Return max 5 recommendations