"""
FAQ ingestion script for RAG.

Ingests client FAQ Q&A pairs into ChromaDB as atomic documents (no chunking).
Each FAQ becomes one document with full question + answer as content.
Sits alongside the already-ingested website page documents.

Usage:
    python -m agents.chatbot.ingest_faqs                    # Ingest FAQs
    python -m agents.chatbot.ingest_faqs --clear-existing   # Remove old FAQ docs first
"""

import json
import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from agents.chatbot.config import chatbot_settings

logger = logging.getLogger(__name__)

# Default path to FAQ data file
DEFAULT_FAQ_PATH = Path(__file__).parent / "data" / "faqs.json"


def load_faqs(filepath: str = None) -> list[dict]:
    """Load FAQ entries from JSON file."""
    path = filepath or str(DEFAULT_FAQ_PATH)
    with open(path) as f:
        return json.load(f)


def build_document_content(faq: dict) -> str:
    """
    Build the text content that gets embedded.

    Format: "Question: {q}\n\nAnswer: {a}"

    Uses answer_raw (markdown-formatted with links) so embeddings
    capture both user intent and answer semantics including link context.
    """
    # Use answer_raw if available, fall back to answer
    answer = faq.get("answer_raw") or faq["answer"]
    return f"Question: {faq['question']}\n\nAnswer: {answer}"


def build_metadata(faq: dict) -> dict:
    """
    Build Chroma metadata for a FAQ document.

    Uses answer_raw for original_answer so the LLM gets
    properly formatted markdown links in its context.
    """
    # Use answer_raw for the original answer (preserves markdown links)
    original_answer = faq.get("answer_raw") or faq["answer"]

    # Store links as JSON string (Chroma metadata must be str/int/float/bool)
    links_json = json.dumps(faq.get("links", []))

    return {
        "source_type": "faq",
        "source": "client_faq_mar2026",
        "intent": faq.get("intent", "other"),
        "category": faq.get("category", ""),
        "slug": faq["slug"],
        "escalation_type": faq.get("escalation_type", "none"),
        "has_links": bool(faq.get("links")),
        "links": links_json,
        "original_answer": original_answer,
    }


def ingest(filepath: str = None, clear_existing: bool = False):
    """
    Ingest FAQ entries into ChromaDB.

    Each FAQ becomes a single atomic document (no chunking).
    Documents are tagged with source_type='faq' to distinguish
    from website page documents.
    """
    faqs = load_faqs(filepath)
    logger.info(f"Loaded {len(faqs)} FAQs from {filepath or DEFAULT_FAQ_PATH}")

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma(
        persist_directory=chatbot_settings.chroma_path,
        embedding_function=embeddings,
    )

    # Optionally clear old FAQ documents before re-ingesting
    if clear_existing:
        try:
            existing = vectorstore.get(where={"source_type": "faq"})
            if existing and existing["ids"]:
                vectorstore.delete(ids=existing["ids"])
                count = len(existing["ids"])
                logger.info(f"Deleted {count} existing FAQ documents")
                print(f"🗑️  Deleted {count} existing FAQ documents")
        except Exception as e:
            logger.warning(f"Could not clear existing FAQs: {e}")

    # Build documents
    ids = []
    documents = []
    metadatas = []

    for faq in faqs:
        doc_id = f"faq-{faq['slug']}"
        content = build_document_content(faq)
        metadata = build_metadata(faq)

        ids.append(doc_id)
        documents.append(content)
        metadatas.append(metadata)

    # Upsert to Chroma
    vectorstore.add_texts(
        texts=documents,
        metadatas=metadatas,
        ids=ids,
    )

    # Log distribution by intent
    intent_counts = {}
    for m in metadatas:
        intent = m["intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    print(f"\n✅ Ingested {len(ids)} FAQ documents into Chroma")
    print(f"📊 Distribution by intent:")
    for intent, count in sorted(intent_counts.items()):
        print(f"   {intent}: {count}")

    logger.info(
        f"Ingested {len(ids)} FAQ documents into Chroma. "
        f"Distribution: {intent_counts}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Ingest FAQ Q&A pairs into ChromaDB"
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Path to FAQ JSON file (default: data/faqs.json)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Remove old FAQ docs before ingesting",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TGP Chatbot — FAQ Ingestion")
    print("=" * 60)

    ingest(filepath=args.file, clear_existing=args.clear_existing)


if __name__ == "__main__":
    main()
