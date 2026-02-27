"""
ChromaDB RAG manager.
On startup: reads doc files, chunks them, embeds with sentence-transformers,
and persists to ChromaDB. Re-uses existing embeddings if collection non-empty.
"""
import os
from pathlib import Path
from typing import Optional
from loguru import logger

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from .config import settings

# ─── ChromaDB client (module-level, initialised on startup) ─────────────────
_chroma_client: Optional[chromadb.PersistentClient] = None
_embedder: Optional[SentenceTransformer] = None

COLLECTIONS = {
    "protocols": "docs/protocols.txt",
    "templates": "docs/outreach_templates.txt",
    "case_studies": "docs/case_studies.txt",
}

CHUNK_SIZE = 400  # characters
CHUNK_OVERLAP = 40


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        # Try to end at a sentence boundary
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break
    return chunks


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        logger.info(f"Loading sentence-transformer: {settings.embedding_model}")
        _embedder = SentenceTransformer(settings.embedding_model)
    return _embedder


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


async def ingest_documents() -> None:
    """Chunk, embed, and store all protocol/template/case-study documents."""
    client = get_chroma_client()
    embedder = _get_embedder()

    docs_base = Path(settings.docs_dir)

    for collection_name, rel_path in COLLECTIONS.items():
        doc_path = docs_base / Path(rel_path).name
        if not doc_path.exists():
            logger.warning(f"Document not found: {doc_path}")
            continue

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Skip if already populated
        if collection.count() > 0:
            logger.info(f"Collection '{collection_name}' already has {collection.count()} chunks — skipping ingest.")
            continue

        text = doc_path.read_text(encoding="utf-8")
        chunks = _chunk_text(text)
        logger.info(f"Ingesting '{collection_name}': {len(chunks)} chunks from {doc_path.name}")

        embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()

        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]
            batch_ids = [f"{collection_name}_{i + j}" for j in range(len(batch_chunks))]
            collection.add(
                documents=batch_chunks,
                embeddings=batch_embeddings,
                ids=batch_ids,
            )

        logger.info(f"Collection '{collection_name}' ingested: {collection.count()} chunks stored.")


def search_rag(query: str, collection_name: str, n_results: int = 4) -> list[str]:
    """Return top n_results relevant chunks from the specified collection."""
    client = get_chroma_client()
    embedder = _get_embedder()

    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    query_embedding = embedder.encode([query])[0].tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count() or 1),
    )
    return results.get("documents", [[]])[0]


def search_protocols(query: str, n_results: int = 4) -> list[str]:
    return search_rag(query, "protocols", n_results)


def search_templates(query: str, n_results: int = 3) -> list[str]:
    return search_rag(query, "templates", n_results)


def search_case_studies(query: str, n_results: int = 3) -> list[str]:
    return search_rag(query, "case_studies", n_results)
