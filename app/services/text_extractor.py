from typing import Protocol


class TextExtractor(Protocol):
    def extract(self, content: bytes) -> str:
        """Extract text from binary document content."""
