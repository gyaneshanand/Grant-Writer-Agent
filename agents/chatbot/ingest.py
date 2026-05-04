"""
Document ingestion script for RAG.

Fetches TGP website pages and stores them in ChromaDB for
product navigation queries.

Usage:
    python -m agents.chatbot.ingest           # Ingest documents
    python -m agents.chatbot.ingest --reset   # Clear and re-ingest
"""

import os
import argparse
import shutil
from dotenv import load_dotenv

load_dotenv()

# URLs to index (TGP website pages)
URLS_TO_INGEST = [
    "https://www.thegrantportal.com/pricing-and-plans",
    "https://www.thegrantportal.com/faqs",
    "https://www.thegrantportal.com/about-us",
    "https://www.thegrantportal.com/contact-us",
    "https://www.thegrantportal.com/hire-a-grant-writer",
    "https://www.thegrantportal.com/i-am-a-grant-provider",
    "https://www.thegrantportal.com/grant-writer-application",
    "https://www.thegrantportal.com/privacy-policy",
    "https://www.thegrantportal.com/cookie-policy",
    "https://www.thegrantportal.com/terms-service",
    "https://www.thegrantportal.com/terms-and-conditions-grant-writers",
    "https://blog.thegrantportal.com/",
    "https://www.thegrantportal.com/grants-for-nonprofits",
    "https://www.thegrantportal.com/grants-for-small-business",
    "https://www.thegrantportal.com/grants-for-individuals",
    "https://www.thegrantportal.com/irs-990-private-foundations/profile-search",
]


def get_chroma_path():
    """Get ChromaDB path from settings."""
    try:
        from agents.chatbot.config import chatbot_settings
        return chatbot_settings.chroma_path
    except Exception:
        # Fallback if settings can't be loaded
        return "agents/chatbot/data/chroma_db"


def load_documents():
    """Load documents from URLs."""
    from langchain_community.document_loaders import WebBaseLoader

    documents = []

    print(f"Loading {len(URLS_TO_INGEST)} URLs...")
    for url in URLS_TO_INGEST:
        try:
            print(f"  Loading: {url}")
            loader = WebBaseLoader(url)
            docs = loader.load()
            documents.extend(docs)
            print(f"    ✓ Loaded {len(docs)} document(s)")
        except Exception as e:
            print(f"    ✗ Error loading {url}: {e}")

    return documents


def clear_database(chroma_path: str):
    """Clear the existing ChromaDB data."""
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"✓ Cleared existing data at {chroma_path}")


def ingest():
    """Main ingestion function."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma

    chroma_path = get_chroma_path()

    print("=" * 60)
    print("TGP Chatbot - Document Ingestion")
    print("=" * 60)

    # Load documents
    print("\n📥 Loading documents...")
    documents = load_documents()

    if not documents:
        print("\n⚠️  No documents found to ingest.")
        return

    print(f"\n✓ Loaded {len(documents)} documents total.")

    # Split into chunks
    print("\n✂️  Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✓ Split into {len(chunks)} chunks.")

    # Clear existing data
    print(f"\n🗑️  Clearing existing database at {chroma_path}...")
    clear_database(chroma_path)

    # Create embeddings and store
    print("\n💾 Saving to ChromaDB...")
    Chroma.from_documents(
        documents=chunks,
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        persist_directory=chroma_path,
    )

    print(f"\n✅ Successfully saved {len(chunks)} chunks to {chroma_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents for TGP Chatbot RAG"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Only clear the database without re-ingesting",
    )
    args = parser.parse_args()

    if args.reset:
        chroma_path = get_chroma_path()
        print("✨ Clearing Database")
        clear_database(chroma_path)
    else:
        ingest()


if __name__ == "__main__":
    main()
