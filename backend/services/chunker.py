import tiktoken
from typing import List, Dict, Any, Optional
import ast

from backend.services.ast_parser import parse_python_file
from backend.services import treesitter_parser


class CodeChunker:
    """Intelligently chunks code for embedding"""
    
    def __init__(self, max_tokens: int = 1000, overlap: int = 100):
        self.max_tokens = max_tokens
        self.overlap = overlap
        try:
            self.encoder = tiktoken.encoding_for_model("text-embedding-3-small")
        except KeyError:
            self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        if not text:
            return 0
        return len(self.encoder.encode(text))
    
    def chunk_file(self, source: str, file_path: str = "") -> List[Dict[str, Any]]:
        """Chunk Python source code using AST
        
        Args:
            source: Python source code
            file_path: Optional file path for metadata
            
        Returns:
            List of chunks with content and metadata
        """
        if not source or not source.strip():
            return []
        
        metadata = parse_python_file(source)
        
        if metadata.get("error"):
            return []
        
        chunks = []
        
        imports_chunk = self._create_imports_chunk(source, metadata, file_path)
        if imports_chunk:
            chunks.append(imports_chunk)
        
        for func in metadata.get("functions", []):
            func_source = self._extract_lines(source, func["line_start"], func["line_end"])
            chunk = self._create_chunk(
                content=func_source,
                chunk_type="function",
                name=func["name"],
                start_line=func["line_start"],
                end_line=func["line_end"],
                file_path=file_path
            )
            chunks.append(chunk)
        
        for cls in metadata.get("classes", []):
            cls_source = self._extract_lines(source, cls["line_start"], cls["line_end"])
            chunk = self._create_chunk(
                content=cls_source,
                chunk_type="class",
                name=cls["name"],
                start_line=cls["line_start"],
                end_line=cls["line_end"],
                file_path=file_path
            )
            chunks.append(chunk)
        
        return self._split_large_chunks(chunks)
    
    def _create_imports_chunk(self, source: str, metadata: Dict[str, Any], file_path: str = "") -> Optional[Dict[str, Any]]:
        """Create a chunk for imports/header"""
        imports = metadata.get("imports", [])
        if not imports:
            return None
        
        import_lines = []
        for imp in imports:
            if imp.startswith("from "):
                import_lines.append(imp)
            else:
                import_lines.append(f"import {imp}")
        
        header = "\n".join(import_lines)
        
        return {
            "content": header,
            "chunk_type": "imports",
            "name": "__init__",
            "start_line": 1,
            "end_line": min(50, metadata.get("line_count", 0)),
            "file_path": file_path,
            "token_count": self.count_tokens(header)
        }
    
    def _extract_lines(self, source: str, start: int, end: int) -> str:
        """Extract specific lines from source"""
        if not source:
            return ""
        
        lines = source.split('\n')
        
        start_idx = max(0, start - 1)
        end_idx = min(len(lines), end)
        
        if start_idx >= end_idx:
            return ""
        
        return '\n'.join(lines[start_idx:end_idx])
    
    def _create_chunk(self, content: str, chunk_type: str, name: str,
                     start_line: int, end_line: int, file_path: str) -> Dict[str, Any]:
        """Create a chunk with metadata"""
        return {
            "content": content,
            "chunk_type": chunk_type,
            "name": name,
            "start_line": start_line,
            "end_line": end_line,
            "file_path": file_path,
            "token_count": self.count_tokens(content)
        }
    
    def _split_large_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split chunks that exceed token limit"""
        result = []
        
        for chunk in chunks:
            if chunk["token_count"] <= self.max_tokens:
                result.append(chunk)
            else:
                result.extend(self._split_by_tokens(chunk))
        
        return result
    
    def _split_by_tokens(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split a large chunk into smaller pieces with overlap"""
        pieces = []
        content = chunk["content"]
        lines = content.split('\n')
        
        current_piece = []
        current_tokens = 0
        piece_start_line = chunk["start_line"]
        
        for i, line in enumerate(lines):
            line_tokens = self.count_tokens(line + "\n")
            
            if current_tokens + line_tokens > self.max_tokens:
                if current_piece:
                    piece_end_line = chunk["start_line"] + i - 1
                    
                    pieces.append(self._create_chunk(
                        content="\n".join(current_piece),
                        chunk_type=chunk["chunk_type"],
                        name=chunk["name"],
                        start_line=piece_start_line,
                        end_line=piece_end_line,
                        file_path=chunk["file_path"]
                    ))
                    
                    overlap_lines = current_piece[-self.overlap:]
                    current_piece = overlap_lines + [line]
                    current_tokens = self.count_tokens("\n".join(current_piece))
                    piece_start_line = piece_end_line - len(overlap_lines) + 1
                else:
                    current_piece = [line]
                    current_tokens = line_tokens
                    piece_start_line = chunk["start_line"] + i
            else:
                current_piece.append(line)
                current_tokens += line_tokens
        
        if current_piece:
            pieces.append(self._create_chunk(
                content="\n".join(current_piece),
                chunk_type=chunk["chunk_type"],
                name=chunk["name"],
                start_line=piece_start_line,
                end_line=chunk["end_line"],
                file_path=chunk["file_path"]
            ))
        
        return pieces
    
    def chunk_file_multilang(
        self, source: str, file_path: str = "", language: str = "python"
    ) -> List[Dict[str, Any]]:
        """Chunk any supported language file using AST where possible.

        Dispatch order:
          1. Python  → existing `chunk_file` (Python ast module)
          2. Other   → tree-sitter AST; same chunk assembly as Python path
          3. Fallback → line-based chunking when tree-sitter is unavailable
        """
        if language == "python":
            return self.chunk_file(source, file_path)

        parsed = treesitter_parser.parse_file(source, language)
        if parsed is not None:
            return self._chunks_from_parsed(source, file_path, parsed)

        # Tree-sitter not available for this language — use line-based chunking
        return self._chunk_by_lines(source, file_path)

    def _chunks_from_parsed(
        self, source: str, file_path: str, parsed: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Assemble chunks from a treesitter_parser result dict."""
        chunks = []

        for func in parsed.get("functions", []):
            func_source = self._extract_lines(source, func["line_start"], func["line_end"])
            chunks.append(self._create_chunk(
                content=func_source,
                chunk_type="function",
                name=func["name"],
                start_line=func["line_start"],
                end_line=func["line_end"],
                file_path=file_path,
            ))

        for cls in parsed.get("classes", []):
            cls_source = self._extract_lines(source, cls["line_start"], cls["line_end"])
            chunks.append(self._create_chunk(
                content=cls_source,
                chunk_type="class",
                name=cls["name"],
                start_line=cls["line_start"],
                end_line=cls["line_end"],
                file_path=file_path,
            ))

        if not chunks:
            # No functions/classes found — chunk the whole file by lines
            return self._chunk_by_lines(source, file_path)

        return self._split_large_chunks(chunks)

    def _chunk_by_lines(self, source: str, file_path: str) -> List[Dict[str, Any]]:
        """Sliding-window line-based chunking for files without AST support."""
        if not source or not source.strip():
            return []

        lines = source.split("\n")
        chunks = []
        current_lines: List[str] = []
        current_tokens = 0
        start_line = 1

        for i, line in enumerate(lines, 1):
            line_tokens = self.count_tokens(line + "\n")

            if current_tokens + line_tokens > self.max_tokens and current_lines:
                chunks.append(self._create_chunk(
                    content="\n".join(current_lines),
                    chunk_type="code",
                    name="",
                    start_line=start_line,
                    end_line=i - 1,
                    file_path=file_path,
                ))
                # Build overlap by including lines from the end of the current
                # chunk until their cumulative token count reaches self.overlap.
                # This bounds overlap in tokens, not line count, so dense code
                # (e.g. 20 tokens/line) does not produce overlap larger than
                # the chunk itself.
                overlap: List[str] = []
                overlap_tokens = 0
                for prev_line in reversed(current_lines):
                    t = self.count_tokens(prev_line + "\n")
                    if overlap_tokens + t > self.overlap:
                        break
                    overlap.insert(0, prev_line)
                    overlap_tokens += t
                current_lines = overlap + [line]
                current_tokens = self.count_tokens("\n".join(current_lines))
                start_line = i - len(overlap)
            else:
                current_lines.append(line)
                current_tokens += line_tokens

        if current_lines:
            chunks.append(self._create_chunk(
                content="\n".join(current_lines),
                chunk_type="code",
                name="",
                start_line=start_line,
                end_line=len(lines),
                file_path=file_path,
            ))

        return chunks

    def chunk_directory(self, directory: str) -> List[Dict[str, Any]]:
        """Chunk all Python files in a directory
        
        Args:
            directory: Path to directory
            
        Returns:
            List of all chunks from all files
        """
        from backend.services.file_scanner import scan_directory, get_file_content
        
        all_chunks = []
        files = scan_directory(directory)
        
        for file_info in files:
            content = get_file_content(file_info["path"])
            if content:
                chunks = self.chunk_file_multilang(
                    content, file_info["relative_path"], file_info["language"]
                )
                for chunk in chunks:
                    chunk["repository_id"] = ""
                all_chunks.extend(chunks)
        
        return all_chunks
