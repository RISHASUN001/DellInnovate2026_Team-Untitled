import os
from typing import List, Dict
import chromadb
from chromadb.config import Settings
import re
from openai import OpenAI
from app.config import settings

class RAGSystem:
    def __init__(self, docs_path: str = "./docs", chroma_path: str = "../data/chromadb"):
        self.docs_path = docs_path
        self.chroma_path = chroma_path
        
        # Initialize OpenAI client for embeddings
        print("Initializing OpenAI embeddings client...")
        self.openai_client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
        self.embedding_model = settings.embedding_model
        
        # Initialize ChromaDB
        print(f"Connecting to ChromaDB at {chroma_path}...")
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="scs_protocols",
            metadata={"hnsw:space": "cosine"}
        )
        
        current_count = self.collection.count()
        print(f"✓ ChromaDB ready. Collection has {current_count} documents.")
        
        # Auto-ingest if collection is empty
        if current_count == 0:
            print("Collection is empty. Starting document ingestion...")
            self.ingest_documents()
        else:
            print(f"Collection already populated with {current_count} documents.")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
        
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks"""
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Add overlap
        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                # Add last sentences from previous chunk
                prev_sentences = chunks[i-1].split('.')[-3:]
                chunk = '. '.join(prev_sentences) + '. ' + chunk
            overlapped_chunks.append(chunk)
        
        return overlapped_chunks
    
    def ingest_documents(self, force_reingest: bool = False):
        """Ingest all documents from docs folder into ChromaDB"""
        print("Starting document ingestion...")
        
        # Check if already ingested
        if self.collection.count() > 0 and not force_reingest:
            print(f"Collection already has {self.collection.count()} documents. Skipping ingestion.")
            print("To re-ingest, call clear_and_reingest() instead.")
            return
        
        all_chunks = []
        all_metadatas = []
        all_ids = []
        
        doc_id = 0
        
        for filename in os.listdir(self.docs_path):
            if not filename.endswith('.txt'):
                continue
                
            filepath = os.path.join(self.docs_path, filename)
            print(f"Processing {filename}...")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract category from filename
            category = filename.replace('.txt', '').replace('_', ' ').title()
            
            # Chunk the document
            chunks = self.chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadatas.append({
                    'source': filename,
                    'category': category,
                    'chunk_id': i
                })
                all_ids.append(f"{filename}_{i}")
                doc_id += 1
        
        print(f"Generated {len(all_chunks)} chunks from {len([f for f in os.listdir(self.docs_path) if f.endswith('.txt')])} documents")
        
        # Generate embeddings using OpenAI API
        print("Generating embeddings using OpenAI API...")
        embeddings = []
        for i, chunk in enumerate(all_chunks):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(all_chunks)} embeddings generated...")
            embedding = self.generate_embedding(chunk)
            embeddings.append(embedding)
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Add to ChromaDB
        print("Adding to ChromaDB...")
        self.collection.add(
            embeddings=embeddings,
            documents=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids
        )
        
        print(f"✓ Ingestion complete! Added {len(all_chunks)} chunks to ChromaDB")
    
    def clear_and_reingest(self):
        """Clear the collection and reingest all documents"""
        print("\n⚠️  Clearing ChromaDB collection...")
        
        # Delete the collection
        try:
            self.chroma_client.delete_collection(name="scs_protocols")
            print("✓ Collection deleted")
        except Exception as e:
            print(f"Collection deletion note: {e}")
        
        # Recreate collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="scs_protocols",
            metadata={"hnsw:space": "cosine"}
        )
        print("✓ Collection recreated")
        
        # Force reingest
        self.ingest_documents(force_reingest=True)
    
    def retrieve(self, query: str, n_results: int = 5) -> List[Dict]:
        """Retrieve relevant chunks for a query"""
        # Generate query embedding using OpenAI API
        query_embedding = self.generate_embedding(query)
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return formatted_results