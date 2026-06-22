import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder

DATA_DIR = os.getenv("DATA_DIR", "./data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
os.makedirs(CHROMA_DIR, exist_ok=True)

# tried all-MiniLM-L6-v2 first but bge-small gave slightly better results
# both are small enough to run on CPU without issues
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# small cross encoder to rerank, reads each chunk against the question properly
# vector search is fast but rough, this picks the actually relevant ones
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
COLLECTION_NAME = "documents"

# pull a wide net from chroma first
CANDIDATE_K = 20
# then keep only the best few after reranking, fewer but more accurate
# works better than dumping lots of chunks on a small model
TOP_K = 6

_embedder: SentenceTransformer = None
_reranker: CrossEncoder = None
_chroma_client: chromadb.PersistentClient = None
_collection = None


def _get_embedder() -> SentenceTransformer:
    # load once and reuse, loading every request would be very slow
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine similarity works better than euclidean for text
        )
    return _collection


def embed_and_store(chunks: List[Dict[str, Any]], filename: str) -> int:
    collection = _get_collection()
    embedder = _get_embedder()

    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    ids = [f"{filename}::page{c['metadata']['page']}::idx{i}" for i, c in enumerate(chunks)]

    embeddings = embedder.encode(texts, normalize_embeddings=True).tolist()
    # upsert instead of insert so re-uploading same file doesn't create duplicates
    collection.upsert(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
    return len(chunks)


def query(question: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    collection = _get_collection()
    embedder = _get_embedder()

    # step 1 - vector search to get a wide set of candidates (good recall)
    q_embedding = embedder.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=q_embedding, n_results=CANDIDATE_K)

    candidates = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        candidates.append({"text": doc, "metadata": meta})

    if not candidates:
        return []

    # step 2 - rerank candidates with the cross encoder for better precision
    # it scores how well each chunk actually answers the question
    reranker = _get_reranker()
    pairs = [(question, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_k]]


def delete_document(filename: str):
    collection = _get_collection()
    results = collection.get(where={"filename": filename})
    if results["ids"]:
        collection.delete(ids=results["ids"])
