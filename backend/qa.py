import os
import httpx
from typing import List, Dict, Any

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def _build_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        context_blocks.append(
            f"[Source {i}: {meta['filename']}, page {meta['page']}]\n{chunk['text']}"
        )
    context = "\n\n".join(context_blocks)

    # we tried system prompt approach first but small models like llama3.2:3b
    # follow instructions much better when everything is in one single message
    # system prompts were getting ignored half the time
    return (
        f"Use ONLY the document excerpts below to answer the question.\n"
        f"Do not use any outside knowledge.\n"
        f"First check if the excerpts actually contain information relevant to the question.\n"
        f"If the relevant information is not present in the excerpts, say exactly: "
        f"'I could not find this information in the uploaded documents.'\n"
        f"Do not guess or infer from unrelated content.\n"
        f"Never invent numbers, categories, or breakdowns that are not explicitly written in the excerpts.\n"
        f"If a breakdown or sub-categories are asked for but the excerpts only have a single total figure, "
        f"give that single figure and say a detailed breakdown is not available in the documents.\n"
        f"Every number you state must be copied exactly as it appears in the excerpts, do not calculate "
        f"or split numbers yourself.\n\n"
        f"Give a thorough and complete answer. Include ALL the relevant details that are present in the "
        f"excerpts - for example status or current phase, owners or people involved, scope, dates, "
        f"figures, and any related points. Do not leave out relevant information just to be short. "
        f"At the same time, do not add anything that is not in the excerpts.\n\n"
        f"Format your response using markdown:\n"
        f"- Start with a one line summary, then give the details\n"
        f"- Use bullet points or numbered lists for the details\n"
        f"- Use markdown tables (| col | col |) when presenting structured or tabular data\n"
        f"- Use **bold** for key terms\n\n"
        f"Document excerpts:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )


def answer(question: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = _build_prompt(question, chunks)

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            # temperature 0 so the model picks the most likely answer every time
            # instead of being creative, for factual Q&A we don't want randomness
            "options": {
                "temperature": 0,
                "top_p": 1,
                "num_ctx": 8192,
            },
        },
        timeout=120.0,
    )
    response.raise_for_status()
    answer_text = response.json()["response"]

    citations = [
        {"filename": c["metadata"]["filename"], "page": c["metadata"]["page"]}
        for c in chunks
    ]
    # remove duplicate page citations, same page can appear multiple times if it had many chunks
    seen = set()
    unique_citations = []
    for cit in citations:
        key = (cit["filename"], cit["page"])
        if key not in seen:
            seen.add(key)
            unique_citations.append(cit)

    return {"answer": answer_text, "citations": unique_citations}
