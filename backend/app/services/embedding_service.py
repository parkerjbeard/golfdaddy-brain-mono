"""
Service for generating and managing embeddings for semantic search.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from datetime import datetime
import hashlib
import json

from openai import AsyncOpenAI
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from sqlalchemy.dialects.postgresql import insert

from app.config.settings import settings
from app.models.doc_embeddings import DocEmbedding, CodeContext
# Simple rate limiter for embeddings
class RateLimiter:
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def check(self):
        import time
        now = time.time()
        # Remove old calls
        self.calls = [t for t in self.calls if now - t < self.time_window]
        if len(self.calls) >= self.max_calls:
            raise Exception("Rate limit exceeded")
        self.calls.append(now)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing document embeddings."""
    
    def __init__(self):
        if settings.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            logger.warning("OpenAI API key not configured. Embedding service will have limited functionality.")
            self.client = None
        self.model = settings.EMBEDDING_MODEL or "text-embedding-ada-002"
        self.dimension = 1536  # Ada-002 dimensions
        self.rate_limiter = RateLimiter(
            max_calls=settings.EMBEDDING_RATE_LIMIT or 3000,
            time_window=60  # per minute
        )
        self._cache = {}  # Simple in-memory cache
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a given text."""
        if not text or not text.strip():
            return None
        
        if not self.client:
            logger.warning("OpenAI client not initialized. Cannot generate embeddings.")
            return None
        
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Rate limiting
            await self.rate_limiter.check()
            
            # Generate embedding
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            
            # Cache the result
            self._cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str]
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts efficiently."""
        if not self.client:
            logger.warning("OpenAI client not initialized. Cannot generate embeddings.")
            return [None] * len(texts)
        
        # OpenAI supports batch embeddings
        valid_texts = [t for t in texts if t and t.strip()]
        
        if not valid_texts:
            return [None] * len(texts)
        
        try:
            await self.rate_limiter.check()
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=valid_texts,
                encoding_format="float"
            )
            
            # Map back to original order
            embeddings = {t: emb.embedding for t, emb in zip(valid_texts, response.data)}
            
            return [
                embeddings.get(text) if text and text.strip() else None
                for text in texts
            ]
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)
    
    async def embed_document(
        self,
        db: AsyncSession,
        title: str,
        content: str,
        doc_type: str,
        repository: str,
        file_path: Optional[str] = None,
        document_id: Optional[str] = None,
        doc_approval_id: Optional[str] = None,
        doc_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DocEmbedding]:
        """Embed a document and store in database."""
        # Prepare text for embedding
        embed_text = f"{title}\n\n{content}"
        
        # Truncate if too long (token limit)
        if len(embed_text) > 8000:  # Rough character limit
            embed_text = embed_text[:8000] + "..."
        
        # Generate embedding
        embedding = await self.generate_embedding(embed_text)
        if not embedding:
            return None
        
        try:
            # Create or update embedding record
            stmt = insert(DocEmbedding).values(
                document_id=document_id,
                doc_approval_id=doc_approval_id,
                title=title,
                content=content[:5000],  # Store truncated content
                doc_type=doc_type,
                file_path=file_path,
                repository=repository,
                embedding=embedding,
                doc_metadata=doc_metadata or {}
            ).on_conflict_do_update(
                constraint='unique_doc_embedding',
                set_=dict(
                    title=title,
                    content=content[:5000],
                    embedding=embedding,
                    doc_metadata=doc_metadata or {},
                    updated_at=datetime.utcnow()
                )
            )
            
            result = await db.execute(stmt)
            await db.commit()
            
            # Get the created/updated record
            doc_embedding = await db.get(DocEmbedding, result.inserted_primary_key[0])
            
            logger.info(f"Embedded document: {title} in {repository}")
            return doc_embedding
            
        except Exception as e:
            logger.error(f"Error storing document embedding: {e}")
            await db.rollback()
            return None
    
    async def embed_code_context(
        self,
        db: AsyncSession,
        repository: str,
        file_path: str,
        code_content: str,
        analysis: Dict[str, Any]
    ) -> Optional[CodeContext]:
        """Embed code context for better understanding."""
        # Create context text from analysis
        context_parts = [
            f"File: {file_path}",
            f"Module: {analysis.get('module_name', 'unknown')}",
        ]
        
        if analysis.get('classes'):
            context_parts.append(f"Classes: {', '.join(analysis['classes'])}")
        
        if analysis.get('functions'):
            context_parts.append(f"Functions: {', '.join(analysis['functions'][:10])}")
        
        if analysis.get('imports'):
            context_parts.append(f"Imports: {', '.join(analysis['imports'][:10])}")
        
        if analysis.get('description'):
            context_parts.append(f"Description: {analysis['description']}")
        
        context_text = "\n".join(context_parts)
        
        # Add code snippet
        if len(code_content) > 2000:
            context_text += f"\n\nCode snippet:\n{code_content[:2000]}..."
        else:
            context_text += f"\n\nCode:\n{code_content}"
        
        # Generate embedding
        embedding = await self.generate_embedding(context_text)
        if not embedding:
            return None
        
        try:
            # Store context
            stmt = insert(CodeContext).values(
                repository=repository,
                file_path=file_path,
                module_name=analysis.get('module_name'),
                class_names=analysis.get('classes', []),
                function_names=analysis.get('functions', []),
                imports=analysis.get('imports', []),
                exports=analysis.get('exports', []),
                design_patterns=analysis.get('design_patterns', []),
                coding_style=analysis.get('coding_style', {}),
                dependencies=analysis.get('dependencies', []),
                dependents=analysis.get('dependents', []),
                related_issues=analysis.get('related_issues', []),
                related_prs=analysis.get('related_prs', []),
                complexity_score=analysis.get('complexity_score'),
                test_coverage=analysis.get('test_coverage'),
                last_modified=analysis.get('last_modified'),
                context_embedding=embedding,
                context_metadata=analysis.get('metadata', {})
            ).on_conflict_do_update(
                constraint='unique_code_context',
                set_=dict(
                    module_name=analysis.get('module_name'),
                    class_names=analysis.get('classes', []),
                    function_names=analysis.get('functions', []),
                    context_embedding=embedding,
                    updated_at=datetime.utcnow()
                )
            )
            
            result = await db.execute(stmt)
            await db.commit()
            
            return await db.get(CodeContext, result.inserted_primary_key[0])
            
        except Exception as e:
            logger.error(f"Error storing code context: {e}")
            await db.rollback()
            return None
    
    async def find_similar_documents(
        self,
        db: AsyncSession,
        query: str,
        repository: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[DocEmbedding, float]]:
        """Find documents similar to the query."""
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        if not query_embedding:
            return []
        
        # Use the PostgreSQL function for similarity search
        query_text = """
        SELECT * FROM find_similar_docs(
            :embedding::vector,
            :limit,
            :threshold
        )
        """
        
        if repository:
            query_text += " WHERE repository = :repository"
        
        try:
            result = await db.execute(
                query_text,
                {
                    "embedding": query_embedding,
                    "limit": limit,
                    "threshold": threshold,
                    "repository": repository
                }
            )
            
            rows = result.fetchall()
            
            # Fetch full DocEmbedding objects
            results = []
            for row in rows:
                doc = await db.get(DocEmbedding, row.id)
                if doc:
                    results.append((doc, row.similarity))
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar documents: {e}")
            return []
    
    async def find_related_code(
        self,
        db: AsyncSession,
        query: str,
        repository: str,
        limit: int = 5
    ) -> List[Tuple[CodeContext, float]]:
        """Find code files related to the query."""
        query_embedding = await self.generate_embedding(query)
        if not query_embedding:
            return []
        
        try:
            result = await db.execute(
                """
                SELECT * FROM find_related_code(
                    :embedding::vector,
                    :repository,
                    :limit
                )
                """,
                {
                    "embedding": query_embedding,
                    "repository": repository,
                    "limit": limit
                }
            )
            
            rows = result.fetchall()
            
            results = []
            for row in rows:
                context = await db.get(CodeContext, row.id)
                if context:
                    results.append((context, row.similarity))
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding related code: {e}")
            return []
    
    async def detect_duplicates(
        self,
        db: AsyncSession,
        title: str,
        content: str,
        repository: str,
        threshold: float = 0.85,
        exclude_id: Optional[str] = None
    ) -> List[DocEmbedding]:
        """Detect potential duplicate documents."""
        # Search for similar documents with high threshold
        similar = await self.find_similar_documents(
            db,
            f"{title}\n{content[:500]}",  # Use title and beginning of content
            repository,
            limit=10,
            threshold=threshold
        )
        
        # Filter out excluded ID and apply threshold
        return [
            doc for doc, score in similar 
            if score > threshold and (not exclude_id or doc.id != exclude_id)
        ]
    
    async def update_embeddings_for_repository(
        self,
        db: AsyncSession,
        repository: str,
        force: bool = False
    ) -> int:
        """Update all embeddings for a repository."""
        # Get all documents without embeddings or force update
        stmt = select(DocEmbedding).where(
            DocEmbedding.repository == repository
        )
        
        if not force:
            stmt = stmt.where(DocEmbedding.embedding == None)
        
        result = await db.execute(stmt)
        documents = result.scalars().all()
        
        updated = 0
        for doc in documents:
            embed_text = f"{doc.title}\n\n{doc.content}"
            embedding = await self.generate_embedding(embed_text)
            
            if embedding:
                doc.embedding = embedding
                doc.updated_at = datetime.utcnow()
                updated += 1
        
        if updated > 0:
            await db.commit()
            logger.info(f"Updated {updated} embeddings for {repository}")
        
        return updated
    
    def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def create_or_update_embedding(
        self,
        db: AsyncSession,
        document_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DocEmbedding]:
        """Create or update a document embedding (wrapper for embed_document)."""
        # This is a wrapper method to match test expectations
        return await self.embed_document(
            db=db,
            title=title,
            content=content,
            doc_type=metadata.get('doc_type', 'general') if metadata else 'general',
            repository=metadata.get('repository', 'default') if metadata else 'default',
            document_id=document_id,
            doc_metadata=metadata
        )
    
    async def batch_create_embeddings(
        self,
        db: AsyncSession,
        documents: List[Dict[str, Any]]
    ) -> List[Optional[DocEmbedding]]:
        """Batch create embeddings for multiple documents."""
        results = []
        
        for doc in documents:
            try:
                embedding = await self.create_or_update_embedding(
                    db=db,
                    document_id=doc.get('document_id'),
                    title=doc.get('title', ''),
                    content=doc.get('content', ''),
                    metadata=doc.get('metadata', {})
                )
                results.append(embedding)
            except Exception as e:
                logger.error(f"Error creating embedding for document {doc.get('document_id')}: {e}")
                results.append(None)
        
        return results
    
    async def search_code_context(
        self,
        db: AsyncSession,
        query: str,
        repository: str,
        limit: int = 5
    ) -> List[Tuple[CodeContext, float]]:
        """Search for code context (wrapper for find_related_code)."""
        return await self.find_related_code(db, query, repository, limit)
    
    async def update_code_context_embedding(
        self,
        db: AsyncSession,
        repository: str,
        file_path: str,
        analysis: Dict[str, Any]
    ) -> Optional[CodeContext]:
        """Update code context embedding (wrapper for embed_code_context)."""
        # Get the code content from analysis or fetch it
        code_content = analysis.get('code_content', '')
        return await self.embed_code_context(
            db=db,
            repository=repository,
            file_path=file_path,
            code_content=code_content,
            analysis=analysis
        )