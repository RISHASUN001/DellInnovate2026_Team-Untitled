import os
from typing import List, Dict
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import re

class RAGSystem:
    def __init__(self, docs_path: str = "./docs", chroma_path: str = "../data/chromadb"):
        self.docs_path = docs_path
        self.chroma_path = chroma_path
        
        # Initialize sentence transformer
        print("Loading sentence transformer model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB
        print(f"Connecting to ChromaDB at {chroma_path}...")
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="scs_protocols",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"✓ ChromaDB ready. Collection has {self.collection.count()} documents.")
        
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
    
    def ingest_documents(self):
        """Ingest all documents from docs folder into ChromaDB"""
        print("Starting document ingestion...")
        
        # Check if already ingested
        if self.collection.count() > 0:
            print(f"Collection already has {self.collection.count()} documents. Skipping ingestion.")
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
        
        print(f"Generated {len(all_chunks)} chunks from {len(os.listdir(self.docs_path))} documents")
        
        # Generate embeddings
        print("Generating embeddings...")
        embeddings = self.embedding_model.encode(all_chunks, show_progress_bar=True).tolist()
        
        # Add to ChromaDB
        print("Adding to ChromaDB...")
        self.collection.add(
            embeddings=embeddings,
            documents=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids
        )
        
        print(f"✓ Ingestion complete! Added {len(all_chunks)} chunks to ChromaDB")
    
    def retrieve(self, query: str, n_results: int = 5) -> List[Dict]:
        """Retrieve relevant chunks for a query"""
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])[0].tolist()
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None
            })
        
        return formatted_results