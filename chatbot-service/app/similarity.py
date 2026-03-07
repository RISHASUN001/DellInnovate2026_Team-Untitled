"""
NetworkX-based case similarity graph.
Nodes = cases (by case_id).
Edges connect cases where:
  1. same category, AND
  2. |risk_score_delta| <= 1, AND
  3. escalation_flag matches OR frequency_metrics cosine similarity >= 0.6

get_similar_cases() returns top-5 most connected neighbours.
Graph is rebuilt from the case-service API on first request and cached in memory.
"""
import json
import asyncio
from typing import Optional
import httpx
import networkx as nx
import numpy as np
from loguru import logger

from .config import settings

_graph: Optional[nx.Graph] = None
_case_metadata: dict[str, dict] = {}   # case_id → {risk_score, category, escalation_flag, freq_vec}
_graph_lock = asyncio.Lock()


def _freq_metrics_to_vector(fm: dict) -> np.ndarray:
    """Normalised feature vector from frequency_metrics dict."""
    keys = ["post_rate_per_day", "story_rate_per_day", "dm_send_rate",
            "sentiment_score", "late_night_post_pct", "engagement_drop_pct"]
    vec = np.array([float(fm.get(k, 0.0)) for k in keys], dtype=float)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def _fetch_and_build_graph() -> None:
    """Fetch all cases + latest history entry and build the similarity graph."""
    global _graph, _case_metadata

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp_cases = await client.get(
                f"{settings.case_service_url}/cases/summary",
                headers={"X-User-Id": "system", "X-User-Role": "Admin"},
            )
            cases = resp_cases.json()
        except Exception as e:
            logger.error(f"Failed to fetch cases for similarity graph: {e}")
            return

        # Fetch latest history row for each case (for freq metrics + escalation flag)
        meta: dict[str, dict] = {}
        for case in cases:
            cid = case["case_id"]
            try:
                resp_hist = await client.get(
                    f"{settings.case_service_url}/cases/{cid}/history",
                    headers={"X-User-Id": "system", "X-User-Role": "Admin"},
                )
                history = resp_hist.json()
                latest = history[-1] if history else {}
            except Exception:
                latest = {}

            freq_metrics = latest.get("frequency_metrics", {})
            if isinstance(freq_metrics, str):
                try:
                    freq_metrics = json.loads(freq_metrics)
                except Exception:
                    freq_metrics = {}

            meta[cid] = {
                "risk_score": case["risk_score"],
                "category": case["category"],
                "escalation_flag": latest.get("escalation_flag", 0),
                "freq_vec": _freq_metrics_to_vector(freq_metrics),
            }

    G = nx.Graph()
    case_ids = list(meta.keys())
    G.add_nodes_from(case_ids)

    for i in range(len(case_ids)):
        for j in range(i + 1, len(case_ids)):
            a_id, b_id = case_ids[i], case_ids[j]
            a, b = meta[a_id], meta[b_id]

            # Criterion 1: same category
            if a["category"] != b["category"]:
                continue

            # Criterion 2: risk score delta <= 1
            risk_delta = abs(a["risk_score"] - b["risk_score"])
            if risk_delta > 1:
                continue

            # Criterion 3: escalation match OR freq cosine >= 0.6
            escalation_match = a["escalation_flag"] == b["escalation_flag"]
            cosine_sim = _cosine_similarity(a["freq_vec"], b["freq_vec"])

            if escalation_match or cosine_sim >= 0.6:
                weight = round(cosine_sim, 3)
                G.add_edge(a_id, b_id, weight=weight)

    _graph = G
    _case_metadata = meta
    logger.info(
        f"Similarity graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )


async def get_similar_cases(case_id: str, top_k: int = 5) -> list[dict]:
    """Return top_k similar cases to the given case_id."""
    global _graph

    async with _graph_lock:
        if _graph is None:
            await _fetch_and_build_graph()

    if _graph is None or case_id not in _graph:
        return []

    neighbours = list(_graph.neighbors(case_id))
    # Sort by edge weight descending
    scored = sorted(
        [
            {
                "case_id": n,
                "similarity_score": _graph[case_id][n].get("weight", 0.0),
                "category": _case_metadata.get(n, {}).get("category", ""),
                "risk_score": _case_metadata.get(n, {}).get("risk_score", 0),
                "escalation_flag": _case_metadata.get(n, {}).get("escalation_flag", 0),
            }
            for n in neighbours
        ],
        key=lambda x: x["similarity_score"],
        reverse=True,
    )
    return scored[:top_k]


async def rebuild_graph() -> None:
    """Force rebuild the similarity graph (call after case updates)."""
    global _graph
    async with _graph_lock:
        _graph = None
        await _fetch_and_build_graph()
