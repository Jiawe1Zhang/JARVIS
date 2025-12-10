"""
Intent routing orchestrator for Jarvis (proposer -> reviewer).

Flow:
- Level 1 (keywords/regex, strict) proposes RAG/tool_sets.
- Level 3 (LLM reviewer) sees provisional decisions and can overwrite/clear.
Returns:
{
    "requires_rag": bool,
    "tool_sets": List[str],
    "specific_tools": List[str],  # optional, may be empty
    "reasoning": str,
    "source": "L1" | "L3" | "default",
}
"""

from typing import Dict, List, Optional, Set

from .level1_keywords import classify as level1_classify
from .level3_llm import LLMRouter


_llm_router = LLMRouter()

DEFAULT_RESULT: Dict[str, object] = {
    "requires_rag": True,
    "tool_sets": [],
    "specific_tools": [],
    "reasoning": "Fallback: default to RAG.",
    "source": "default",
}


def _normalize(result: Dict[str, object]) -> Dict[str, object]:
    tool_sets = result.get("tool_sets")
    if tool_sets is None:
        tool_sets = result.get("tool_domains") or []
    return {
        "requires_rag": bool(result.get("requires_rag")),
        "tool_sets": list(tool_sets or []),
        "specific_tools": list(result.get("specific_tools") or []),
        "reasoning": result.get("reasoning", ""),
        "source": result.get("source", ""),
    }


def get_intent(query: str, available_servers: Optional[List[Dict[str, object]]] = None) -> Dict[str, object]:
    """
    Proposer (L1/L2) -> Reviewer (L3). L3 can overwrite/clear proposals.
    Fast path: if L1 fully resolves (rag != None and tools != None), return immediately.
    """
    provisional_rag: Optional[bool] = None
    provisional_tools: Optional[List[str]] = None

    # Level 1: strict keywords
    l1 = level1_classify(query)
    if l1:
        l1["source"] = "L1"
        provisional_rag = l1.get("requires_rag")
        provisional_tools = l1.get("tool_sets")
        if provisional_rag is not None and provisional_tools is not None:
            return _normalize(l1)

    # Level 3: LLM reviewer with authority to overwrite/clear
    l3 = _llm_router.classify(
        query,
        provisional_rag=provisional_rag,
        provisional_tools=provisional_tools,
        available_servers=available_servers,
    )
    if l3:
        l3["source"] = "L3"
        return _normalize(l3)

    # Safety fallback
    return _normalize(DEFAULT_RESULT)


__all__ = ["get_intent"]
