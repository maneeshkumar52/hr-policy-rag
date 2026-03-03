"""Recursive text chunker for HR document indexing."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DocumentChunk:
    content: str
    source_file: str
    title: str
    chunk_index: int
    section_heading: Optional[str] = None
    category: str = "hr_policy"
    clearance_level: int = 1


class RecursiveChunker:
    """Splits documents recursively on paragraph then sentence boundaries."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " "]

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text]
        sep = separators[0]
        rest = separators[1:]
        parts = text.split(sep)
        chunks, current = [], ""
        for part in parts:
            if len(current) + len(part) + len(sep) <= self.chunk_size:
                current += (sep if current else "") + part
            else:
                if current:
                    chunks.append(current)
                if len(part) > self.chunk_size and rest:
                    chunks.extend(self._split(part, rest))
                else:
                    current = part
        if current:
            chunks.append(current)
        return chunks

    def chunk(self, text: str, source_file: str, title: str, clearance_level: int = 1) -> List[DocumentChunk]:
        raw = self._split(text, self.separators)
        result = []
        for i, chunk_text in enumerate(raw):
            if len(chunk_text.strip()) < 50:
                continue
            overlap = raw[i-1][-self.chunk_overlap:] if i > 0 else ""
            content = (overlap + "\n" + chunk_text).strip() if overlap else chunk_text.strip()
            result.append(DocumentChunk(
                content=content,
                source_file=source_file,
                title=title,
                chunk_index=i,
                clearance_level=clearance_level,
            ))
        return result
