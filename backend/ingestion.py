import os
import pdfplumber
from typing import List, Dict, Any

DATA_DIR = os.getenv("DATA_DIR", "./data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# 800 worked better than 500 or 1000 in our testing
# 500 was too small, the chunks were losing context
# 1000 was too big, the model was getting confused with too much info at once
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def save_upload(filename: str, content: bytes) -> str:
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    return path


def _table_to_markdown(table: List[List]) -> str:
    # pdfplumber gives tables as list of lists, like a 2D array
    # we convert to markdown so the LLM can actually read and understand it
    # if we leave tables as raw text they become one jumbled line, which is useless
    if not table or not table[0]:
        return ""
    header = table[0]
    md = "| " + " | ".join(str(c or "") for c in header) + " |\n"
    md += "| " + " | ".join("---" for _ in header) + " |\n"
    for row in table[1:]:
        md += "| " + " | ".join(str(c or "") for c in row) + " |\n"
    return md


def _chunk_text(text: str, page: int, filename: str, heading: str) -> List[Dict[str, Any]]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            # prepend the section heading so every chunk knows which section it
            # belongs to, otherwise later chunks of a long section lose context
            body = f"[{heading}]\n{chunk.strip()}" if heading else chunk.strip()
            chunks.append({
                "text": body,
                "metadata": {"filename": filename, "page": page, "type": "text"},
            })
        # overlap so that sentences cut at the boundary don't lose meaning
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _page_heading(page) -> str:
    # use the first non empty line of the page as the section heading
    # this is what ties a table to its project, eg "6B. Project Solis ..."
    raw = page.extract_text() or ""
    for line in raw.split("\n"):
        line = line.strip()
        if line:
            return line
    return ""


def _in_any_table(obj, table_bboxes) -> bool:
    # check if a word/char sits inside any detected table region
    # we use the centre point of the object so partial overlaps are handled cleanly
    cx = (obj["x0"] + obj["x1"]) / 2
    cy = (obj["top"] + obj["bottom"]) / 2
    for x0, top, x1, bottom in table_bboxes:
        if x0 <= cx <= x1 and top <= cy <= bottom:
            return True
    return False


def extract_chunks(pdf_path: str, filename: str) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # grab the section heading before anything else so we can tag chunks with it
            heading = _page_heading(page)

            # find tables first so we know which parts of the page are tables
            found_tables = page.find_tables()
            table_bboxes = [t.bbox for t in found_tables]

            # get the page text but remove anything that falls inside a table area
            # otherwise the same table comes twice - once as jumbled text and once
            # as clean markdown, and the jumbled one confuses the model badly
            if table_bboxes:
                text_only_page = page.filter(lambda obj: not _in_any_table(obj, table_bboxes))
                text = text_only_page.extract_text() or ""
            else:
                text = page.extract_text() or ""

            chunks.extend(_chunk_text(text, page_num, filename, heading))

            # now add each table once, as clean markdown
            # prepend the section heading so a standalone table like a budget table
            # still carries which project/section it belongs to, otherwise a table
            # of just numbers cannot be matched to a question about that project
            for t in found_tables:
                table_md = _table_to_markdown(t.extract())
                if table_md.strip():
                    body = f"[{heading}]\n{table_md}" if heading else table_md
                    chunks.append({
                        "text": body,
                        "metadata": {"filename": filename, "page": page_num, "type": "table"},
                    })

    return chunks
