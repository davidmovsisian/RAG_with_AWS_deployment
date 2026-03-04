"""
Text chunking utilities for splitting documents into overlapping chunks.
"""

import os
from typing import List


class TextChunker:
    """Splits text into overlapping chunks with optional sentence boundary awareness."""

    def __init__(self):
        """Load chunking configuration from environment variables."""
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE", "1500"))
        print(
            f"TextChunker initialized (chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, max={self.max_chunk_size})"
        )

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks, trying to break at sentence boundaries.

        Args:
            text: The input text to split.

        Returns:
            A list of text chunks.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to find a sentence boundary near the end of the chunk
            boundary = self._find_sentence_boundary(text, end)
            chunk = text[start:boundary]
            chunks.append(chunk)
            # Move start forward by chunk_size minus overlap
            start = boundary - self.chunk_overlap
            if start < 0 or start >= len(text):
                break

        print(f"Split text into {len(chunks)} chunks")
        return chunks

    def chunk_by_sentences(self, text: str) -> List[str]:
        """Split text strictly at sentence boundaries, grouping sentences into chunks.

        Args:
            text: The input text to split.

        Returns:
            A list of text chunks, each respecting sentence boundaries.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        sentences = self._split_into_sentences(text)
        if not sentences:
            return []

        chunks = []
        current_chunk = ""
        for sentence in sentences:
            if not current_chunk:
                current_chunk = sentence
            elif len(current_chunk) + len(sentence) + 1 <= self.max_chunk_size:
                current_chunk += " " + sentence
            else:
                chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        print(f"Split text into {len(chunks)} sentence-based chunks")
        return chunks

    def _find_sentence_boundary(self, text: str, position: int) -> int:
        """Find the nearest sentence boundary at or before position.

        Args:
            text: The full text.
            position: The target position.

        Returns:
            The index of the best boundary position.
        """
        sentence_endings = ".!?"
        # Search backwards from position to find a sentence end
        for i in range(position, max(position - self.chunk_overlap, 0), -1):
            if text[i] in sentence_endings:
                return i + 1
        # Fall back to the original position if no boundary found
        return position

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into individual sentences.

        Args:
            text: The text to split.

        Returns:
            A list of sentence strings.
        """
        sentences = []
        current = ""
        for char in text:
            current += char
            if char in ".!?" and len(current.strip()) > 0:
                sentence = current.strip()
                if sentence:
                    sentences.append(sentence)
                current = ""
        if current.strip():
            sentences.append(current.strip())
        return sentences
