from typing import Dict, Any, Optional, List
import requests
import json
import os
from datetime import datetime
import openai
from openai import OpenAI
from openai.types.chat import ChatCompletion

from app.config.settings import settings
from app.integrations.commit_analysis import CommitAnalyzer

class AIIntegration:
    """Integration with OpenAI API for documentation generation."""
    
    def __init__(self):
        """Initialize the OpenAI integration with API key from settings."""
        self.api_key = settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key not configured in settings")
            
        self.client = OpenAI(api_key=self.api_key)
        self.model = settings.openai_model or "gpt-4-0125-preview"  # Use settings or fallback to latest model
        
        # Models that don't support temperature parameter (typically reasoning/embedding models)
        self.reasoning_models = [
            "o3-mini-", 
            "text-embedding-",
            "-e-",
            "text-search-"
        ]
        
        # Initialize the commit analyzer
        self.commit_analyzer = CommitAnalyzer()
    
    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if the model is a reasoning model that doesn't support temperature."""
        return any(prefix in model_name for prefix in self.reasoning_models)
    
    def analyze_commit_diff(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit diff using OpenAI to provide insights and estimates.
        
        This method delegates to the CommitAnalyzer class.
        
        Args:
            commit_data: Dictionary containing commit information from GitHub
                
        Returns:
            Dictionary with analysis results
        """
        return self.commit_analyzer.analyze_commit_diff(commit_data)
    
    def generate_doc(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate documentation using OpenAI's API.
        
        Args:
            context: Dictionary containing:
                - text: The text to use as context
                - file_references: Optional list of file contents
                - doc_type: Type of documentation to generate
                - format: Output format (markdown, html, etc.)
                - commit_data: Optional commit data from GitHub integration
                
        Returns:
            Dictionary with generated documentation
        """
        try:
            # Prepare the prompt for documentation generation
            prompt = f"""Generate comprehensive documentation for the following context and provide a JSON response.

            Please format your response as a JSON object with the following structure:
            {{
                "content": <string>,
                "format": <string>,
                "sections": [
                    {{
                        "title": <string>,
                        "content": <string>
                    }}
                ],
                "metadata": {{
                    "generated_at": <timestamp>,
                    "doc_type": <string>,
                    "format": <string>
                }}
            }}

            Documentation Type: {context.get('doc_type', 'general')}
            Format: {context.get('format', 'markdown')}
            
            Context:
            {context.get('text', '')}
            
            File References:
            {json.dumps(context.get('file_references', []), indent=2)}"""

            # Add commit information if available
            if commit_data := context.get('commit_data'):
                prompt += f"""
                
                Commit Information:
                Repository: {commit_data.get('repository', '')}
                Author: {commit_data.get('author_name', '')}
                Message: {commit_data.get('message', '')}
                Files Changed: {', '.join(commit_data.get('files_changed', []))}
                """

            # Set up parameters for the API call
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an expert technical writer and documentation specialist. Focus on clarity, completeness, and technical accuracy."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            
            # Only add temperature for models that support it
            if not self._is_reasoning_model(self.model):
                api_params["temperature"] = 0.7  # Higher temperature for more creative documentation
            
            # Make API call to OpenAI with structured output
            response = self.client.chat.completions.create(**api_params)
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            return {
                **result,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return self.error_handling(e)
    
    def error_handling(self, error: Exception) -> Dict[str, Any]:
        """
        Handle errors from OpenAI API.
        
        Args:
            error: The error that occurred
            
        Returns:
            Dictionary with error details
        """
        error_message = str(error)
        
        # Log the error (in a real implementation)
        print(f"OpenAI API Error: {error_message}")
        
        return {
            "error": True,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }