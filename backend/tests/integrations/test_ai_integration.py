import logging
from datetime import datetime
from pathlib import Path

from app.integrations.ai_integration import AIIntegration

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_commit_analysis():
    """Test the commit analysis functionality."""
    ai = AIIntegration()

    # Sample commit data
    commit_data = {
        "commit_message": "Add user authentication and login functionality",
        "repository": "golfdaddy-app",
        "author": "john.doe@example.com",
        "files_changed": ["app/auth/login.py", "app/models/user.py", "app/templates/login.html"],
        "diff": """
        diff --git a/app/auth/login.py b/app/auth/login.py
        new file mode 100644
        index 0000000..1234567
        --- /dev/null
        +++ b/app/auth/login.py
        @@ -0,0 +1,50 @@
        +from flask import Blueprint, request, jsonify
        +from app.models.user import User
        +
        +login_bp = Blueprint('login', __name__)
        +
        +@login_bp.route('/login', methods=['POST'])
        +def login():
        +    data = request.get_json()
        +    user = User.query.filter_by(email=data['email']).first()
        +    if user and user.check_password(data['password']):
        +        return jsonify({'message': 'Login successful'})
        +    return jsonify({'error': 'Invalid credentials'}), 401
        """,
    }

    logger.info("Testing commit analysis...")
    result = ai.analyze_commit_diff(commit_data)
    logger.info(f"Commit analysis result: {result}")
    return result


def test_doc_generation():
    """Test the documentation generation functionality."""
    ai = AIIntegration()

    # Sample context for documentation
    context = {
        "text": """
        The GolfDaddy application is a comprehensive golf management system that helps users track their golf games,
        manage their equipment, and improve their skills. The system includes features for:
        - Score tracking
        - Equipment management
        - Performance analytics
        - Course information
        """,
        "file_references": ["app/models/game.py", "app/services/analytics.py", "app/templates/dashboard.html"],
        "doc_type": "api",
        "format": "markdown",
    }

    logger.info("Testing documentation generation...")
    result = ai.generate_doc(context)
    logger.info(f"Documentation generation result: {result}")
    return result


if __name__ == "__main__":
    # Run all tests
    logger.info("Starting AI Integration tests...")

    # Test commit analysis
    commit_result = test_commit_analysis()
    logger.info("Commit analysis test completed")

    # Test documentation generation
    doc_result = test_doc_generation()
    logger.info("Documentation generation test completed")

    logger.info("All tests completed")
