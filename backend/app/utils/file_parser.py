"""
File parsing utilities
Extracts text from PDF, Markdown, and TXT files.
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
        Read a text file, auto-detecting the encoding if UTF-8 fails.
    
        Fallback chain:
    1.     1. try UTF-8 decoding
    2.     2. detect the encoding with charset_normalizer
    3.     3. fall back to chardet
    4.     4. last resort: UTF-8 + errors='replace'
    
    Args:
                file_path: file path
        
    Returns:
                The decoded text.
    """
    data = Path(file_path).read_bytes()
    
        # try UTF-8 first
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
        # try charset_normalizer detection
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
        # fall back to chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
        # last resort: UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """File parser."""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    
    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
                Check whether the file format is supported.
        
        Args:
                    file_path: file path
            
        Returns:
                    True when the format is supported.
        """
        suffix = Path(file_path).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
                Extract text from a file.
        
        Args:
                    file_path: file path
            
        Returns:
                    The extracted text.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        
        raise ValueError(f"Unhandled file format: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extract text from a PDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF required: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Extract text from Markdown, auto-detecting the encoding."""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """Extract text from TXT, auto-detecting the encoding."""
        return _read_text_with_fallback(file_path)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
                Extract text from multiple files and merge.
        
        Args:
                        file_paths: list of file paths
            
        Returns:
                        The merged text.
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Document {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Document {i}: {file_path} (extraction failed: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
            Split text into chunks.
    
    Args:
                    text: source text
                    chunk_size: chars per chunk
                    overlap: overlap chars
        
    Returns:
                    The chunk list.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
                # try splitting on sentence boundaries
        if end < len(text):
                    # find the nearest sentence terminator
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
                # the next chunk starts at the overlap position
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

