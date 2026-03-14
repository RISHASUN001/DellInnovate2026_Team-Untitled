#!/usr/bin/env python3
"""
Script to clear and re-ingest ChromaDB with new embedding model.
Run this ONCE to populate ChromaDB with embeddings.

Usage:
    python3 clear_chromadb.py
"""

import sys
import os
from dotenv import load_dotenv

# Load .env file before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.rag import RAGSystem
from app.config import settings

def main():
    print("=" * 60)
    print("ChromaDB Population Script")
    print("=" * 60)
    print(f"\nDocs path: {settings.docs_dir}")
    print(f"ChromaDB path: {settings.chroma_persist_dir}")
    print(f"Embedding model: {settings.openrouter_embedding_model}")
    
    # Confirm action
    print("\n⚠️  This will populate ChromaDB with embeddings (run only ONCE).")
    response = input("Do you want to continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("❌ Operation cancelled.")
        return
    
    # Initialize RAG system (will auto-populate if empty)
    print("\n🔄 Initializing RAG system...")
    rag = RAGSystem(docs_path=settings.docs_dir, chroma_path=settings.chroma_persist_dir)
    
    # Show final status
    final_count = rag.collection.count()
    print(f"\n✅ SUCCESS! ChromaDB now contains {final_count} document chunks.")
    print("=" * 60)

if __name__ == "__main__":
    main()
