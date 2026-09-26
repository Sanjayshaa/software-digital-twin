from abc import ABC, abstractmethod
from typing import List, Optional, Any


class SyntaxNode:
    """Unified syntax tree node abstraction decoupled from parser implementations."""

    def __init__(
        self,
        node_type: str,
        text: str,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        children: Optional[List["SyntaxNode"]] = None,
        is_named: bool = True,
    ):
        self.node_type = node_type
        self.text = text
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.children = children or []
        self.is_named = is_named

    def find_children_by_type(self, *target_types: str) -> List["SyntaxNode"]:
        """Finds direct children matching given node types."""
        return [c for c in self.children if c.node_type in target_types]

    def walk(self):
        """Depth-first pre-order traversal generator."""
        yield self
        for child in self.children:
            yield from child.walk()


class ParserResult:
    """Standardized result returned by all parser adapters."""

    def __init__(
        self,
        success: bool,
        root_node: Optional[SyntaxNode] = None,
        errors: Optional[List[str]] = None,
        source_code: str = "",
        language: str = "",
        file_path: str = "",
    ):
        self.success = success
        self.root_node = root_node
        self.errors = errors or []
        self.source_code = source_code
        self.language = language
        self.file_path = file_path


class ParserAdapter(ABC):
    """Abstract adapter decoupling tree-sitter or other engines from the Digital Twin."""

    @property
    @abstractmethod
    def supported_language(self) -> str:
        """Normalized language name (e.g. 'python', 'java')."""
        pass

    @abstractmethod
    def can_parse(self, file_path: str, language: str) -> bool:
        """Return True if this adapter can process the file."""
        pass

    @abstractmethod
    def parse_source(self, source_bytes: bytes, file_path: str = "") -> ParserResult:
        """Parse source code in bytes and return normalized ParserResult."""
        pass

    def parse_file(self, file_path: str) -> ParserResult:
        """Read file from disk and parse."""
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return self.parse_source(content, file_path=file_path)
        except Exception as exc:
            return ParserResult(
                success=False,
                errors=[f"Failed to read file {file_path}: {str(exc)}"],
                file_path=file_path,
                language=self.supported_language,
            )
