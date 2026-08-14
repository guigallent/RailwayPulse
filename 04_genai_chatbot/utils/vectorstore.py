"""
RailPulse AI Co-Pilot - few-shot vectorstore.

Embeds the (question, sql) pairs from query_examples.py into a local
Chroma collection, and exposes a retrieval function that returns the most
similar examples to an incoming question, formatted for direct injection
into the SQL generation prompt.
"""

import os
import sys
import warnings
from pathlib import Path

# 1. Disable huggingface tokenizer parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 2. Ignore LangChain deprecation warnings without upgrading packages
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*LangChainDeprecationWarning.*")

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent

sys.path.insert(0, str(REPO_ROOT))

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from utils.query_examples import FEW_SHOT_EXAMPLES

# Persist DB at repo root level
CHROMA_PERSIST_DIR = str(REPO_ROOT / "chroma_few_shot_db")
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)


def build_vectorstore(force_rebuild: bool = False) -> Chroma:
    """Embed all few-shot examples and persist them to disk."""
    embeddings = _get_embeddings()

    if os.path.exists(CHROMA_PERSIST_DIR) and not force_rebuild:
        print(f"Vectorstore already exists at {CHROMA_PERSIST_DIR}, loading it as-is.")
        print("Pass force_rebuild=True (or delete the folder) to re-embed after editing examples.")
        return Chroma(persist_directory=CHROMA_PERSIST_DIR, embedding_function=embeddings)

    print(f"Embedding {len(FEW_SHOT_EXAMPLES)} examples with {EMBEDDING_MODEL_NAME}...")
    documents = [
        Document(page_content=ex["question"], metadata={"sql": ex["sql"]})
        for ex in FEW_SHOT_EXAMPLES
    ]

    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    print(f"Vectorstore built and persisted to {CHROMA_PERSIST_DIR}")
    return vectorstore


def load_vectorstore() -> Chroma:
    """Load the already-persisted vectorstore without re-embedding."""
    if not os.path.exists(CHROMA_PERSIST_DIR):
        raise RuntimeError(
            f"No vectorstore found at {CHROMA_PERSIST_DIR}. "
            "Run `python utils/vectorstore.py` first to build it."
        )
    return Chroma(persist_directory=CHROMA_PERSIST_DIR, embedding_function=_get_embeddings())


def get_similar_examples(question: str, k: int = 3) -> str:
    """Return top-k similar examples formatted as text for prompt injection."""
    vectorstore = load_vectorstore()
    results = vectorstore.similarity_search(question, k=k)

    blocks = []
    for i, doc in enumerate(results, start=1):
        blocks.append(
            f"Example {i}:\nQuestion: {doc.page_content}\nSQL: {doc.metadata['sql']}"
        )
    return "\n\n".join(blocks)


if __name__ == "__main__":
    build_vectorstore()

    test_question = "What station is the busiest in Brussels?"
    print(f"\nTest retrieval for: {test_question!r}\n")
    print(get_similar_examples(test_question, k=3))