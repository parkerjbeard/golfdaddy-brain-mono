"""
Target file selection for documentation updates with semantic matching.
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.core.database import AsyncSession
from app.integrations.ai_integration_v2 import AIIntegrationV2
from app.repositories.doc_chunk_repository import DocChunkRepository
from app.services.doc_task_planner import DocSection, DocumentationTask

logger = logging.getLogger(__name__)


class DocFramework(Enum):
    """Supported documentation frameworks."""

    MKDOCS = "mkdocs"
    DOCUSAURUS = "docusaurus"
    SPHINX = "sphinx"
    HUGO = "hugo"
    JEKYLL = "jekyll"
    VITEPRESS = "vitepress"
    GENERIC = "generic"


@dataclass
class TargetFile:
    """Represents a target documentation file."""

    path: str
    framework: DocFramework
    confidence: float  # How confident we are this is the right file
    reason: str  # Why this file was selected
    section: Optional[str] = None  # Specific section within the file
    create_if_missing: bool = False  # Whether to create if doesn't exist
    metadata: Dict[str, Any] = None


@dataclass
class DocStructureRule:
    """Rule for documentation structure organization."""

    framework: DocFramework
    section_mapping: Dict[DocSection, str]  # Maps DocSection to file paths
    nav_file: str  # Navigation/sidebar configuration file
    nav_format: str  # Format of navigation file (yaml, json, js)
    create_pattern: str  # Pattern for creating new files


class TargetFileSelector:
    """Selects appropriate documentation files for updates."""

    def __init__(self, session: AsyncSession):
        """Initialize the target file selector."""
        self.session = session
        self.doc_repository = DocChunkRepository(session)
        self.ai_integration = AIIntegrationV2()
        self.structure_rules = self._initialize_structure_rules()
        self._docs_cache = {}  # Cache for documentation file listings

    async def select_target_files(
        self, task: DocumentationTask, repo_path: str, max_files: int = 3
    ) -> List[TargetFile]:
        """
        Select target documentation files for a task.

        Args:
            task: Documentation task to find files for
            repo_path: Repository root path
            max_files: Maximum number of target files to return

        Returns:
            List of target files sorted by confidence
        """
        targets = []

        # Detect documentation framework
        framework = self._detect_framework(repo_path)

        # Try semantic matching first
        semantic_targets = await self._semantic_file_matching(task, repo_path, framework)
        targets.extend(semantic_targets)

        # Fall back to convention-based matching
        if len(targets) < max_files:
            convention_targets = self._convention_based_matching(task, repo_path, framework)
            targets.extend(convention_targets)

        # Check for duplicate content
        targets = await self._check_duplicates(targets, task)

        # Sort by confidence and limit
        targets = sorted(targets, key=lambda t: t.confidence, reverse=True)[:max_files]

        # Update navigation files if needed
        if framework != DocFramework.GENERIC:
            nav_updates = self._get_nav_updates(task, targets, repo_path, framework)
            if nav_updates:
                targets.extend(nav_updates)

        return targets

    def _detect_framework(self, repo_path: str) -> DocFramework:
        """Detect which documentation framework is being used."""
        repo = Path(repo_path)

        # Check for framework-specific files
        if (repo / "mkdocs.yml").exists() or (repo / "mkdocs.yaml").exists():
            return DocFramework.MKDOCS
        elif (repo / "docusaurus.config.js").exists():
            return DocFramework.DOCUSAURUS
        elif (repo / "conf.py").exists() and (repo / "source").exists():
            return DocFramework.SPHINX
        elif (repo / "config.toml").exists() and (repo / "content").exists():
            return DocFramework.HUGO
        elif (repo / "_config.yml").exists():
            return DocFramework.JEKYLL
        elif (repo / ".vitepress").exists():
            return DocFramework.VITEPRESS
        else:
            return DocFramework.GENERIC

    async def _semantic_file_matching(
        self, task: DocumentationTask, repo_path: str, framework: DocFramework
    ) -> List[TargetFile]:
        """Use embeddings to find semantically similar documentation files."""
        targets = []

        try:
            # Generate embedding for the task
            task_text = f"{task.title}\n{task.description}\n{task.content_template[:500]}"
            task_embedding = await self.ai_integration.generate_embeddings(task_text)

            # Search for similar documentation chunks
            similar_chunks = await self.doc_repository.search_similar_chunks(
                repo=repo_path, embedding=task_embedding, limit=10
            )

            # Group by file and calculate file-level confidence
            file_scores = {}
            for chunk in similar_chunks:
                file_path = chunk.get("path", "")
                similarity = chunk.get("similarity", 0.0)

                if file_path not in file_scores:
                    file_scores[file_path] = []
                file_scores[file_path].append(similarity)

            # Create target files from top matches
            for file_path, scores in file_scores.items():
                avg_score = sum(scores) / len(scores)

                # Only include files with reasonable similarity
                if avg_score > 0.5:
                    target = TargetFile(
                        path=file_path,
                        framework=framework,
                        confidence=avg_score,
                        reason=f"Semantic similarity: {avg_score:.2f}",
                        section=self._find_best_section(task, similar_chunks, file_path),
                    )
                    targets.append(target)

        except Exception as e:
            logger.error(f"Error in semantic matching: {e}")

        return targets

    def _convention_based_matching(
        self, task: DocumentationTask, repo_path: str, framework: DocFramework
    ) -> List[TargetFile]:
        """Use naming conventions and structure rules to find target files."""
        targets = []

        # Get structure rule for this framework
        rule = next((r for r in self.structure_rules if r.framework == framework), None)
        if not rule:
            rule = self._get_generic_rule()

        # Map task section to file path pattern
        path_pattern = rule.section_mapping.get(task.target_section, None)

        if path_pattern:
            # Check if file exists or should be created
            docs_dir = self._get_docs_directory(repo_path, framework)
            target_path = Path(docs_dir) / path_pattern

            if target_path.exists():
                confidence = 0.7  # Good confidence for convention match
                reason = "Convention-based match"
            else:
                confidence = 0.6  # Lower confidence for new file
                reason = "Convention-based (new file)"

            target = TargetFile(
                path=str(target_path),
                framework=framework,
                confidence=confidence,
                reason=reason,
                create_if_missing=not target_path.exists(),
            )
            targets.append(target)

        # Also check suggested files from the task
        for suggested_file in task.suggested_files:
            full_path = Path(repo_path) / suggested_file

            # Check if it's a reasonable suggestion
            if self._is_valid_doc_path(full_path):
                target = TargetFile(
                    path=str(full_path),
                    framework=framework,
                    confidence=0.5,  # Medium confidence for suggestions
                    reason="Task-suggested file",
                    create_if_missing=not full_path.exists(),
                )
                targets.append(target)

        return targets

    async def _check_duplicates(self, targets: List[TargetFile], task: DocumentationTask) -> List[TargetFile]:
        """Check for and prevent duplicate content."""
        filtered_targets = []

        for target in targets:
            # Check if similar content already exists in this file
            is_duplicate = await self._content_exists(target.path, task)

            if not is_duplicate:
                filtered_targets.append(target)
            else:
                logger.info(f"Skipping {target.path} - similar content already exists")

        return filtered_targets

    async def _content_exists(self, file_path: str, task: DocumentationTask) -> bool:
        """Check if similar content already exists in a file."""
        try:
            # Get chunks for this file
            repo = str(Path(file_path).parent.parent)  # Assume repo is 2 levels up
            chunks = await self.doc_repository.get_chunks_by_document(repo, file_path)

            # Check for similar headings or content
            task_keywords = self._extract_keywords(task.title + " " + task.description)

            for chunk in chunks:
                chunk_keywords = self._extract_keywords(chunk.heading + " " + (chunk.content or ""))
                overlap = len(task_keywords & chunk_keywords) / max(len(task_keywords), 1)

                if overlap > 0.7:  # High overlap suggests duplicate
                    return True

        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")

        return False

    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text for duplicate detection."""
        # Simple keyword extraction
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter out common words
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
        }
        return set(w for w in words if w not in stopwords and len(w) > 2)

    def _get_nav_updates(
        self, task: DocumentationTask, targets: List[TargetFile], repo_path: str, framework: DocFramework
    ) -> List[TargetFile]:
        """Get navigation/sidebar files that need updating."""
        nav_targets = []

        rule = next((r for r in self.structure_rules if r.framework == framework), None)
        if not rule:
            return nav_targets

        nav_path = Path(repo_path) / rule.nav_file

        # Check if any target files are new
        new_files = [t for t in targets if t.create_if_missing]

        if new_files and nav_path.exists():
            nav_target = TargetFile(
                path=str(nav_path),
                framework=framework,
                confidence=0.9,  # High confidence for nav updates
                reason="Navigation update for new files",
                metadata={"new_entries": [f.path for f in new_files], "section": task.target_section.value},
            )
            nav_targets.append(nav_target)

        return nav_targets

    def _find_best_section(
        self, task: DocumentationTask, chunks: List[Dict[str, Any]], file_path: str
    ) -> Optional[str]:
        """Find the best section within a file for the task."""
        file_chunks = [c for c in chunks if c.get("path") == file_path]

        if not file_chunks:
            return None

        # Return the heading of the most similar chunk
        best_chunk = max(file_chunks, key=lambda c: c.get("similarity", 0))
        return best_chunk.get("heading")

    def _get_docs_directory(self, repo_path: str, framework: DocFramework) -> str:
        """Get the documentation directory for a framework."""
        repo = Path(repo_path)

        directories = {
            DocFramework.MKDOCS: repo / "docs",
            DocFramework.DOCUSAURUS: repo / "docs",
            DocFramework.SPHINX: repo / "source",
            DocFramework.HUGO: repo / "content",
            DocFramework.JEKYLL: repo / "_posts",
            DocFramework.VITEPRESS: repo / "docs",
            DocFramework.GENERIC: repo / "docs",
        }

        docs_dir = directories.get(framework, repo / "docs")

        # Create if doesn't exist
        if not docs_dir.exists():
            docs_dir = repo / "docs"

        return str(docs_dir)

    def _is_valid_doc_path(self, path: Path) -> bool:
        """Check if a path is a valid documentation file."""
        # Check extension
        valid_extensions = [".md", ".mdx", ".rst", ".adoc"]
        if not any(str(path).endswith(ext) for ext in valid_extensions):
            return False

        # Check if it's in a reasonable location
        path_str = str(path).lower()
        doc_indicators = ["doc", "guide", "manual", "readme", "wiki", "help"]

        return any(indicator in path_str for indicator in doc_indicators)

    def _initialize_structure_rules(self) -> List[DocStructureRule]:
        """Initialize documentation structure rules for different frameworks."""
        return [
            # MkDocs
            DocStructureRule(
                framework=DocFramework.MKDOCS,
                section_mapping={
                    DocSection.API_DOCS: "api/reference.md",
                    DocSection.CONFIGURATION: "configuration/settings.md",
                    DocSection.MIGRATION: "migration/guide.md",
                    DocSection.TUTORIALS: "tutorials/getting-started.md",
                    DocSection.REFERENCE: "reference/index.md",
                    DocSection.CHANGELOG: "changelog.md",
                    DocSection.EXAMPLES: "examples/index.md",
                    DocSection.ARCHITECTURE: "architecture/overview.md",
                    DocSection.TROUBLESHOOTING: "troubleshooting/common-issues.md",
                    DocSection.RELEASE_NOTES: "release-notes.md",
                },
                nav_file="mkdocs.yml",
                nav_format="yaml",
                create_pattern="{section}/{name}.md",
            ),
            # Docusaurus
            DocStructureRule(
                framework=DocFramework.DOCUSAURUS,
                section_mapping={
                    DocSection.API_DOCS: "api/reference.md",
                    DocSection.CONFIGURATION: "guides/configuration.md",
                    DocSection.MIGRATION: "guides/migration.md",
                    DocSection.TUTORIALS: "tutorials/intro.md",
                    DocSection.REFERENCE: "reference/overview.md",
                    DocSection.CHANGELOG: "changelog.md",
                    DocSection.EXAMPLES: "examples/overview.md",
                    DocSection.ARCHITECTURE: "architecture/design.md",
                    DocSection.TROUBLESHOOTING: "guides/troubleshooting.md",
                    DocSection.RELEASE_NOTES: "blog/release-notes.md",
                },
                nav_file="sidebars.js",
                nav_format="js",
                create_pattern="{section}/{name}.md",
            ),
            # Sphinx
            DocStructureRule(
                framework=DocFramework.SPHINX,
                section_mapping={
                    DocSection.API_DOCS: "api.rst",
                    DocSection.CONFIGURATION: "configuration.rst",
                    DocSection.MIGRATION: "migration.rst",
                    DocSection.TUTORIALS: "tutorials/index.rst",
                    DocSection.REFERENCE: "reference/index.rst",
                    DocSection.CHANGELOG: "changelog.rst",
                    DocSection.EXAMPLES: "examples.rst",
                    DocSection.ARCHITECTURE: "architecture.rst",
                    DocSection.TROUBLESHOOTING: "troubleshooting.rst",
                    DocSection.RELEASE_NOTES: "release_notes.rst",
                },
                nav_file="index.rst",
                nav_format="rst",
                create_pattern="{section}/{name}.rst",
            ),
        ]

    def _get_generic_rule(self) -> DocStructureRule:
        """Get a generic documentation structure rule."""
        return DocStructureRule(
            framework=DocFramework.GENERIC,
            section_mapping={
                DocSection.API_DOCS: "docs/api.md",
                DocSection.CONFIGURATION: "docs/configuration.md",
                DocSection.MIGRATION: "docs/migration.md",
                DocSection.TUTORIALS: "docs/tutorials.md",
                DocSection.REFERENCE: "docs/reference.md",
                DocSection.CHANGELOG: "CHANGELOG.md",
                DocSection.EXAMPLES: "docs/examples.md",
                DocSection.ARCHITECTURE: "docs/architecture.md",
                DocSection.TROUBLESHOOTING: "docs/troubleshooting.md",
                DocSection.RELEASE_NOTES: "docs/release-notes.md",
            },
            nav_file="README.md",
            nav_format="md",
            create_pattern="docs/{name}.md",
        )


class NavigationUpdater:
    """Updates navigation/sidebar files for documentation frameworks."""

    def update_mkdocs_nav(self, nav_path: str, new_entries: List[Dict[str, str]]) -> bool:
        """Update MkDocs navigation file."""
        try:
            with open(nav_path, "r") as f:
                nav_data = yaml.safe_load(f)

            if "nav" not in nav_data:
                nav_data["nav"] = []

            for entry in new_entries:
                section = entry.get("section", "Reference")
                title = entry.get("title", "New Page")
                path = entry.get("path", "")

                # Find or create section
                section_found = False
                for item in nav_data["nav"]:
                    if isinstance(item, dict) and section in item:
                        item[section].append({title: path})
                        section_found = True
                        break

                if not section_found:
                    nav_data["nav"].append({section: [{title: path}]})

            with open(nav_path, "w") as f:
                yaml.dump(nav_data, f, default_flow_style=False)

            return True

        except Exception as e:
            logger.error(f"Error updating MkDocs nav: {e}")
            return False

    def update_docusaurus_sidebar(self, sidebar_path: str, new_entries: List[Dict[str, str]]) -> bool:
        """Update Docusaurus sidebar file."""
        try:
            # Read existing sidebar
            with open(sidebar_path, "r") as f:
                content = f.read()

            # Parse JavaScript module
            # This is simplified - real implementation would use proper JS parsing
            for entry in new_entries:
                section = entry.get("section", "reference")
                doc_id = entry.get("path", "").replace(".md", "").replace("/", "-")

                # Find section and add entry
                section_pattern = f"'{section}':\\s*\\["
                if re.search(section_pattern, content):
                    # Add to existing section
                    content = re.sub(section_pattern, f"'{section}': ['{doc_id}', ", content, count=1)
                else:
                    # Add new section
                    content = content.replace(
                        "module.exports = {", f"module.exports = {{\n  '{section}': ['{doc_id}'],"
                    )

            with open(sidebar_path, "w") as f:
                f.write(content)

            return True

        except Exception as e:
            logger.error(f"Error updating Docusaurus sidebar: {e}")
            return False
