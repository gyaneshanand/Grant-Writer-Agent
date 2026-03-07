"""
Modular vector store abstraction.

Supports ChromaDB (default) with ability to switch to Pinecone.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class VectorStoreProvider(ABC):
    """Abstract base class for vector store providers."""

    @abstractmethod
    def get_retriever(self, k: int = 4):
        """Return a LangChain retriever."""
        pass


class ChromaVectorStore(VectorStoreProvider):
    """ChromaDB vector store implementation."""

    def __init__(self, persist_directory: str):
        self.persist_directory = persist_directory
        self._vector_store = None

    def _ensure_initialized(self):
        if self._vector_store is None:
            from langchain_chroma import Chroma
            self._vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=OpenAIEmbeddings(),
            )
        return self._vector_store

    def get_retriever(self, k: int = 4):
        vs = self._ensure_initialized()
        return vs.as_retriever(search_kwargs={"k": k})

    def is_initialized(self) -> bool:
        """Check if the vector store has been populated."""
        return os.path.exists(self.persist_directory) and os.listdir(self.persist_directory)

    def similarity_search_with_score(
        self, query: str, k: int = 5, filter: dict = None
    ) -> list[tuple]:
        """
        Search with relevance scores and optional metadata filters.

        Returns list of (Document, score) tuples.
        Lower score = better match (Chroma uses L2 distance by default).
        """
        vs = self._ensure_initialized()
        kwargs = {"k": k}
        if filter:
            kwargs["filter"] = filter
        return vs.similarity_search_with_score(query, **kwargs)

    def search_faqs(
        self, query: str, intent: str, top_k: int = 5
    ) -> list[dict]:
        """
        Search FAQ documents filtered by intent.

        Used by account_support, eligibility_assessment,
        and application_guidance handlers.
        """
        results = self.similarity_search_with_score(
            query,
            k=top_k,
            filter={
                "$and": [
                    {"source_type": "faq"},
                    {"intent": intent},
                ]
            },
        )
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ]

    def search_all(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Broad search across all documents (FAQ + website).

        Used by product_navigation and fallback handlers
        where the question could match any source type.
        """
        results = self.similarity_search_with_score(query, k=top_k)
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ]


class PineconeVectorStore(VectorStoreProvider):
    """Pinecone vector store implementation (for future use)."""

    def __init__(self, api_key: str, index_name: str):
        self.api_key = api_key
        self.index_name = index_name
        self._vector_store = None

    def _ensure_initialized(self):
        if self._vector_store is None:
            from langchain_pinecone import PineconeVectorStore as LangchainPinecone
            from pinecone import Pinecone

            pc = Pinecone(api_key=self.api_key)
            index = pc.Index(self.index_name)

            self._vector_store = LangchainPinecone(
                index=index,
                embedding=OpenAIEmbeddings(),
                text_key="text",
            )
        return self._vector_store

    def get_retriever(self, k: int = 4):
        vs = self._ensure_initialized()
        return vs.as_retriever(search_kwargs={"k": k})


# ── Factory ────────────────────────────────────────────────

_vector_store: Optional[VectorStoreProvider] = None


def get_vector_store() -> VectorStoreProvider:
    """
    Get the configured vector store provider.
    Returns ChromaDB by default, Pinecone if configured.
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    from agents.chatbot.config import chatbot_settings

    if chatbot_settings.vector_store_provider == "pinecone":
        if not chatbot_settings.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY required when using Pinecone")

        logger.info(f"Using Pinecone vector store: {chatbot_settings.pinecone_index_name}")
        _vector_store = PineconeVectorStore(
            api_key=chatbot_settings.pinecone_api_key,
            index_name=chatbot_settings.pinecone_index_name,
        )
    else:
        # Default to ChromaDB
        logger.info(f"Using ChromaDB vector store: {chatbot_settings.chroma_path}")
        _vector_store = ChromaVectorStore(
            persist_directory=chatbot_settings.chroma_path,
        )

    return _vector_store


def get_retriever(k: int = 4):
    """Convenience function to get a retriever from the configured vector store."""
    return get_vector_store().get_retriever(k=k)
