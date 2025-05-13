import os
import uuid
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio

from app.models.task import Task
from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository
from app.services.notification_service import NotificationService
from app.services.raci_service import RACIService
from app.config.settings import settings
from app.integrations.ai_integration import AIIntegration
from app.models.user import User as UserModel

from app.core.exceptions import (
    ResourceNotFoundError,
    AIIntegrationError,
    DatabaseError,
    BadRequestError,
    AppExceptionBase
)

logger = logging.getLogger(__name__)

# Development areas for managers
DEVELOPMENT_AREAS = [
    "strategic_thinking",
    "team_leadership",
    "communication",
    "decision_making",
    "conflict_resolution",
    "delegation",
    "coaching",
    "feedback_delivery",
    "business_acumen",
    "change_management"
]

# Task types specific to manager development
MANAGER_DEV_TASK_TYPE_KEY = "manager_development"

TASK_SUB_TYPES = {
    "milestone": "Assessment and goal-setting tasks",
    "skill_practice": "Skill practice and implementation tasks",
    "feedback_coaching": "Observation and coaching tasks"
}

class ManagerDevelopmentService:
    """
    Service for creating, managing, and tracking manager development tasks
    with full RACI implementation.
    
    This service integrates with AI to generate personalized development 
    content and uses the notification service to keep all stakeholders
    informed according to RACI principles.
    """
    
    def __init__(
        self,
        task_repository: TaskRepository,
        user_repository: UserRepository,
        notification_service: NotificationService,
        raci_service: RACIService,
        ai_integration: AIIntegration
    ):
        self.task_repository = task_repository
        self.user_repository = user_repository
        self.notification_service = notification_service
        self.raci_service = raci_service
        self.ai_integration = ai_integration
    
    async def _generate_task_content_from_ai(
        self,
        manager_name: str,
        development_area: str,
        task_sub_type: str
    ) -> Dict[str, Any]:
        """
        Generates task content (title, description, and metadata) using AI.
        Metadata includes learning_objectives, suggested_resources, success_metrics.
        """
        try:
            logger.info(f"Generating AI content for manager {manager_name}, area: {development_area}, type: {task_sub_type}")
            ai_content = await self.ai_integration.generate_development_task_content(
                manager_name=manager_name,
                development_area=development_area,
                task_type=task_sub_type,
            )
            
            title = f"{development_area.replace('_', ' ').title()} - {task_sub_type.replace('_', ' ').title()}"
            
            if not ai_content.get("description"):
                 logger.warning(f"AI did not return a description for {development_area} - {task_sub_type}. Using a placeholder.")
                 ai_content["description"] = f"Placeholder task for {development_area} ({task_sub_type}). Please define clear objectives and actions."

            task_metadata = {
                "development_area": development_area,
                "task_sub_type": task_sub_type,
                "learning_objectives": ai_content.get("learning_objectives", ["Define specific learning objectives."]),
                "suggested_resources": ai_content.get("suggested_resources", ["Identify relevant resources."]),
                "success_metrics": ai_content.get("success_metrics", ["Define clear success metrics."])
            }
            
            return {
                "title": title,
                "description": ai_content["description"],
                "metadata": task_metadata
            }
            
        except Exception as e:
            logger.error(f"AI content generation failed for {development_area} ({task_sub_type}): {e}", exc_info=True)
            default_title = f"{development_area.replace('_', ' ').title()} - {task_sub_type.replace('_', ' ').title()} (Error)"
            return {
                "title": default_title,
                "description": f"Error generating AI content. Please manually define this {task_sub_type} task for the {development_area} development area.",
                "metadata": {
                    "development_area": development_area,
                    "task_sub_type": task_sub_type,
                    "learning_objectives": ["Error: Define objectives"],
                    "suggested_resources": ["Error: Define resources"],
                    "success_metrics": ["Error: Define metrics"],
                    "ai_error": str(e)
                }
            }

    async def _determine_raci_user_ids(
        self,
        task_sub_type: str, 
        manager: UserModel, 
        director: UserModel,
    ) -> Dict[str, Any]:
        """
        Determines the User IDs for R, A, C, I roles based on task type and hierarchy.
        Returns a dictionary with keys: responsible_id, accountable_id, consulted_ids, informed_ids.
        """
        manager_id = manager.id
        director_id = director.id
        
        direct_reports_users = await self.user_repository.get_direct_reports(manager_id)
        peer_users = await self.user_repository.get_peers(manager_id)
        
        direct_report_ids = [u.id for u in direct_reports_users]
        peer_ids = [u.id for u in peer_users][:2]

        raci_user_ids = {
            "responsible_id": None, "accountable_id": None,
            "consulted_ids": [], "informed_ids": []
        }

        if task_sub_type == "milestone":
            raci_user_ids["responsible_id"] = manager_id
            raci_user_ids["accountable_id"] = director_id
            raci_user_ids["consulted_ids"] = peer_ids
            raci_user_ids["informed_ids"] = direct_report_ids[:3] 
        elif task_sub_type == "skill_practice":
            raci_user_ids["responsible_id"] = manager_id
            raci_user_ids["accountable_id"] = manager_id 
            raci_user_ids["consulted_ids"] = [director_id] + peer_ids
            raci_user_ids["informed_ids"] = direct_report_ids[:3]
        elif task_sub_type == "feedback_coaching":
            raci_user_ids["responsible_id"] = director_id
            raci_user_ids["accountable_id"] = director_id
            raci_user_ids["consulted_ids"] = [manager_id]
            raci_user_ids["informed_ids"] = peer_ids 
        else:
            logger.warning(f"Unknown task sub-type '{task_sub_type}' for RACI determination. Defaulting R&A to manager.")
            raci_user_ids["responsible_id"] = manager_id
            raci_user_ids["accountable_id"] = manager_id

        return raci_user_ids

    async def create_development_task(
        self,
        task_sub_type: str,
        development_area: str,
        manager_user_id: uuid.UUID,
        creator_user_id: uuid.UUID,
        custom_title: Optional[str] = None,
        custom_description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        director_user_id: Optional[uuid.UUID] = None
    ) -> Task:
        """
        Creates a single management development task.
        """
        logger.info(f"Creating development task: Area='{development_area}', SubType='{task_sub_type}' for Manager ID {manager_user_id}")

        if task_sub_type not in TASK_SUB_TYPES:
            raise BadRequestError(f"Invalid task sub_type: {task_sub_type}. Must be one of: {', '.join(TASK_SUB_TYPES.keys())}")
        if development_area not in DEVELOPMENT_AREAS:
            raise BadRequestError(f"Invalid development area: {development_area}.")

        manager = await self.user_repository.get_user_by_id(manager_user_id)
        if not manager:
            raise ResourceNotFoundError(resource_name="Manager", resource_id=str(manager_user_id))

        creator = await self.user_repository.get_user_by_id(creator_user_id)
        if not creator:
            raise ResourceNotFoundError(resource_name="Creator", resource_id=str(creator_user_id))

        if director_user_id:
            director = await self.user_repository.get_user_by_id(director_user_id)
            if not director:
                raise ResourceNotFoundError(resource_name="Director", resource_id=str(director_user_id))
        else:
            director = await self.user_repository.get_director_for_manager(manager_user_id)
            if not director:
                 logger.warning(f"No director ID provided and director not found for manager {manager_user_id}. Plan creation will proceed.")
        
        if custom_title and custom_description:
            title = custom_title
            description = custom_description
            metadata = {
                "development_area": development_area,
                "task_sub_type": task_sub_type,
                "learning_objectives": ["Manually defined objectives if any"],
                "suggested_resources": ["Manually defined resources if any"],
                "success_metrics": ["Manually defined success metrics if any"]
            }
        else:
            generated_content = await self._generate_task_content_from_ai(
                manager_name=getattr(manager, 'name', 'The Manager'), 
                development_area=development_area,
                task_sub_type=task_sub_type
            )
            title = custom_title or generated_content["title"]
            description = custom_description or generated_content["description"]
            metadata = generated_content["metadata"]
        
        if not due_date:
            due_date = datetime.now() + timedelta(weeks=1)

        raci_user_ids = await self._determine_raci_user_ids(
            task_sub_type, manager, director if director else manager
        )
        
        created_task_tuple = await self.raci_service.register_raci_assignments(
            title=title,
            description=description,
            assignee_id=manager.id,
            creator_id=creator.id,
            responsible_id=raci_user_ids["responsible_id"],
            accountable_id=raci_user_ids["accountable_id"],
            consulted_ids=raci_user_ids["consulted_ids"],
            informed_ids=raci_user_ids["informed_ids"],
            due_date=due_date,
            task_type=MANAGER_DEV_TASK_TYPE_KEY,
            metadata=metadata
        )
        
        created_task = created_task_tuple[0]
        warnings = created_task_tuple[1]

        if not created_task:
            logger.error(f"Failed to create development task via RACI service for manager {manager_user_id}, area {development_area}.")
            raise DatabaseError("Failed to save development task via RACI service.")
        
        if warnings:
            logger.warning(f"Task {created_task.id} created with warnings: {warnings}")

        await self.notification_service.task_created_notification(created_task, creator_id=creator.id)
        
        logger.info(f"Successfully created development task {created_task.id} for manager {manager.id}")
        return created_task

    async def create_development_plan(
        self,
        manager_user_id: uuid.UUID,
        creator_user_id: uuid.UUID,
        development_areas: List[str],
        director_user_id: Optional[uuid.UUID] = None
    ) -> List[Task]:
        """
        Creates a development plan consisting of multiple tasks for a manager.
        """
        logger.info(f"Creating development plan for Manager ID {manager_user_id} in areas: {', '.join(development_areas)}")
        manager = await self.user_repository.get_user_by_id(manager_user_id)
        if not manager:
            raise ResourceNotFoundError(resource_name="Manager", resource_id=str(manager_user_id))
        
        creator = await self.user_repository.get_user_by_id(creator_user_id)
        if not creator:
            raise ResourceNotFoundError(resource_name="Creator", resource_id=str(creator_user_id))

        director = None
        if director_user_id:
            director = await self.user_repository.get_user_by_id(director_user_id)
            if not director:
                logger.warning(f"Director with ID {director_user_id} not found. Plan creation will proceed, RACI might be affected for some tasks.")
        else:
            director = await self.user_repository.get_director_for_manager(manager_user_id)
            if not director:
                 logger.warning(f"No director ID provided and director not found for manager {manager_user_id}. Plan creation will proceed.")
        
        created_tasks: List[Task] = []
        base_due_date = datetime.now()

        for i, area in enumerate(development_areas):
            if area not in DEVELOPMENT_AREAS:
                logger.warning(f"Skipping invalid development area '{area}' in plan for manager {manager_user_id}")
                continue
            
            for j, (sub_type_key, sub_type_desc) in enumerate(TASK_SUB_TYPES.items()):
                task_due_date = base_due_date + timedelta(weeks=(i * len(TASK_SUB_TYPES)) + j + 1) 
                
                try:
                    task = await self.create_development_task(
                        task_sub_type=sub_type_key,
                        development_area=area,
                        manager_user_id=manager.id,
                        creator_user_id=creator.id,
                        due_date=task_due_date,
                        director_user_id=director.id if director else None
                    )
                    created_tasks.append(task)
                except Exception as e:
                    logger.error(f"Failed to create task for area '{area}', sub-type '{sub_type_key}' for manager {manager_user_id}: {e}", exc_info=True)

        if not created_tasks:
            logger.warning(f"No tasks were created for the development plan for manager {manager_user_id}.")
            return []

        logger.info(f"Created development plan with {len(created_tasks)} tasks for manager {manager.id}")
        
        plan_link_placeholder = f"/user/{manager.id}/development-plan/{datetime.now().strftime('%Y%m%d')}" 
        await self.notification_service.send_development_plan_notification(
            manager_user_id=manager.id, 
            development_areas=development_areas,
            num_tasks_created=len(created_tasks),
            plan_link=plan_link_placeholder 
        )
        
        return created_tasks
    
    async def update_task_progress(
        self,
        task_id: uuid.UUID,
        progress: int,
        updater_user_id: uuid.UUID,
        update_notes: Optional[str] = None
    ) -> Task:
        """
        Updates the progress of a development task.
        """
        logger.info(f"Updating progress for task {task_id} to {progress}% by user {updater_user_id}")
        if not 0 <= progress <= 100:
            raise BadRequestError("Progress must be between 0 and 100")
            
        task_to_update = await self.task_repository.get_task_by_id(task_id)
        if not task_to_update:
            raise ResourceNotFoundError(resource_name="Task", resource_id=str(task_id))
            
        if task_to_update.task_type != MANAGER_DEV_TASK_TYPE_KEY:
            raise BadRequestError(f"Task {task_id} is not a manager development task. Current type: {task_to_update.task_type}")
            
        updater = await self.user_repository.get_user_by_id(updater_user_id)
        if not updater:
            raise ResourceNotFoundError(resource_name="Updater User", resource_id=str(updater_user_id))

        update_payload: Dict[str, Any] = {"metadata": task_to_update.metadata.copy() if task_to_update.metadata else {}}
        
        update_payload["metadata"]["progress"] = progress 
        update_payload["metadata"]["last_progress_update_by"] = str(updater.id)
        update_payload["metadata"]["last_progress_update_at"] = datetime.now().isoformat()

        if update_notes:
            if "progress_notes" not in update_payload["metadata"]:
                update_payload["metadata"]["progress_notes"] = []
            update_payload["metadata"]["progress_notes"].append({
                "note": update_notes,
                "updated_by": str(updater.id),
                "updated_at": datetime.now().isoformat()
            })
        
        if progress == 100:
            update_payload["status"] = "completed"
        elif progress > 0 and task_to_update.status.value == "assigned":
             update_payload["status"] = "in_progress"

        updated_task = await self.task_repository.update_task(task_id, update_payload)
        if not updated_task:
            logger.error(f"Failed to update task {task_id} progress in repository.")
            raise DatabaseError(f"Failed to update task {task_id} progress in repository.")
        
        logger.info(f"Task {updated_task.id} progress updated to {progress}%. Status: {updated_task.status.value}")

        if updated_task.status.value == "completed":
            if updated_task.accountable_id:
                accountable_user = await self.user_repository.get_user_by_id(updated_task.accountable_id)
                if accountable_user and accountable_user.slack_id:
                    logger.info(f"Placeholder: Notifying accountable user {accountable_user.id} about task {updated_task.id} completion.")

            if updated_task.informed_ids:
                for informed_id in updated_task.informed_ids:
                    informed_user = await self.user_repository.get_user_by_id(informed_id)
                    if informed_user and informed_user.slack_id:
                        logger.info(f"Placeholder: Notifying informed user {informed_user.id} about task {updated_task.id} completion.")
        
        return updated_task

    async def generate_feedback(
        self,
        manager_id: str,
        development_area: str,
        context_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates AI-powered feedback for a manager in a specific development area.
        
        Args:
            manager_id: ID of the manager
            development_area: Area to provide feedback on
            context_notes: Optional context or observations
            
        Returns:
            Dictionary containing structured feedback
        """
        manager = await self.user_repository.get_user_by_id(manager_id)
        if not manager:
            raise ResourceNotFoundError(resource_name="Manager", resource_id=manager_id)
            
        recent_tasks = await self.task_repository.get_tasks_by_user_and_area(
            manager_id, development_area, limit=5
        )
        
        manager_name = manager.get("name", "the manager")
        manager_role = manager.get("role", "manager")
        recent_task_titles = [task.get("title", "") for task in recent_tasks]
        recent_progress = [task.get("progress", 0) for task in recent_tasks]
        
        prompt = self._create_feedback_prompt(
            manager_name,
            manager_role,
            development_area,
            recent_task_titles,
            recent_progress,
            context_notes
        )
        
        try:
            ai_response = await self.ai_integration.generate_text(prompt)
        except Exception as ai_exc:
            logger.error(f"AI integration error generating feedback for manager {manager_id}: {ai_exc}", exc_info=True)
            raise AIIntegrationError(f"Failed to generate feedback due to AI service error: {str(ai_exc)}")
        
        try:
            feedback = self._process_feedback_response(ai_response, development_area)
            logger.info(f"Generated feedback for manager {manager_id} in area: {development_area}")
            return feedback
        except ValueError as ve:
            logger.error(f"Failed to process AI feedback response for manager {manager_id}: {ve}", exc_info=True)
            raise AIIntegrationError(f"Failed to structure AI feedback: {str(ve)}")
    
    async def get_manager_development_summary(
        self, 
        manager_id: str
    ) -> Dict[str, Any]:
        """
        Provides a summary of a manager's development across all areas.
        
        Args:
            manager_id: ID of the manager
            
        Returns:
            Summary of development progress
        """
        manager = await self.user_repository.get_user_by_id(manager_id)
        if not manager:
            raise ResourceNotFoundError(resource_name="Manager", resource_id=manager_id)
            
        all_tasks = await self.task_repository.get_tasks_for_user(manager_id)
        
        tasks_by_area = {}
        for area in DEVELOPMENT_AREAS:
            tasks_by_area[area] = []
            
        for task in all_tasks:
            if "development_area" in task and task["development_area"] in DEVELOPMENT_AREAS:
                tasks_by_area[task["development_area"]].append(task)
        
        area_progress = {}
        for area, tasks in tasks_by_area.items():
            if not tasks:
                area_progress[area] = 0
            else:
                total_progress = sum(task.get("progress", 0) for task in tasks)
                area_progress[area] = total_progress / (len(tasks) * 100) * 100 if tasks else 0
        
        total_progress = sum(area_progress.values())
        overall_progress = total_progress / len(DEVELOPMENT_AREAS) if DEVELOPMENT_AREAS else 0
        
        strengths = sorted(area_progress.items(), key=lambda x: x[1], reverse=True)[:3]
        weaknesses = sorted(area_progress.items(), key=lambda x: x[1])[:3]
        
        summary = {
            "manager_id": manager_id,
            "manager_name": manager.get("name", ""),
            "overall_progress": overall_progress,
            "area_progress": area_progress,
            "strengths": [area for area, _ in strengths],
            "improvement_areas": [area for area, _ in weaknesses],
            "total_tasks": len(all_tasks),
            "completed_tasks": sum(1 for task in all_tasks if task.get("status") == "completed"),
            "in_progress_tasks": sum(1 for task in all_tasks if task.get("status") == "in_progress"),
            "pending_tasks": sum(1 for task in all_tasks if task.get("status") == "created")
        }
        
        return summary
    
    def _create_feedback_prompt(
        self,
        manager_name: str,
        manager_role: str,
        development_area: str,
        recent_task_titles: List[str],
        recent_progress: List[int],
        context_notes: Optional[str]
    ) -> str:
        """
        Creates a detailed prompt for AI feedback generation.
        """
        area_display = development_area.replace("_", " ")
        
        context = f"The manager has recently worked on: {', '.join(recent_task_titles)}" if recent_task_titles else ""
        
        if context_notes:
            context += f"\n\nAdditional context: {context_notes}"
        
        progress_info = ""
        if recent_progress:
            avg_progress = sum(recent_progress) / len(recent_progress)
            progress_info = f"The manager has made approximately {avg_progress:.1f}% progress on recent tasks."
        
        prompt = f"""
        Generate professional feedback for {manager_name}, who is in a {manager_role} role.
        Focus specifically on their '{area_display}' capabilities.
        
        {context}
        
        {progress_info}
        
        Provide:
        1. A brief summary of strengths in this area
        2. 2-3 specific areas for improvement
        3. 3-5 actionable suggestions with specific techniques or approaches
        4. A recommended timeline for implementing changes
        
        Format the response as JSON with the following fields:
        - strengths: An array of strength statements
        - improvement_areas: An array of areas needing improvement
        - suggestions: An array of specific actionable suggestions
        - timeline: A string describing the recommended implementation timeline
        """
        
        return prompt
    
    def _process_feedback_response(
        self,
        ai_response: str,
        development_area: str
    ) -> Dict[str, Any]:
        """
        Processes AI response into structured feedback.
        """
        try:
            feedback_data = json.loads(ai_response)
            
            required_fields = ["strengths", "improvement_areas", "suggestions", "timeline"]
            for field in required_fields:
                if field not in feedback_data:
                    logger.warning(f"AI feedback response for area {development_area} missing field: {field}. Raw: {ai_response[:200]}")
                    raise ValueError(f"AI response missing required field: {field}")
            
            feedback_data["generated_at"] = datetime.now().isoformat()
            feedback_data["development_area"] = development_area
            
            return feedback_data
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"AI feedback response for {development_area} not valid JSON or missing fields: {str(e)}. Raw: {ai_response[:200]}", exc_info=True)
            raise AIIntegrationError(f"AI response for feedback was not valid JSON or had missing fields.") 