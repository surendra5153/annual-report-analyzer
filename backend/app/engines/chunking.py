"""
Adaptive chunking engine.
Produces two chunk sets from an ingested document:
  - QA chunks   : larger overlapping windows for retrieval / question answering
  - Extract chunks: smaller precise windows for KPI / number extraction
"""
from typing import List, Dict, Any
from dataclasses import dataclass

from app.core.config import settings
from app.engines.ingestion import IngestedDocument


@dataclass
class Chunk:
    chunk_id: str
    filing_id: str
    text: str
    page_number: int
    chunk_type: str        # "qa" | "extract"
    metadata: Dict[str, Any]


def _sliding_window(
    text: str,
    window_size: int,
    overlap: int,
    page_number: int,
    filing_id: str,
    chunk_type: str,
) -> List[Chunk]:
    """Split text with a sliding window, returning Chunk objects."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + window_size
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    chunk_id=f"{filing_id}_{chunk_type}_p{page_number}_{idx}",
                    filing_id=filing_id,
                    text=chunk_text,
                    page_number=page_number,
                    chunk_type=chunk_type,
                    metadata={"page": page_number, "start_char": start, "end_char": end},
                )
            )
        start += window_size - overlap
        idx += 1
    return chunks


def chunk_document(doc: IngestedDocument, filing_id: str) -> Dict[str, List[Chunk]]:
    """
    Chunk an ingested document into QA and extraction sets.

    Returns:
        {"qa": [...], "extract": [...]}
    """
    qa_chunks: List[Chunk] = []
    extract_chunks: List[Chunk] = []

    for page in doc.pages:
        text = page.text.strip()
        if not text:
            continue

        # QA chunks: larger overlapping windows
        qa_chunks.extend(
            _sliding_window(
                text,
                window_size=settings.qa_chunk_size,
                overlap=settings.qa_chunk_overlap,
                page_number=page.page_number,
                filing_id=filing_id,
                chunk_type="qa",
            )
        )

        # Extract chunks: small precise windows
        extract_chunks.extend(
            _sliding_window(
                text,
                window_size=settings.extraction_chunk_size,
                overlap=settings.extraction_chunk_overlap,
                page_number=page.page_number,
                filing_id=filing_id,
                chunk_type="extract",
            )
        )

        # Also add table text to extraction chunks
        for t_idx, table in enumerate(page.tables):
            table_text = _table_to_text(table)
            if table_text.strip():
                extract_chunks.append(
                    Chunk(
                        chunk_id=f"{filing_id}_table_p{page.page_number}_{t_idx}",
                        filing_id=filing_id,
                        text=table_text,
                        page_number=page.page_number,
                        chunk_type="extract",
                        metadata={"page": page.page_number, "is_table": True, "table_index": t_idx},
                    )
                )

        # Add chart descriptions to QA chunks
        for c_idx, desc in enumerate(page.chart_descriptions):
            if desc.strip():
                qa_chunks.append(
                    Chunk(
                        chunk_id=f"{filing_id}_chart_p{page.page_number}_{c_idx}",
                        filing_id=filing_id,
                        text=f"[Chart description, page {page.page_number}]: {desc}",
                        page_number=page.page_number,
                        chunk_type="qa",
                        metadata={"page": page.page_number, "is_chart": True},
                    )
                )

    return {"qa": qa_chunks, "extract": extract_chunks}


def _table_to_text(table: List[List]) -> str:
    """Convert a pdfplumber table (list of rows) to plain text."""
    lines = []
    for row in table:
        cleaned = [str(cell).strip() if cell is not None else "" for cell in row]
        lines.append(" | ".join(cleaned))
    return "\n".join(lines)
