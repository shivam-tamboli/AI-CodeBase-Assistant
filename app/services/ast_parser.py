import ast
from typing import List, Dict, Any, Optional


class CodeExtractor(ast.NodeVisitor):
    """Extracts code structure from Python AST using visitor pattern"""
    
    def __init__(self, source: str):
        self.source = source
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.line_count: int = 0
        
        if source:
            self.line_count = len(source.split('\n'))
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract function definition with full metadata"""
        args = []
        for arg in node.args.args:
            args.append({
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation else None
            })
        
        defaults = node.args.defaults
        kw_defaults = node.args.kw_defaults
        
        self.functions.append({
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "args": args,
            "is_async": False,
            "decorators": [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
            "returns": ast.unparse(node.returns) if node.returns else None
        })
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract async function definition"""
        args = []
        for arg in node.args.args:
            args.append({
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation else None
            })
        
        self.functions.append({
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "args": args,
            "is_async": True,
            "decorators": [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
            "returns": ast.unparse(node.returns) if node.returns else None
        })
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class definition with base classes"""
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except:
                bases.append(str(base))
        
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        
        self.classes.append({
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "bases": bases,
            "decorators": [ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
            "methods": methods
        })
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import) -> None:
        """Extract import statements"""
        for alias in node.names:
            if alias.asname:
                self.imports.append(f"{alias.name} as {alias.asname}")
            else:
                self.imports.append(alias.name)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Extract from-import statements"""
        module = node.module or ""
        level = node.level
        
        for alias in node.names:
            if alias.asname:
                self.imports.append(f"from {module} import {alias.name} as {alias.asname}")
            else:
                self.imports.append(f"from {module} import {alias.name}")


def parse_python_file(source: str) -> Dict[str, Any]:
    """Parse Python source code and extract structure
    
    Args:
        source: Python source code as string
        
    Returns:
        Dict with functions, classes, imports, and metadata
    """
    if not source or not source.strip():
        return {
            "functions": [],
            "classes": [],
            "imports": [],
            "line_count": 0,
            "error": None
        }
    
    try:
        tree = ast.parse(source)
        extractor = CodeExtractor(source)
        extractor.visit(tree)
        
        return {
            "functions": extractor.functions,
            "classes": extractor.classes,
            "imports": extractor.imports,
            "line_count": extractor.line_count,
            "error": None
        }
    except SyntaxError as e:
        return {
            "functions": [],
            "classes": [],
            "imports": [],
            "line_count": 0,
            "error": f"Syntax error at line {e.lineno}: {e.msg}"
        }
    except Exception as e:
        return {
            "functions": [],
            "classes": [],
            "imports": [],
            "line_count": 0,
            "error": f"Parse error: {str(e)}"
        }


def extract_lines(source: str, start_line: int, end_line: int) -> str:
    """Extract specific lines from source code
    
    Args:
        source: Full source code
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)
        
    Returns:
        Extracted lines as string
    """
    if not source:
        return ""
    
    lines = source.split('\n')
    
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    
    return '\n'.join(lines[start_idx:end_idx])


def get_code_element(source: str, line_number: int) -> Optional[Dict[str, Any]]:
    """Find which code element (function/class) contains a given line
    
    Args:
        source: Python source code
        line_number: Line number to find
        
    Returns:
        Dict with element info or None if not found
    """
    result = parse_python_file(source)
    
    for func in result.get("functions", []):
        if func["line_start"] <= line_number <= func["line_end"]:
            return {
                "type": "function",
                "name": func["name"],
                "line_start": func["line_start"],
                "line_end": func["line_end"]
            }
    
    for cls in result.get("classes", []):
        if cls["line_start"] <= line_number <= cls["line_end"]:
            return {
                "type": "class",
                "name": cls["name"],
                "line_start": cls["line_start"],
                "line_end": cls["line_end"]
            }
    
    return None
