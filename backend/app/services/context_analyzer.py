"""
Service for analyzing code context and repository structure.
"""
import os
import re
import ast
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path
import subprocess
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.doc_embeddings import CodeContext
from app.services.embedding_service import EmbeddingService
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """Analyzes code repositories to understand structure and context."""
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or EmbeddingService()
        self.file_patterns = {
            'python': r'\.py$',
            'javascript': r'\.(js|jsx)$',
            'typescript': r'\.(ts|tsx)$',
            'go': r'\.go$',
            'java': r'\.java$',
            'cpp': r'\.(cpp|cc|cxx|hpp|h)$',
            'rust': r'\.rs$',
            'ruby': r'\.rb$',
            'php': r'\.php$',
            'swift': r'\.swift$',
            'kotlin': r'\.kt$',
            'markdown': r'\.(md|markdown)$',
            'yaml': r'\.(yml|yaml)$',
            'json': r'\.json$'
        }
        
        # Design pattern detectors
        self.design_patterns = {
            'singleton': [r'getInstance', r'_instance', r'@singleton'],
            'factory': [r'Factory', r'create\w+', r'build\w+'],
            'observer': [r'Observer', r'addListener', r'addEventListener', r'subscribe'],
            'decorator': [r'@\w+', r'Decorator', r'wrapper'],
            'strategy': [r'Strategy', r'Policy', r'Algorithm'],
            'adapter': [r'Adapter', r'Wrapper', r'Facade'],
            'repository': [r'Repository', r'Store', r'DAO'],
            'mvc': [r'Controller', r'Model', r'View'],
            'dependency_injection': [r'@inject', r'@autowired', r'Container'],
            'builder': [r'Builder', r'with\w+', r'build\(\)']
        }
    
    async def analyze_repository(
        self,
        db: AsyncSession,
        repository: str,
        repo_path: str,
        max_files: int = 1000
    ) -> Dict[str, Any]:
        """Analyze entire repository structure and context."""
        logger.info(f"Analyzing repository: {repository} at {repo_path}")
        
        analysis = {
            'repository': repository,
            'total_files': 0,
            'analyzed_files': 0,
            'languages': {},
            'patterns': {},
            'structure': {},
            'dependencies': set(),
            'conventions': {},
            'metrics': {}
        }
        
        # Walk through repository
        file_count = 0
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '__pycache__', 'target', 'build', 'dist']]
            
            for file in files:
                if file_count >= max_files:
                    break
                
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repo_path)
                
                # Determine file type
                file_type = self._get_file_type(file)
                if not file_type:
                    continue
                
                file_count += 1
                analysis['total_files'] += 1
                
                # Analyze file
                try:
                    file_analysis = await self.analyze_file(
                        db, repository, relative_path, file_path
                    )
                    
                    if file_analysis:
                        analysis['analyzed_files'] += 1
                        
                        # Update language statistics
                        lang = file_analysis.get('language', 'unknown')
                        analysis['languages'][lang] = analysis['languages'].get(lang, 0) + 1
                        
                        # Collect patterns
                        for pattern in file_analysis.get('design_patterns', []):
                            analysis['patterns'][pattern] = analysis['patterns'].get(pattern, 0) + 1
                        
                        # Collect dependencies
                        analysis['dependencies'].update(file_analysis.get('imports', []))
                        
                except Exception as e:
                    logger.error(f"Error analyzing file {relative_path}: {e}")
        
        # Analyze repository structure
        analysis['structure'] = await self._analyze_structure(repo_path)
        
        # Detect conventions
        analysis['conventions'] = await self._detect_conventions(repo_path)
        
        # Calculate metrics
        analysis['metrics'] = await self._calculate_repository_metrics(
            db, repository, analysis
        )
        
        # Convert sets to lists for JSON serialization
        analysis['dependencies'] = list(analysis['dependencies'])
        
        logger.info(f"Repository analysis complete: {analysis['analyzed_files']} files analyzed")
        
        return analysis
    
    async def analyze_file(
        self,
        db: AsyncSession,
        repository: str,
        relative_path: str,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single file for context."""
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content:
                return None
            
            # Get file info
            stat = os.stat(file_path)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Determine language
            language = self._detect_language(file_path, content)
            
            # Language-specific analysis
            analysis = {
                'file_path': relative_path,
                'language': language,
                'last_modified': last_modified,
                'size': stat.st_size,
                'lines': len(content.splitlines())
            }
            
            if language == 'python':
                analysis.update(self._analyze_python(content))
            elif language in ['javascript', 'typescript']:
                analysis.update(self._analyze_javascript(content))
            elif language == 'go':
                analysis.update(self._analyze_go(content))
            # Add more language analyzers as needed
            
            # Detect design patterns
            analysis['design_patterns'] = self._detect_design_patterns(content)
            
            # Extract related issues and PRs from comments
            analysis['related_issues'] = self._extract_issue_references(content)
            analysis['related_prs'] = self._extract_pr_references(content)
            
            # Calculate complexity (simple line/cyclomatic complexity)
            analysis['complexity_score'] = self._calculate_complexity(content, language)
            
            # Check for tests
            analysis['is_test'] = self._is_test_file(relative_path, content)
            
            # Store in database
            if self.embedding_service:
                await self.embedding_service.embed_code_context(
                    db, repository, relative_path, content[:2000], analysis
                )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return None
    
    def _get_file_type(self, filename: str) -> Optional[str]:
        """Determine file type from filename."""
        for file_type, pattern in self.file_patterns.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return file_type
        return None
    
    def _detect_language(self, file_path: str, content: str) -> str:
        """Detect programming language from file extension and content."""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.md': 'markdown',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.json': 'json'
        }
        
        return language_map.get(ext, 'unknown')
    
    def _analyze_python(self, content: str) -> Dict[str, Any]:
        """Analyze Python file content."""
        analysis = {
            'module_name': None,
            'classes': [],
            'functions': [],
            'imports': [],
            'exports': [],
            'docstring': None
        }
        
        try:
            tree = ast.parse(content)
            
            # Extract module docstring
            if ast.get_docstring(tree):
                analysis['docstring'] = ast.get_docstring(tree)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    analysis['classes'].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    analysis['functions'].append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis['imports'].append(node.module)
            
            # Exports are typically __all__ in Python
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == '__all__':
                            if isinstance(node.value, ast.List):
                                analysis['exports'] = [
                                    elt.s for elt in node.value.elts
                                    if isinstance(elt, ast.Str)
                                ]
            
        except Exception as e:
            logger.debug(f"Error parsing Python file: {e}")
        
        return analysis
    
    def _analyze_javascript(self, content: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript file content."""
        analysis = {
            'module_name': None,
            'classes': [],
            'functions': [],
            'imports': [],
            'exports': [],
            'components': []  # For React components
        }
        
        # Extract imports
        import_pattern = r'import\s+(?:{[^}]+}|[\w,\s]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            analysis['imports'].append(match.group(1))
        
        # Extract require statements
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, content):
            analysis['imports'].append(match.group(1))
        
        # Extract classes
        class_pattern = r'class\s+(\w+)'
        analysis['classes'] = re.findall(class_pattern, content)
        
        # Extract functions
        function_patterns = [
            r'function\s+(\w+)',
            r'const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>'
        ]
        for pattern in function_patterns:
            analysis['functions'].extend(re.findall(pattern, content))
        
        # Extract exports
        export_patterns = [
            r'export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)',
            r'export\s*{\s*([^}]+)\s*}'
        ]
        for pattern in export_patterns:
            matches = re.findall(pattern, content)
            if matches:
                if isinstance(matches[0], str) and ',' in matches[0]:
                    analysis['exports'].extend([m.strip() for m in matches[0].split(',')])
                else:
                    analysis['exports'].extend(matches)
        
        # Detect React components
        component_pattern = r'(?:function|const)\s+([A-Z]\w+).*?(?:return\s+(?:<|\(?\s*<)|React\.createElement)'
        analysis['components'] = re.findall(component_pattern, content, re.DOTALL)
        
        return analysis
    
    def _analyze_go(self, content: str) -> Dict[str, Any]:
        """Analyze Go file content."""
        analysis = {
            'package': None,
            'structs': [],
            'functions': [],
            'interfaces': [],
            'imports': []
        }
        
        # Extract package name
        package_match = re.search(r'package\s+(\w+)', content)
        if package_match:
            analysis['package'] = package_match.group(1)
        
        # Extract imports
        import_pattern = r'import\s*\(\s*([^)]+)\s*\)|import\s+"([^"]+)"'
        for match in re.finditer(import_pattern, content, re.DOTALL):
            if match.group(1):  # Multi-line import
                imports = re.findall(r'"([^"]+)"', match.group(1))
                analysis['imports'].extend(imports)
            elif match.group(2):  # Single import
                analysis['imports'].append(match.group(2))
        
        # Extract structs
        struct_pattern = r'type\s+(\w+)\s+struct'
        analysis['structs'] = re.findall(struct_pattern, content)
        
        # Extract interfaces
        interface_pattern = r'type\s+(\w+)\s+interface'
        analysis['interfaces'] = re.findall(interface_pattern, content)
        
        # Extract functions
        func_pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('
        analysis['functions'] = re.findall(func_pattern, content)
        
        return analysis
    
    def _detect_design_patterns(self, content: str) -> List[str]:
        """Detect design patterns in code."""
        detected_patterns = []
        
        for pattern_name, indicators in self.design_patterns.items():
            for indicator in indicators:
                if re.search(indicator, content, re.IGNORECASE):
                    detected_patterns.append(pattern_name)
                    break
        
        return list(set(detected_patterns))
    
    def _extract_issue_references(self, content: str) -> List[str]:
        """Extract GitHub issue references from code."""
        # Match patterns like #123, GH-123, fixes #123
        pattern = r'(?:(?:fixes|closes|resolves|references?|see)\s+)?#(\d+)|GH-(\d+)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        issues = []
        for match in matches:
            issue_num = match[0] or match[1]
            if issue_num:
                issues.append(issue_num)
        
        return list(set(issues))
    
    def _extract_pr_references(self, content: str) -> List[str]:
        """Extract PR references from code."""
        # Match patterns like PR #123, !123 (GitLab style)
        pattern = r'PR\s*#(\d+)|!(\d+)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        prs = []
        for match in matches:
            pr_num = match[0] or match[1]
            if pr_num:
                prs.append(pr_num)
        
        return list(set(prs))
    
    def _calculate_complexity(self, content: str, language: str) -> float:
        """Calculate simple complexity score."""
        lines = content.splitlines()
        
        # Simple complexity factors
        complexity = 0.0
        
        # Lines of code
        loc = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//'))])
        complexity += loc * 0.01
        
        # Control structures
        control_patterns = [
            r'\bif\b', r'\belse\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
            r'\btry\b', r'\bcatch\b', r'\bswitch\b', r'\bcase\b'
        ]
        
        for pattern in control_patterns:
            complexity += len(re.findall(pattern, content)) * 0.5
        
        # Nesting depth (simplified)
        max_indent = 0
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent)
        
        complexity += (max_indent / 4) * 2  # Assuming 4-space indents
        
        return min(complexity, 100.0)  # Cap at 100
    
    def _is_test_file(self, file_path: str, content: str) -> bool:
        """Check if file is a test file."""
        # Check file path
        test_indicators = ['test', 'spec', '__tests__', 'tests']
        if any(indicator in file_path.lower() for indicator in test_indicators):
            return True
        
        # Check content
        test_patterns = [
            r'import\s+unittest', r'from\s+unittest',
            r'describe\(', r'it\(', r'test\(',
            r'@Test', r'func\s+Test\w+'
        ]
        
        return any(re.search(pattern, content) for pattern in test_patterns)
    
    async def _analyze_structure(self, repo_path: str) -> Dict[str, Any]:
        """Analyze repository structure."""
        structure = {
            'type': 'unknown',
            'framework': None,
            'build_tool': None,
            'test_framework': None,
            'has_ci': False,
            'has_docker': False,
            'has_docs': False
        }
        
        # Check for common project files
        files_to_check = {
            'package.json': ('node', 'npm'),
            'pyproject.toml': ('python', 'poetry'),
            'setup.py': ('python', 'setuptools'),
            'requirements.txt': ('python', 'pip'),
            'go.mod': ('go', 'go modules'),
            'Cargo.toml': ('rust', 'cargo'),
            'pom.xml': ('java', 'maven'),
            'build.gradle': ('java', 'gradle'),
            'composer.json': ('php', 'composer'),
            'Gemfile': ('ruby', 'bundler')
        }
        
        for file, (lang, tool) in files_to_check.items():
            if os.path.exists(os.path.join(repo_path, file)):
                structure['type'] = lang
                structure['build_tool'] = tool
                
                # Read file for framework detection
                try:
                    with open(os.path.join(repo_path, file), 'r') as f:
                        content = f.read()
                        
                        # Detect frameworks
                        if 'react' in content.lower():
                            structure['framework'] = 'react'
                        elif 'vue' in content.lower():
                            structure['framework'] = 'vue'
                        elif 'angular' in content.lower():
                            structure['framework'] = 'angular'
                        elif 'django' in content.lower():
                            structure['framework'] = 'django'
                        elif 'flask' in content.lower():
                            structure['framework'] = 'flask'
                        elif 'fastapi' in content.lower():
                            structure['framework'] = 'fastapi'
                        elif 'spring' in content.lower():
                            structure['framework'] = 'spring'
                        
                        # Detect test framework
                        if 'jest' in content.lower():
                            structure['test_framework'] = 'jest'
                        elif 'pytest' in content.lower():
                            structure['test_framework'] = 'pytest'
                        elif 'unittest' in content.lower():
                            structure['test_framework'] = 'unittest'
                        elif 'mocha' in content.lower():
                            structure['test_framework'] = 'mocha'
                except:
                    pass
                
                break
        
        # Check for CI/CD
        ci_paths = ['.github/workflows', '.gitlab-ci.yml', 'Jenkinsfile', '.circleci']
        structure['has_ci'] = any(
            os.path.exists(os.path.join(repo_path, path))
            for path in ci_paths
        )
        
        # Check for Docker
        structure['has_docker'] = os.path.exists(os.path.join(repo_path, 'Dockerfile'))
        
        # Check for docs
        docs_paths = ['docs', 'documentation', 'README.md']
        structure['has_docs'] = any(
            os.path.exists(os.path.join(repo_path, path))
            for path in docs_paths
        )
        
        return structure
    
    async def _detect_conventions(self, repo_path: str) -> Dict[str, Any]:
        """Detect coding conventions used in the repository."""
        conventions = {
            'naming': {
                'style': 'unknown',
                'file_naming': 'unknown',
                'const_naming': 'unknown'
            },
            'formatting': {
                'indent': 'unknown',
                'quotes': 'unknown',
                'semicolons': None
            },
            'documentation': {
                'style': 'unknown',
                'coverage': 0.0
            }
        }
        
        # Sample some files to detect conventions
        sample_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if self._get_file_type(file) in ['python', 'javascript', 'typescript']:
                    sample_files.append(os.path.join(root, file))
                    if len(sample_files) >= 10:
                        break
            if len(sample_files) >= 10:
                break
        
        if not sample_files:
            return conventions
        
        # Analyze naming conventions
        camel_case_count = 0
        snake_case_count = 0
        kebab_case_count = 0
        
        for file_path in sample_files:
            filename = os.path.basename(file_path)
            
            if re.match(r'^[a-z]+(?:[A-Z][a-z]+)*\.\w+$', filename):
                camel_case_count += 1
            elif re.match(r'^[a-z]+(?:_[a-z]+)*\.\w+$', filename):
                snake_case_count += 1
            elif re.match(r'^[a-z]+(?:-[a-z]+)*\.\w+$', filename):
                kebab_case_count += 1
        
        # Determine predominant style
        if snake_case_count > camel_case_count and snake_case_count > kebab_case_count:
            conventions['naming']['file_naming'] = 'snake_case'
        elif camel_case_count > kebab_case_count:
            conventions['naming']['file_naming'] = 'camelCase'
        else:
            conventions['naming']['file_naming'] = 'kebab-case'
        
        # Analyze code formatting
        indent_counts = {2: 0, 4: 0}
        quote_counts = {'single': 0, 'double': 0}
        semicolon_count = 0
        total_lines = 0
        
        for file_path in sample_files[:5]:  # Just check first 5 files
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.splitlines()
                    
                    for line in lines:
                        if line.strip():
                            total_lines += 1
                            
                            # Check indentation
                            if line.startswith('  ') and not line.startswith('    '):
                                indent_counts[2] += 1
                            elif line.startswith('    '):
                                indent_counts[4] += 1
                            
                            # Check quotes
                            quote_counts['single'] += line.count("'")
                            quote_counts['double'] += line.count('"')
                            
                            # Check semicolons (for JS/TS)
                            if line.rstrip().endswith(';'):
                                semicolon_count += 1
            except:
                pass
        
        # Determine conventions
        conventions['formatting']['indent'] = '4 spaces' if indent_counts[4] > indent_counts[2] else '2 spaces'
        conventions['formatting']['quotes'] = 'single' if quote_counts['single'] > quote_counts['double'] else 'double'
        
        if total_lines > 0:
            semicolon_ratio = semicolon_count / total_lines
            conventions['formatting']['semicolons'] = semicolon_ratio > 0.3
        
        return conventions
    
    async def _calculate_repository_metrics(
        self,
        db: AsyncSession,
        repository: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate repository-wide metrics."""
        metrics = {
            'total_lines': 0,
            'documentation_files': 0,
            'test_files': 0,
            'average_file_size': 0,
            'languages_breakdown': analysis['languages'],
            'patterns_used': list(analysis['patterns'].keys()),
            'estimated_complexity': 0.0
        }
        
        # Get all code contexts for this repository
        stmt = select(CodeContext).where(CodeContext.repository == repository)
        result = await db.execute(stmt)
        contexts = result.scalars().all()
        
        if contexts:
            total_complexity = sum(c.complexity_score or 0 for c in contexts)
            metrics['estimated_complexity'] = total_complexity / len(contexts)
            
            test_count = sum(1 for c in contexts if c.context_metadata.get('is_test'))
            metrics['test_files'] = test_count
        
        # Count documentation files
        doc_extensions = ['.md', '.rst', '.txt']
        metrics['documentation_files'] = sum(
            1 for lang in analysis['languages']
            if lang in ['markdown', 'restructuredtext', 'text']
        )
        
        return metrics
    
    async def get_file_context(
        self,
        db: AsyncSession,
        repository: str,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive context for a specific file."""
        # Get stored context
        stmt = select(CodeContext).where(
            CodeContext.repository == repository,
            CodeContext.file_path == file_path
        )
        result = await db.execute(stmt)
        context = result.scalar_one_or_none()
        
        if not context:
            return None
        
        # Build comprehensive context
        file_context = context.to_dict()
        
        # Find related files using embeddings
        if self.embedding_service and context.context_embedding:
            related = await self.embedding_service.find_related_code(
                db,
                f"Related to {file_path}",
                repository,
                limit=5
            )
            
            file_context['related_files'] = [
                {
                    'path': ctx.file_path,
                    'similarity': score,
                    'type': 'dependency' if ctx.file_path in context.dependencies else 'related'
                }
                for ctx, score in related
            ]
        
        # Get recent commits touching this file
        try:
            commits = await self._get_recent_commits(repository, file_path, limit=5)
            file_context['recent_commits'] = commits
        except:
            file_context['recent_commits'] = []
        
        return file_context
    
    async def _get_recent_commits(
        self,
        repository: str,
        file_path: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent commits for a file using git."""
        # This is a simplified version - in production, you'd use the GitHub API
        # or have a proper git integration
        try:
            # Assume we have a local clone of the repository
            repo_path = f"/tmp/repos/{repository}"
            if not os.path.exists(repo_path):
                return []
            
            # Get commit history for the file
            cmd = [
                'git', '-C', repo_path, 'log',
                f'--max-count={limit}',
                '--pretty=format:%H|%an|%ae|%at|%s',
                '--', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        commits.append({
                            'hash': parts[0][:7],
                            'author': parts[1],
                            'email': parts[2],
                            'timestamp': datetime.fromtimestamp(int(parts[3])).isoformat(),
                            'message': parts[4]
                        })
            
            return commits
            
        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            return []