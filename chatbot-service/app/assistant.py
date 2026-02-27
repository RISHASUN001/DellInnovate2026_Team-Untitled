"""
Single orchestrator assistant.
Combines advisory (RAG-backed guidance) and agentic (action proposals) in one.
Returns both a response text AND a list of proposed_actions that the UI can
Approve / Edit / Regenerate / Cancel before anything is executed.
"""
import json
from typing import Optional
from loguru import logger
from openai import AsyncOpenAI

from .config import settings
from .rag import search_protocols, search_templates, search_case_studies
from .similarity import get_similar_cases

_openai_client: Optional[AsyncOpenAI] = None

SYSTEM_PROMPT = """You are the SCS Youth Case Management Assistant, embedded in the Singapore Children's Society YOUTHHCARE dashboard.

You serve two roles simultaneously:
1. ADVISORY: Provide trauma-informed, protocol-compliant guidance to Youth Helpers and Admins based on SCS protocols, outreach templates, and case studies.
2. AGENTIC: Propose structured actions that the user must explicitly approve before they are executed. You NEVER execute actions yourself — you only propose them.

CRITICAL RULES:
- You are advising trained case workers, not youth themselves.
- Always cite whether your advice comes from SCS protocols, outreach templates, or case studies.
- Use professional, clear language. No emojis unless illustrating a template.
- Never access or mention raw social media content (only AI-generated risk signals are available).
- All proposed actions go through explicit human approval — explicitly state this.
- If you propose an action, include it in the `proposed_actions` JSON at the end of your response.

PROPOSED ACTIONS FORMAT:
At the end of your response, include a JSON block (and ONLY this JSON, no surrounding text after it):
<ACTIONS>
[
  {
    "action_type": "add_checklist_item | update_checklist_item_status | add_case_note | schedule_followup | update_case_status | update_priority | request_reassignment | assign_case",
    "description": "One-sentence human-readable description of what this action will do",
    "payload": { ... action-specific fields ... }
  }
]
</ACTIONS>

If no actions are proposed, end with: <ACTIONS>[]</ACTIONS>

CONTEXT AVAILABLE:
- Relevant protocol excerpts will be provided in [PROTOCOLS]
- Relevant outreach templates will be provided in [TEMPLATES]
- Relevant case study excerpts will be provided in [CASE STUDIES]
- Similar cases will be provided in [SIMILAR CASES] if available
- The current case context (if attached) will be in [CASE CONTEXT]
"""


def _build_context_block(
    query: str,
    category: Optional[str],
    case_context: Optional[dict],
    similar_cases: list[dict],
) -> str:
    blocks = []

    # RAG retrieval
    protocol_chunks = search_protocols(query, n_results=3)
    template_chunks = search_templates(query, n_results=2)
    study_chunks = search_case_studies(query, n_results=2)

    if protocol_chunks:
        blocks.append("[PROTOCOLS]\n" + "\n---\n".join(protocol_chunks))
    if template_chunks:
        blocks.append("[TEMPLATES]\n" + "\n---\n".join(template_chunks))
    if study_chunks:
        blocks.append("[CASE STUDIES]\n" + "\n---\n".join(study_chunks))

    if case_context:
        signals = case_context.get("explanation_signals", {})
        if isinstance(signals, str):
            try:
                signals = json.loads(signals)
            except Exception:
                signals = {}
        blocks.append(
            f"[CASE CONTEXT]\n"
            f"Case ID: {case_context.get('case_id')}\n"
            f"Category: {case_context.get('category')}\n"
            f"Risk Score: {case_context.get('risk_score')}/5 ({case_context.get('priority', 'medium')} priority)\n"
            f"Status: {case_context.get('status')}\n"
            f"Assigned To: {case_context.get('assigned_to', 'unassigned')}\n"
            f"Risk Summary: {signals.get('risk_summary', 'N/A')}\n"
            f"Risk Indicators: {json.dumps(signals.get('risk_indicators', []))}\n"
            f"Last Signal: {case_context.get('created_at')}\n"
            f"Prior Signal: {case_context.get('last_signal_at', 'N/A')}"
        )

    if similar_cases:
        sim_text = "\n".join(
            f"- {s['case_id']} | Cat: {s['category']} | Risk: {s['risk_score']}/5 | "
            f"Escalated: {'Yes' if s['escalation_flag'] else 'No'} | Sim: {s['similarity_score']:.2f}"
            for s in similar_cases
        )
        blocks.append(f"[SIMILAR CASES (top {len(similar_cases)})\n{sim_text}")

    return "\n\n".join(blocks)


def _parse_actions(text: str) -> tuple[str, list[dict]]:
    """Extract proposed_actions from <ACTIONS>...</ACTIONS> and return cleaned text + actions."""
    import re
    pattern = r"<ACTIONS>(.*?)</ACTIONS>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return text.strip(), []

    actions_json = match.group(1).strip()
    clean_text = text[: match.start()].strip()

    try:
        actions = json.loads(actions_json)
        if not isinstance(actions, list):
            actions = []
    except Exception as e:
        logger.warning(f"Failed to parse actions JSON: {e}")
        actions = []

    return clean_text, actions


async def chat(
    messages: list[dict],
    case_context: Optional[dict] = None,
    user_id: str = "unknown",
    user_role: str = "Youth Helper",
) -> dict:
    """
    Main chat entrypoint.
    Returns: { response_text: str, proposed_actions: list[dict] }
    """
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-placeholder"):
        # Graceful fallback without LLM
        return _fallback_response(messages, case_context)

    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Build user query from last message
    last_user_msg = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    # Get similar cases if case context provided
    similar_cases: list[dict] = []
    if case_context:
        case_id = case_context.get("case_id")
        if case_id:
            try:
                similar_cases = await get_similar_cases(case_id, top_k=5)
            except Exception as e:
                logger.warning(f"Similar cases fetch failed: {e}")

    context_block = _build_context_block(
        last_user_msg,
        case_context.get("category") if case_context else None,
        case_context,
        similar_cases,
    )

    # Build message history for OpenAI
    openai_messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context_block},
        {"role": "system", "content": f"Current user: {user_id} (role: {user_role})"},
    ]
    # Convert conversation history
    for m in messages:
        role = m.get("role", "user")
        if role in ("user", "assistant"):
            openai_messages.append({"role": role, "content": m["content"]})

    try:
        response = await _openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=openai_messages,
            temperature=0.3,
            max_tokens=1200,
        )
        raw_text = response.choices[0].message.content or ""
        response_text, proposed_actions = _parse_actions(raw_text)
        return {
            "response_text": response_text,
            "proposed_actions": proposed_actions,
            "similar_cases": similar_cases,
        }
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        return {
            "response_text": (
                "I'm unable to connect to the AI service right now. "
                "Please review the SCS protocols directly or contact your team lead."
            ),
            "proposed_actions": [],
            "similar_cases": similar_cases,
        }


def _fallback_response(messages: list[dict], case_context: Optional[dict]) -> dict:
    """Static fallback when OpenAI key is not configured."""
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    lower = last.lower()

    protocol_matches = search_protocols(last, n_results=2)
    template_matches = search_templates(last, n_results=1)

    intro = ""
    if case_context:
        intro = (
            f"Reviewing case {case_context.get('case_id')} "
            f"({case_context.get('category')}, Risk {case_context.get('risk_score')}/5):\n\n"
        )

    if "escalat" in lower:
        text = (
            intro
            + "**Escalation criteria (SCS Protocol):**\n\n"
            "Escalate immediately if any apply:\n"
            "- Youth expresses intent to self-harm or harm others\n"
            "- Youth mentions feeling unsafe at home\n"
            "- Risk score 4+ with no response within 48 hours\n"
            "- Multiple high-risk signals across platforms\n"
            "- Youth under 14 with any form of abuse\n\n"
            "*When in doubt, escalate. Better safe than sorry.*"
        )
        actions = [
            {
                "action_type": "update_case_status",
                "description": "Mark case as 'In Review' to flag for senior review",
                "payload": {"status": "in_review"},
            }
        ]
    elif "outreach" in lower or "message" in lower or "template" in lower:
        text = (
            intro
            + "**Recommended outreach approach:**\n\n"
            + (template_matches[0] if template_matches else
               "Use a warm, low-pressure message. Keep the first contact brief (2–3 sentences). "
               "Acknowledge feelings without mentioning how you detected the signals.")
        )
        actions = []
    elif "follow" in lower:
        text = (
            intro
            + "**Follow-up timelines (SCS Protocol):**\n\n"
            "- Critical (5): 2h → 24h → 48h → 72h\n"
            "- High (4): 6h → 48h → 72h → 1 week\n"
            "- Medium (3): 24h → 3 days → 1 week\n"
            "- Low-Med (2): 48h → 1 week → 2 weeks\n"
            "- Low (1): 1 week → 2 weeks → monthly"
        )
        actions = [
            {
                "action_type": "schedule_followup",
                "description": "Schedule a follow-up for this case",
                "payload": {"note": "Follow-up as per SCS protocol"},
            }
        ]
    elif "bully" in lower:
        text = (
            intro
            + "**Approaching bullying cases:**\n\n"
            + (protocol_matches[0] if protocol_matches else
               "1. Assess severity — single incident or repeated pattern?\n"
               "2. Do not confront the perpetrator directly.\n"
               "3. Reach out with warmth — non-judgmental, acknowledge feelings.\n"
               "4. Document everything in the checklist.\n"
               "5. Coordinate with school liaison if school-based.")
        )
        actions = []
    elif "resource" in lower:
        text = (
            intro
            + "**Crisis resources:**\n\n"
            "- Samaritans of Singapore: 1800-221-4444 (24/7)\n"
            "- IMH Emergency: 6389 2222\n"
            "- CHAT (youth mental health): 6493 6500\n"
            "- SCS School Liaison Programme\n"
            "- Family Service Centres (FSC)\n\n"
            "*Always check with your team lead before sharing external resources.*"
        )
        actions = []
    else:
        text = (
            intro
            + "Based on SCS protocols, I recommend reviewing the case signals carefully "
            "before deciding on next steps. All outreach decisions are yours — I'm here "
            "to guide, not to act. Would you like help with a specific aspect of this case?"
            + (f"\n\n**Relevant protocol context:**\n{protocol_matches[0]}" if protocol_matches else "")
        )
        actions = []

    return {
        "response_text": text,
        "proposed_actions": actions,
        "similar_cases": [],
    }
