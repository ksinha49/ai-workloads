from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import nbformat
from pygments.lexers import guess_lexer_for_filename
from tree_sitter import Language, Parser
import tiktoken


@dataclass
class FileChunk:
    """A chunk of text produced by a chunker."""

    text: str
    start: int
    end: int
    metadata: Optional[dict] = None


class TextFileChunker:
    """Simple chunker for plain text using token counts."""

    def __init__(self, max_tokens: int, overlap: int = 0, encoding: str = "cl100k_base"):
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.tokenizer = tiktoken.get_encoding(encoding)

    def chunk(self, text: str) -> List[FileChunk]:
        tokens = self.tokenizer.encode(text)
        step = self.max_tokens - self.overlap
        if step <= 0:
            step = self.max_tokens
        chunks: List[FileChunk] = []
        for start in range(0, len(tokens), step):
            sub = tokens[start : start + self.max_tokens]
            chunk_text = self.tokenizer.decode(sub)
            chunks.append(FileChunk(chunk_text, start, start + len(sub)))
        return chunks


class CodeFileChunker(TextFileChunker):
    """Chunker for source code files using tree_sitter if available."""

    _parser_cache: dict[str, Parser] = {}

    def __init__(self, max_tokens: int, overlap: int = 0, language: str | None = None):
        super().__init__(max_tokens, overlap)
        self.language = language

    def _get_parser(self, language: str) -> Parser:
        if language not in self._parser_cache:
            lang_path = Language.build_library(
                os.path.join("/tmp", "ts_lang.so"),
                [f"tree_sitter_languages/{language}"]
            )
            lang = Language(lang_path, language)
            parser = Parser()
            parser.set_language(lang)
            self._parser_cache[language] = parser
        return self._parser_cache[language]

    def chunk(self, text: str) -> List[FileChunk]:
        if not self.language:
            return super().chunk(text)
        try:
            parser = self._get_parser(self.language)
            tree = parser.parse(bytes(text, "utf8"))
            # naive split by top level node ranges
            chunks: List[FileChunk] = []
            for node in tree.root_node.children:
                part = text[node.start_byte : node.end_byte]
                chunks.extend(super().chunk(part))
            return chunks or super().chunk(text)
        except Exception:
            return super().chunk(text)


class IpynbFileChunker(TextFileChunker):
    """Chunker for Jupyter notebooks."""

    def chunk(self, text: str) -> List[FileChunk]:
        nb = nbformat.reads(text, as_version=4)
        joined: List[str] = []
        for cell in nb.cells:
            if cell.cell_type == "markdown":
                joined.append(cell.source)
            elif cell.cell_type == "code":
                joined.append(cell.source)
        return super().chunk("\n".join(joined))


class UniversalFileChunker:
    """Selects a chunker based on file name or provided strategy."""

    _CODE_EXT = {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".go",
    }

    def __init__(self, max_tokens: int, overlap: int = 0, default_strategy: str = "text"):
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.default_strategy = default_strategy
        self.text_chunker = TextFileChunker(max_tokens, overlap)

    def chunk(self, text: str, file_name: str | None = None) -> List[FileChunk]:
        strategy = self._choose_strategy(file_name)
        if strategy == "ipynb":
            return IpynbFileChunker(self.max_tokens, self.overlap).chunk(text)
        if strategy == "code":
            language = None
            if file_name:
                try:
                    lexer = guess_lexer_for_filename(file_name, text)
                    language = lexer.name.lower()
                except Exception:
                    pass
            return CodeFileChunker(self.max_tokens, self.overlap, language).chunk(text)
        return self.text_chunker.chunk(text)

    def _choose_strategy(self, file_name: str | None) -> str:
        if not file_name:
            return self.default_strategy
        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".ipynb":
            return "ipynb"
        if ext in self._CODE_EXT:
            return "code"
        return self.default_strategy
