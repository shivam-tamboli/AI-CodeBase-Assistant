import os
from pathlib import Path
from typing import List, Dict, Any

CODE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}

SKIP_DIRECTORIES: set = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    "ENV",
    ".env",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "vendor",
    "target",
}


def scan_directory(directory: str) -> List[Dict[str, Any]]:
    """Find all code files in directory
    
    Args:
        directory: Root directory to scan
        
    Returns:
        List of dicts with file path, language, and name
    """
    code_files: List[Dict[str, Any]] = []
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith('.')]
        
        for file in files:
            if file.startswith('.'):
                continue
                
            path = Path(file)
            extension = path.suffix.lower()
            
            if extension in CODE_EXTENSIONS:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, directory)
                
                code_files.append({
                    "path": full_path,
                    "relative_path": relative_path,
                    "name": file,
                    "extension": extension,
                    "language": CODE_EXTENSIONS[extension]
                })
    
    return code_files


def get_file_content(file_path: str) -> str:
    """Read file content with UTF-8 encoding
    
    Args:
        file_path: Path to file
        
    Returns:
        File content as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception:
            return ""
    except Exception:
        return ""


def is_supported_language(extension: str) -> bool:
    """Check if file extension is supported
    
    Args:
        extension: File extension (e.g., '.py')
        
    Returns:
        True if supported
    """
    return extension.lower() in CODE_EXTENSIONS


def get_language(extension: str) -> str:
    """Get language name for extension
    
    Args:
        extension: File extension (e.g., '.py')
        
    Returns:
        Language name (e.g., 'python')
    """
    return CODE_EXTENSIONS.get(extension.lower(), "unknown")
