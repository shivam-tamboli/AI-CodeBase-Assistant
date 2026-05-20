"""
Multi-language AST parser using tree-sitter.

Extracts functions and classes from JS, TS, Go, Java, Rust, and Ruby source files.
Returns None when a grammar package is not installed, allowing callers to fall back
to line-based chunking without failing.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import importlib
import logging

logger = logging.getLogger(__name__)

# Maps language name → (tree-sitter package, language factory function, function node types, class node types)
_LANG_CONFIG: Dict[str, Tuple[str, str, Set[str], Set[str]]] = {
    "javascript": (
        "tree_sitter_javascript", "language",
        {"function_declaration", "function_expression", "arrow_function",
         "method_definition", "generator_function_declaration"},
        {"class_declaration", "class"},
    ),
    "typescript": (
        "tree_sitter_typescript", "language_typescript",
        {"function_declaration", "function_expression", "arrow_function",
         "method_definition", "abstract_method_signature"},
        {"class_declaration", "interface_declaration"},
    ),
    "go": (
        "tree_sitter_go", "language",
        {"function_declaration", "method_declaration"},
        {"type_declaration"},
    ),
    "java": (
        "tree_sitter_java", "language",
        {"method_declaration", "constructor_declaration"},
        {"class_declaration", "interface_declaration", "enum_declaration"},
    ),
    "rust": (
        "tree_sitter_rust", "language",
        {"function_item"},
        {"struct_item", "enum_item", "trait_item", "impl_item"},
    ),
    "ruby": (
        "tree_sitter_ruby", "language",
        {"method", "singleton_method"},
        {"class", "module"},
    ),
}


def _get_parser(language: str):
    """Build a tree-sitter Parser for the given language, or return None."""
    config = _LANG_CONFIG.get(language)
    if not config:
        return None, None, None

    pkg_name, func_name, func_types, class_types = config

    try:
        import tree_sitter

        module = importlib.import_module(pkg_name)
        lang_factory = getattr(module, func_name)
        ts_lang = tree_sitter.Language(lang_factory())

        parser = tree_sitter.Parser()
        parser.language = ts_lang

        return parser, func_types, class_types

    except ImportError:
        logger.debug("tree-sitter grammar not installed for '%s' (%s)", language, pkg_name)
        return None, None, None
    except Exception as exc:
        logger.warning("Failed to load tree-sitter grammar for '%s': %s", language, exc)
        return None, None, None


def _node_name(node) -> Optional[str]:
    """Return the name of a function/class node."""
    # Prefer the dedicated 'name' field present in most grammars
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf-8", errors="replace")

    # Fallback: first identifier-like child
    identifier_types = {"identifier", "property_identifier", "field_identifier", "type_identifier"}
    for child in node.children:
        if child.type in identifier_types:
            return child.text.decode("utf-8", errors="replace")

    return None


def _walk(node, func_types: Set[str], class_types: Set[str]) -> Tuple[List, List]:
    """Recursively extract functions and classes from a parse tree node."""
    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []

    for child in node.children:
        if child.type in func_types:
            functions.append({
                "name": _node_name(child) or "<anonymous>",
                "line_start": child.start_point[0] + 1,
                "line_end": child.end_point[0] + 1,
            })
            # Recurse to catch nested functions/classes
            sub_f, sub_c = _walk(child, func_types, class_types)
            functions.extend(sub_f)
            classes.extend(sub_c)
        elif child.type in class_types:
            classes.append({
                "name": _node_name(child) or "<anonymous>",
                "line_start": child.start_point[0] + 1,
                "line_end": child.end_point[0] + 1,
            })
            sub_f, sub_c = _walk(child, func_types, class_types)
            functions.extend(sub_f)
            classes.extend(sub_c)
        else:
            sub_f, sub_c = _walk(child, func_types, class_types)
            functions.extend(sub_f)
            classes.extend(sub_c)

    return functions, classes


def parse_file(source: str, language: str) -> Optional[Dict[str, Any]]:
    """Parse source code and extract functions/classes using tree-sitter.

    Returns a dict with the same shape as ast_parser.parse_python_file(), or
    None if tree-sitter or the language grammar is not available.
    """
    parser, func_types, class_types = _get_parser(language)
    if parser is None:
        return None

    try:
        tree = parser.parse(bytes(source, "utf-8"))
        functions, classes = _walk(tree.root_node, func_types, class_types)

        return {
            "functions": functions,
            "classes": classes,
            "imports": [],
            "line_count": len(source.splitlines()),
            "error": None,
        }
    except Exception as exc:
        logger.warning("tree-sitter parse failed for '%s': %s", language, exc)
        return None
