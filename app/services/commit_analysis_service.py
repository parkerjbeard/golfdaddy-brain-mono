from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import math
import json

from app.repositories.commit_repository import CommitRepository
from app.repositories.user_repository import UserRepository
from app.integrations.ai_integration import AIIntegration

class CommitAnalysisService:
    """Service for analyzing commits and calculating points."""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.commit_repository = CommitRepository(db) if db else None
        self.user_repository = UserRepository(db) if db else None
        self.ai_integration = AIIntegration()
        
        # Simplified point calculation weights
        self.complexity_weight = 2.0  # Base weight for complexity score
        
        # Simplified risk factors - used only for minor adjustments
        self.risk_factors = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5
        }
    
    def analyze_commits(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a commit and calculate points based on AI assessment.
        
        Args:
            commit_data: Dictionary with commit information
            
        Returns:
            Dictionary with analysis results and calculated points
        """
        try:
            # Get AI analysis of the commit
            ai_result = self.ai_integration.analyze_commit_diff(commit_data)
            
            if "error" in ai_result:
                return {"error": True, "message": ai_result.get("message")}
            
            # Extract key metrics from AI analysis - set default values if not found
            complexity_score = ai_result.get("complexity_score", 5)
            risk_level = ai_result.get("risk_level", "medium").lower()  # Normalize to lowercase
            estimated_hours = ai_result.get("estimated_hours", 4)
            
            # Calculate simplified points based primarily on AI assessment
            # This puts more weight on the AI's direct assessment
            points = complexity_score * self.complexity_weight
            
            # Apply minimal risk adjustment (no need to overcomplicate)
            risk_factor = self.risk_factors.get(risk_level, 1.0)
            
            # Final points with minimal risk adjustment
            final_points = points * risk_factor
            
            # Use the AI's estimated hours directly with only risk adjustment
            # Only apply the risk factor for medium/high risk tasks
            # For low risk tasks, we trust the AI's estimate completely
            if risk_level == "low":
                adjusted_hours = estimated_hours  # No adjustment for low risk
            else:
                adjusted_hours = estimated_hours * risk_factor
            
            # Round hours to nearest 0.5 for readability
            adjusted_hours = round(adjusted_hours * 2) / 2
            
            # Create point calculation details for transparency
            point_calculation = {
                "complexity_component": {
                    "score": complexity_score,
                    "weight": self.complexity_weight,
                    "points": complexity_score * self.complexity_weight
                },
                "risk_component": {
                    "level": risk_level,
                    "factor": risk_factor,
                    "points": 0  # No separate points, just a multiplier now
                },
                "total_points": final_points
            }
            
            # Format the analysis result
            analysis = {
                "ai_points": round(final_points, 2),
                "ai_estimated_hours": adjusted_hours,
                "complexity_score": complexity_score,
                "risk_level": risk_level,
                "risk_factor": risk_factor,
                "point_calculation": point_calculation,
                "ai_analysis_notes": {
                    "key_changes": ai_result.get("key_changes", []),
                    "technical_debt": ai_result.get("technical_debt", []),
                    "suggestions": ai_result.get("suggestions", [])
                }
            }
            
            return {
                "commit_hash": commit_data.get("commit_hash"),
                "analysis": analysis
            }
            
        except Exception as e:
            return {
                "error": True,
                "message": str(e)
            }
    
    def store_analysis_results(self, commit_hash: str, analysis_results: Dict[str, Any]) -> bool:
        """
        Store analysis results for an existing commit.
        
        Args:
            commit_hash: The commit hash
            analysis_results: The analysis results to store
            
        Returns:
            Boolean indicating success
        """
        if not self.commit_repository:
            return False
            
        commit = self.commit_repository.get_commit_by_hash(commit_hash)
        
        if not commit:
            return False
        
        # Update the commit with analysis results
        self.commit_repository.save_commit(
            commit_hash=commit_hash,
            author_id=commit.author_id,
            repository=commit.repository,
            branch=commit.branch,
            commit_message=commit.commit_message,
            commit_timestamp=commit.commit_timestamp,
            **analysis_results
        )
        
        return True
    
    def batch_processing(self, commits_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple commits in a single batch.
        
        Args:
            commits_data: List of commit data dictionaries
            
        Returns:
            List of analysis results
        """
        results = []
        
        for commit_data in commits_data:
            # Process each commit
            result = self.analyze_commits(commit_data)
            results.append(result)
        
        return results