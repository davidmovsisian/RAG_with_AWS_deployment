import os
from typing import List


class TextChunker:
    def __init__(self):
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.max_chunk_size = int(os.getenv("MAX_CHUNK_SIZE", "1500"))
        print(
            f"TextChunker initialized (chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, max={self.max_chunk_size})"
        )

    def chunk_text(self, text: str) -> List[str]:
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
        sentence_endings = ".!?"
        # Search backwards from position to find a sentence end
        for i in range(position, max(position - self.chunk_overlap, 0), -1):
            if text[i] in sentence_endings:
                return i + 1
        # Fall back to the original position if no boundary found
        return position

    def _split_into_sentences(self, text: str) -> List[str]:
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
