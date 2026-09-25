from typing import List, Dict
from app.services.discovery.scanner import FileInventory
from app.services.discovery.models import LanguageStat, EvidenceItem, EvidenceType
from app.services.discovery.registry import capability_registry

# Extension to normalized language mapping
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Modern languages
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".cs": "csharp",
    ".scala": "scala",
    ".dart": "dart",
    # Legacy & native languages
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cob": "cobol",
    ".cbl": "cobol",
    ".cpy": "cobol",
    ".f": "fortran",
    ".for": "fortran",
    ".f90": "fortran",
    ".f95": "fortran",
    ".pas": "pascal",
    ".pp": "pascal",
    ".vb": "visual_basic",
    ".vbs": "visual_basic",
    ".pl": "perl",
    ".pm": "perl",
    ".php": "php",
    ".rb": "ruby",
    ".adb": "ada",
    ".ads": "ada",
    # Shell & scripts
    ".sh": "bash",
    ".bash": "bash",
    ".ps1": "powershell",
    ".psm1": "powershell",
    # Data & config
    ".sql": "sql",
    ".pls": "plsql",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".toml": "toml",
    ".tf": "terraform",
    ".graphql": "graphql",
    ".gql": "graphql",
}

# Special filename mappings
EXACT_FILENAME_LANGUAGE_MAP: Dict[str, str] = {
    "dockerfile": "dockerfile",
    "containerfile": "dockerfile",
    "makefile": "makefile",
    "cmakelists.txt": "cmake",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "vagrantfile": "ruby",
}


class LanguageDetector:
    """Deterministic language detector across modern, legacy, and infrastructure languages."""

    def detect(self, inventory: FileInventory) -> List[LanguageStat]:
        lang_line_counts: Dict[str, int] = {}
        lang_file_counts: Dict[str, int] = {}
        lang_evidence: Dict[str, List[EvidenceItem]] = {}

        for f in inventory.files:
            lower_name = f.file_name.lower()
            detected_lang = None
            rule_matched = None

            # 1. Exact filename check
            if lower_name in EXACT_FILENAME_LANGUAGE_MAP:
                detected_lang = EXACT_FILENAME_LANGUAGE_MAP[lower_name]
                rule_matched = f"exact_filename:{lower_name}"
            # 2. Extension check
            elif f.extension in EXTENSION_LANGUAGE_MAP:
                detected_lang = EXTENSION_LANGUAGE_MAP[f.extension]
                rule_matched = f"extension:{f.extension}"
            # 3. Dockerfile.* patterns
            elif lower_name.startswith("dockerfile."):
                detected_lang = "dockerfile"
                rule_matched = "prefix:dockerfile"

            if detected_lang:
                lang_line_counts[detected_lang] = lang_line_counts.get(detected_lang, 0) + f.line_count
                lang_file_counts[detected_lang] = lang_file_counts.get(detected_lang, 0) + 1

                # Collect sample evidence up to 5 files per language
                if len(lang_evidence.get(detected_lang, [])) < 5:
                    lang_evidence.setdefault(detected_lang, []).append(
                        EvidenceItem(
                            evidence_type=EvidenceType.OBSERVED,
                            file_path=f.relative_path,
                            line_number=None,
                            snippet=f"{f.file_name} ({f.line_count} lines)",
                            confidence=0.99,
                            detection_rule=rule_matched or "pattern_match",
                        )
                    )

        # Calculate totals and percentages
        total_detected_lines = sum(lang_line_counts.values()) or 1
        results: List[LanguageStat] = []

        for lang, count in lang_line_counts.items():
            pct = round((count / total_detected_lines) * 100.0, 2)
            cap = capability_registry.get_capabilities_for_language(lang)

            results.append(
                LanguageStat(
                    name=lang,
                    percentage=pct,
                    confidence=0.99,
                    line_count=count,
                    file_count=lang_file_counts.get(lang, 0),
                    capability_level=cap.level,
                    evidence=lang_evidence.get(lang, []),
                )
            )

        # Sort descending by line count / percentage
        results.sort(key=lambda x: x.line_count, reverse=True)
        return results
