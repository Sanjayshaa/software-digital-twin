import bisect
import tree_sitter
from typing import Optional, Dict, List
from app.services.analysis.parsers.base import ParserAdapter, ParserResult, SyntaxNode

# Tree-sitter language imports
import tree_sitter_python
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_typescript


def _convert_ts_node(
    node: tree_sitter.Node,
    source_bytes: bytes,
    line_starts: Optional[List[int]] = None,
) -> SyntaxNode:
    """
    Decoupled converter from native Tree-sitter node to SyntaxNode.
    Uses pure-Python byte-offset bisect for line/col calculation and slices
    source_bytes directly to prevent C extension memory corruption and Bus errors
    under high-volume node allocation during garbage collection.
    """
    if line_starts is None:
        line_starts = [0] + [i + 1 for i, b in enumerate(source_bytes) if b == 10]

    sb = node.start_byte
    eb = node.end_byte

    s_idx = bisect.bisect_right(line_starts, sb) - 1
    s_line = s_idx + 1
    s_col = sb - line_starts[s_idx]

    e_idx = bisect.bisect_right(line_starts, eb) - 1
    e_line = e_idx + 1
    e_col = eb - line_starts[e_idx]

    try:
        text = source_bytes[sb:eb].decode("utf-8", errors="ignore")
    except Exception:
        text = ""

    children = [_convert_ts_node(c, source_bytes, line_starts) for c in node.children]

    return SyntaxNode(
        node_type=node.type,
        text=text,
        start_line=s_line,
        start_col=s_col,
        end_line=e_line,
        end_col=e_col,
        children=children,
        is_named=node.is_named,
    )


class TreeSitterAdapter(ParserAdapter):
    """Production Tree-sitter parser adapter for Python, Java, JS, and TypeScript."""

    def __init__(self, language: str):
        self._language_name = language.lower()
        self._ts_language = self._init_ts_language(self._language_name)
        self._parser = tree_sitter.Parser(self._ts_language)

    def _init_ts_language(self, language: str) -> tree_sitter.Language:
        if language == "python":
            return tree_sitter.Language(tree_sitter_python.language())
        elif language == "java":
            return tree_sitter.Language(tree_sitter_java.language())
        elif language == "javascript":
            return tree_sitter.Language(tree_sitter_javascript.language())
        elif language == "typescript":
            return tree_sitter.Language(tree_sitter_typescript.language_typescript())
        elif language == "tsx":
            return tree_sitter.Language(tree_sitter_typescript.language_tsx())
        else:
            raise ValueError(f"Unsupported tree-sitter language: {language}")

    @property
    def supported_language(self) -> str:
        return self._language_name

    def can_parse(self, file_path: str, language: str) -> bool:
        return language.lower() == self._language_name or (
            self._language_name == "typescript" and language.lower() in {"typescript", "tsx"}
        )

    def parse_source(self, source_bytes: bytes, file_path: str = "") -> ParserResult:
        try:
            tree = self._parser.parse(source_bytes)
            line_starts = [0] + [i + 1 for i, b in enumerate(source_bytes) if b == 10]
            root_syntax_node = _convert_ts_node(tree.root_node, source_bytes, line_starts)
            decoded_source = source_bytes.decode("utf-8", errors="ignore")

            errors = []
            if tree.root_node.has_error:
                errors.append(f"Syntax error detected while parsing {file_path}")

            return ParserResult(
                success=True,
                root_node=root_syntax_node,
                errors=errors,
                source_code=decoded_source,
                language=self._language_name,
                file_path=file_path,
            )
        except Exception as exc:
            return ParserResult(
                success=False,
                errors=[f"Tree-sitter parser error for {file_path}: {str(exc)}"],
                source_code=source_bytes.decode("utf-8", errors="ignore"),
                language=self._language_name,
                file_path=file_path,
            )
