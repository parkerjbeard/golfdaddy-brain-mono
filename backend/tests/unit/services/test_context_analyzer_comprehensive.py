"""
Comprehensive unit tests for the ContextAnalyzer service.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import ast
import re
from typing import Dict, Any, List
from datetime import datetime

from app.services.context_analyzer import ContextAnalyzer
from app.services.embedding_service import EmbeddingService
from app.models.doc_embeddings import CodeContext
from tests.fixtures.auto_doc_fixtures import (
    create_code_context, SAMPLE_DIFFS
)


class TestContextAnalyzerComprehensive:
    """Comprehensive test cases for ContextAnalyzer."""
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Create a mock embedding service."""
        service = Mock(spec=EmbeddingService)
        service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        service.update_code_context_embedding = AsyncMock()
        service.search_code_context = AsyncMock(return_value=[])
        return service
    
    @pytest.fixture
    def analyzer(self, mock_embedding_service):
        """Create a ContextAnalyzer instance."""
        return ContextAnalyzer(mock_embedding_service)
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        return session
    
    @pytest.fixture
    def sample_python_code(self):
        """Sample Python code for testing."""
        return '''
import os
import asyncio
from typing import List, Optional
from app.models import User, Task
from app.services.base import BaseService

class TaskService(BaseService):
    """Service for managing tasks."""
    
    def __init__(self, db_session):
        self.db = db_session
        self.cache = {}
    
    async def get_tasks(self, user_id: int) -> List[Task]:
        """Get all tasks for a user."""
        tasks = await self.db.query(Task).filter(Task.user_id == user_id).all()
        return tasks
    
    async def create_task(self, user: User, title: str, description: Optional[str] = None) -> Task:
        """Create a new task."""
        task = Task(
            user_id=user.id,
            title=title,
            description=description
        )
        self.db.add(task)
        await self.db.commit()
        return task
    
    def _validate_task(self, task_data: dict) -> bool:
        """Validate task data."""
        return bool(task_data.get("title"))

def helper_function():
    """A module-level helper function."""
    return True
'''
    
    @pytest.mark.asyncio
    async def test_analyze_python_file(self, analyzer, sample_python_code):
        """Test analyzing a Python file."""
        file_path = "app/services/task_service.py"
        
        with patch('builtins.open', mock_open(read_data=sample_python_code)):
            # analyze_file takes: db, repository, relative_path, file_path
            result = await analyzer.analyze_file(None, "test-repo", file_path, file_path)
        
        assert result["file_path"] == file_path
        assert result["language"] == "python"
        assert "TaskService" in result["classes"]
        assert "get_tasks" in result["functions"]
        assert "create_task" in result["functions"]
        assert "_validate_task" in result["functions"]
        assert "helper_function" in result["functions"]
        assert "os" in result["imports"]
        assert "asyncio" in result["imports"]
        assert "app.models" in result["imports"]
        assert "BaseService" in result.get("base_classes", [])
    
    @pytest.mark.asyncio
    async def test_analyze_javascript_file(self, analyzer):
        """Test analyzing a JavaScript file."""
        js_code = '''
import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Button } from '../components/ui';

export const TaskList = ({ userId }) => {
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        fetchTasks();
    }, [userId]);
    
    const fetchTasks = async () => {
        try {
            const data = await api.getTasks(userId);
            setTasks(data);
        } finally {
            setLoading(false);
        }
    };
    
    const handleDelete = (taskId) => {
        // Delete task logic
    };
    
    return (
        <div>
            {tasks.map(task => <TaskItem key={task.id} task={task} />)}
        </div>
    );
};

function TaskItem({ task }) {
    return <div>{task.title}</div>;
}
'''
        
        file_path = "frontend/src/components/TaskList.jsx"
        
        with patch('builtins.open', mock_open(read_data=js_code)):
            result = await analyzer.analyze_file(None, "test-repo", file_path, file_path)
        
        assert result["file_path"] == file_path
        assert result["language"] == "javascript"
        assert "TaskList" in result["exports"]
        assert "fetchTasks" in result["functions"]
        assert "handleDelete" in result["functions"]
        assert "TaskItem" in result["functions"]
        assert "react" in result["imports"]
        assert "../services/api" in result["imports"]
    
    @pytest.mark.asyncio
    async def test_analyze_typescript_file(self, analyzer):
        """Test analyzing a TypeScript file."""
        ts_code = '''
interface Task {
    id: number;
    title: string;
    description?: string;
    completed: boolean;
}

export class TaskManager {
    private tasks: Task[] = [];
    
    constructor(private apiService: ApiService) {}
    
    async loadTasks(): Promise<void> {
        this.tasks = await this.apiService.fetchTasks();
    }
    
    addTask(task: Task): void {
        this.tasks.push(task);
    }
    
    getTasks(): Task[] {
        return [...this.tasks];
    }
}

export function createTask(title: string): Task {
    return {
        id: Date.now(),
        title,
        completed: false
    };
}
'''
        
        file_path = "src/services/TaskManager.ts"
        
        with patch('builtins.open', mock_open(read_data=ts_code)):
            result = await analyzer.analyze_file(None, "test-repo", file_path, file_path)
        
        assert result["file_path"] == file_path
        assert result["language"] == "typescript"
        assert "TaskManager" in result["classes"]
        assert "Task" in result["interfaces"]
        assert "loadTasks" in result["functions"]
        assert "addTask" in result["functions"]
        assert "createTask" in result["functions"]
        assert "TaskManager" in result["exports"]
        assert "createTask" in result["exports"]
    
    @pytest.mark.asyncio
    async def test_get_file_context_from_db(self, analyzer, mock_db_session):
        """Test retrieving file context from database."""
        repository = "test-repo"
        file_path = "app/services/user_service.py"
        
        # Mock existing context in database
        context_data = create_code_context(file_path=file_path, repository=repository)
        
        # Create a mock object that has a to_dict method
        mock_context = Mock()
        mock_context.to_dict.return_value = context_data
        
        # Add the attributes directly to the mock
        for key, value in context_data.items():
            setattr(mock_context, key, value)
        
        # Also set context_embedding as an attribute
        mock_context.context_embedding = context_data.get('context_embedding')
        
        mock_db_result = Mock()
        mock_db_result.scalar_one_or_none.return_value = mock_context
        mock_db_session.execute.return_value = mock_db_result
        
        result = await analyzer.get_file_context(mock_db_session, repository, file_path)
        
        assert result is not None
        assert result["file_path"] == file_path
        assert result["module_name"] == "test_service"
        assert "TestService" in result["class_names"]
        assert "get_test" in result["function_names"]
    
    @pytest.mark.asyncio
    async def test_get_file_context_analyze_new(self, analyzer, mock_db_session, sample_python_code):
        """Test analyzing new file when not in database."""
        repository = "test-repo"
        file_path = "app/services/new_service.py"
        
        # Mock no existing context
        mock_db_result = Mock()
        mock_db_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_db_result
        
        # Mock file reading
        with patch('builtins.open', mock_open(read_data=sample_python_code)):
            with patch('os.path.exists', return_value=True):
                result = await analyzer.get_file_context(mock_db_session, repository, file_path)
        
        assert result is not None
        assert result["file_path"] == file_path
        assert "TaskService" in result.get("classes", [])
        
        # Verify embedding was updated
        analyzer.embedding_service.update_code_context_embedding.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_directory(self, analyzer):
        """Test analyzing an entire directory."""
        directory = "/test/repo/src"
        
        # Mock file system
        mock_files = [
            "service1.py",
            "service2.py",
            "utils.js",
            "__pycache__/cache.pyc",  # Should be ignored
            "README.md"  # Should be ignored
        ]
        
        with patch('os.walk', return_value=[(directory, [], mock_files)]):
            with patch('os.path.join', side_effect=lambda d, f: f"{d}/{f}"):
                with patch.object(analyzer, 'analyze_file', new_callable=AsyncMock) as mock_analyze:
                    mock_analyze.return_value = {"file_path": "mocked", "classes": []}
                    
                    results = await analyzer.analyze_directory(directory, "test-repo")
        
        assert len(results) == 3  # Only .py and .js files
        assert mock_analyze.call_count == 3
    
    def test_extract_python_structure(self, analyzer, sample_python_code):
        """Test extracting structure from Python code."""
        result = analyzer._extract_python_structure(sample_python_code)
        
        assert "TaskService" in result["classes"]
        assert "get_tasks" in result["functions"]
        assert "create_task" in result["functions"]
        assert "_validate_task" in result["functions"]
        assert "helper_function" in result["functions"]
        assert "os" in result["imports"]
        assert "BaseService" in result["base_classes"]
        
        # Check method signatures
        assert any("user_id: int" in sig for sig in result.get("signatures", []))
    
    def test_extract_python_decorators(self, analyzer):
        """Test extracting decorators from Python code."""
        code_with_decorators = '''
from functools import lru_cache
from app.decorators import require_auth, rate_limit

class APIService:
    @require_auth
    @rate_limit(calls=100, period=3600)
    async def get_data(self, user_id: int):
        return {"data": "test"}
    
    @lru_cache(maxsize=128)
    def compute_expensive(self, value):
        return value * 2
    
    @property
    def is_ready(self):
        return True
'''
        
        result = analyzer._extract_python_structure(code_with_decorators)
        
        assert "require_auth" in str(result)
        assert "rate_limit" in str(result)
        assert "lru_cache" in str(result)
    
    def test_extract_javascript_structure(self, analyzer):
        """Test extracting structure from JavaScript code."""
        js_code = '''
// Modern JavaScript with various patterns
import { useState } from 'react';
const axios = require('axios');

export class UserService {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
    }
    
    async getUsers() {
        const response = await axios.get(`${this.apiUrl}/users`);
        return response.data;
    }
}

export const useUserData = () => {
    const [users, setUsers] = useState([]);
    
    const loadUsers = async () => {
        const service = new UserService('/api');
        const data = await service.getUsers();
        setUsers(data);
    };
    
    return { users, loadUsers };
};

export default function UserList({ users }) {
    return users.map(u => u.name);
}

module.exports = { UserService };
'''
        
        result = analyzer._extract_javascript_structure(js_code)
        
        assert "UserService" in result["classes"]
        assert "useUserData" in result["functions"]
        assert "UserList" in result["functions"]
        assert "getUsers" in result["functions"]
        assert "loadUsers" in result["functions"]
        assert "UserService" in result["exports"]
        assert "useUserData" in result["exports"]
        assert "react" in result["imports"]
        assert "axios" in result["imports"]
    
    def test_identify_design_patterns(self, analyzer):
        """Test identifying design patterns in code."""
        singleton_code = '''
class DatabaseConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
'''
        
        patterns = analyzer._identify_design_patterns(
            singleton_code, 
            {"classes": ["DatabaseConnection"]}
        )
        
        assert "Singleton" in patterns
        
        factory_code = '''
class AnimalFactory:
    @staticmethod
    def create_animal(animal_type):
        if animal_type == "dog":
            return Dog()
        elif animal_type == "cat":
            return Cat()
'''
        
        patterns = analyzer._identify_design_patterns(
            factory_code,
            {"classes": ["AnimalFactory"], "functions": ["create_animal"]}
        )
        
        assert "Factory" in patterns
        
        observer_code = '''
class Subject:
    def __init__(self):
        self._observers = []
    
    def attach(self, observer):
        self._observers.append(observer)
    
    def notify(self):
        for observer in self._observers:
            observer.update(self)
'''
        
        patterns = analyzer._identify_design_patterns(
            observer_code,
            {"classes": ["Subject"], "functions": ["attach", "notify"]}
        )
        
        assert "Observer" in patterns
    
    @pytest.mark.asyncio
    async def test_find_related_files(self, analyzer, mock_db_session, mock_embedding_service):
        """Test finding related files."""
        file_path = "app/services/user_service.py"
        repository = "test-repo"
        
        # Mock search results
        related_contexts = [
            (Mock(file_path="app/models/user.py", module_name="user"), 0.9),
            (Mock(file_path="app/api/users.py", module_name="users"), 0.85),
            (Mock(file_path="tests/test_user_service.py", module_name="test_user_service"), 0.8)
        ]
        
        mock_embedding_service.search_code_context.return_value = related_contexts
        
        # Mock file analysis
        file_info = {
            "imports": ["app.models.user", "app.core.auth"],
            "content_summary": "User service implementation"
        }
        
        related = await analyzer.find_related_files(
            mock_db_session, repository, file_path, file_info
        )
        
        assert len(related) == 3
        assert related[0]["file_path"] == "app/models/user.py"
        assert related[0]["relevance_score"] == 0.9
        assert related[0]["relationship_type"] == "imports"  # Because it's in imports
    
    def test_calculate_complexity_score(self, analyzer):
        """Test calculating code complexity score."""
        simple_code = '''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
'''
        
        simple_info = {
            "functions": ["add", "subtract"],
            "classes": [],
            "lines_of_code": 6
        }
        
        simple_score = analyzer._calculate_complexity_score(simple_code, simple_info)
        assert simple_score < 3  # Should be low complexity
        
        complex_code = '''
class ComplexProcessor:
    def process(self, data):
        if not data:
            return None
        
        result = []
        for item in data:
            if item.type == "A":
                if item.value > 100:
                    result.append(self._process_high_value(item))
                else:
                    result.append(self._process_low_value(item))
            elif item.type == "B":
                try:
                    processed = self._special_process(item)
                    if processed:
                        result.append(processed)
                except Exception as e:
                    if self.strict_mode:
                        raise
                    else:
                        self.log_error(e)
            else:
                for handler in self.handlers:
                    if handler.can_handle(item):
                        result.append(handler.process(item))
                        break
        
        return result if result else None
'''
        
        complex_info = {
            "functions": ["process", "_process_high_value", "_process_low_value"],
            "classes": ["ComplexProcessor"],
            "lines_of_code": 30
        }
        
        complex_score = analyzer._calculate_complexity_score(complex_code, complex_info)
        assert complex_score > 5  # Should be high complexity
    
    @pytest.mark.asyncio
    async def test_update_repository_context(self, analyzer, mock_db_session):
        """Test updating context for entire repository."""
        repository = "test-repo"
        
        # Mock directory analysis
        mock_files = [
            {"file_path": "app/models/user.py", "classes": ["User"]},
            {"file_path": "app/services/user_service.py", "classes": ["UserService"]},
            {"file_path": "app/api/users.py", "functions": ["get_users", "create_user"]}
        ]
        
        with patch.object(analyzer, 'analyze_directory', return_value=mock_files):
            summary = await analyzer.update_repository_context(
                mock_db_session, repository, "/repo/path"
            )
        
        assert summary["files_analyzed"] == 3
        assert summary["total_classes"] == 2
        assert summary["total_functions"] == 2
    
    def test_error_handling_invalid_python(self, analyzer):
        """Test handling invalid Python code."""
        invalid_code = '''
def broken_function(
    # Missing closing parenthesis
    return "broken"
'''
        
        result = analyzer._extract_python_structure(invalid_code)
        
        # Should handle gracefully
        assert isinstance(result, dict)
        assert "error" not in result  # Should not expose internal errors
    
    def test_error_handling_file_not_found(self, analyzer):
        """Test handling file not found errors."""
        import asyncio
        
        with patch('builtins.open', side_effect=FileNotFoundError("Not found")):
            # Run async function in sync test
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                analyzer.analyze_file("nonexistent.py", "repo")
            )
            loop.close()
        
        assert result["file_path"] == "nonexistent.py"
        assert result["error"] == "File not found"
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, analyzer, mock_db_session):
        """Test that context is cached appropriately."""
        repository = "test-repo"
        file_path = "app/cached_file.py"
        
        # First call - should hit database
        mock_context = create_code_context(file_path=file_path)
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_context
        
        result1 = await analyzer.get_file_context(mock_db_session, repository, file_path)
        assert mock_db_session.execute.call_count == 1
        
        # Second call - should still hit database (no in-memory cache)
        result2 = await analyzer.get_file_context(mock_db_session, repository, file_path)
        assert mock_db_session.execute.call_count == 2
        
        # Results should be the same
        assert result1["file_path"] == result2["file_path"]


def mock_open(*args, **kwargs):
    """Helper to create a mock for builtins.open."""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(*args, **kwargs)