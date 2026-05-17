from __future__ import annotations

from pathlib import Path
from typing import List


class TextSourceReader:
    """Read text files and split them into chunks for LLM processing."""

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 120) -> None:
        """Initialize chunking parameters.

        Args:
            chunk_size: Maximum character count in each chunk.
            chunk_overlap: Character overlap between adjacent chunks.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be greater than or equal to 0.")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def read_text(self, source_path: Path) -> str:
        """Read a .txt source file from disk.

        Args:
            source_path: Path to the input text file.

        Returns:
            The UTF-8 text content.
        """
        if source_path.suffix.lower() != ".txt":
            raise ValueError("Only .txt files are supported.")
        return source_path.read_text(encoding="utf-8")

    def split_chunks(self, text: str) -> List[str]:
        """Split input text into chunks with overlap to preserve context."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._split_long_paragraph(paragraph))
                continue

            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            chunks.append(current)
            prefix = self._chunk_overlap(chunks[-1])
            candidate = f"{prefix}\n\n{paragraph}" if prefix else paragraph
            current = candidate if len(candidate) <= self.chunk_size else paragraph


        if current:
            chunks.append(current)

        return chunks

    def load_and_chunk(self, source_path: Path) -> List[str]:
        """Load a text source and return chunked segments."""
        text = self.read_text(source_path)
        return self.split_chunks(text)

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """Split a single paragraph that exceeds chunk_size."""
        pieces: List[str] = []
        step = self.chunk_size - self.chunk_overlap

        start = 0
        while start < len(paragraph):
            piece = paragraph[start : start + self.chunk_size].strip()
            if piece:
                pieces.append(piece)
            start += step

        return pieces

    def _chunk_overlap(self, chunk: str) -> str:
        """Return the overlap suffix for a completed chunk."""
        if self.chunk_overlap <= 0:
            return ""
        return chunk[-self.chunk_overlap :]
