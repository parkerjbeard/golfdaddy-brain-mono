"""
Slack message templates using Block Kit for rich formatting.
Replaces Make.com webhook message formatting.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime


class SlackMessageTemplates:
    """Templates for various Slack notification types using Block Kit."""
    
    @staticmethod
    def task_created(
        task_name: str,
        task_id: str,
        responsible_user_id: str,
        accountable_user_id: str,
        priority: str,
        due_date: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Template for task created notification."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🆕 New Task Created",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Task:*\n{task_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Priority:*\n{priority.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Responsible:*\n<@{responsible_user_id}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Accountable:*\n<@{accountable_user_id}>"
                    }
                ]
            }
        ]
        
        if description:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{description}"
                }
            })
        
        if due_date:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📅 Due: {due_date.strftime('%B %d, %Y')}"
                    }
                ]
            })
        
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Task",
                        "emoji": True
                    },
                    "url": f"{settings.FRONTEND_URL}/tasks/{task_id}",
                    "style": "primary"
                }
            ]
        })
        
        return {
            "text": f"New task created: {task_name}",
            "blocks": blocks
        }
    
    @staticmethod
    def task_blocked(
        task_name: str,
        task_id: str,
        blocked_by_user_id: str,
        responsible_user_id: str,
        accountable_user_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Template for task blocked notification."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚫 Task Blocked",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{task_name}* has been blocked"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Blocked by:*\n<@{blocked_by_user_id}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Responsible:*\n<@{responsible_user_id}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Accountable:*\n<@{accountable_user_id}>"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Reason:*\n{reason}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Task",
                            "emoji": True
                        },
                        "url": f"{settings.FRONTEND_URL}/tasks/{task_id}",
                        "style": "danger"
                    }
                ]
            }
        ]
        
        return {
            "text": f"Task blocked: {task_name}",
            "blocks": blocks
        }
    
    @staticmethod
    def eod_reminder(
        user_id: str,
        pending_tasks: List[Dict[str, Any]],
        completed_today: int = 0
    ) -> Dict[str, Any]:
        """Template for end-of-day reminder."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🌅 End of Day Summary",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Hey <@{user_id}>! Here's your daily wrap-up:"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*✅ Completed Today:*\n{completed_today} tasks"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*📋 Pending Tasks:*\n{len(pending_tasks)} tasks"
                    }
                ]
            }
        ]
        
        if pending_tasks:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Your pending tasks:*"
                }
            })
            
            for task in pending_tasks[:5]:  # Show max 5 tasks
                priority_emoji = {
                    "URGENT": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🟢"
                }.get(task.get("priority", "MEDIUM"), "🟡")
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{priority_emoji} *{task['name']}*\n_{task.get('status', 'pending')}_"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View",
                            "emoji": True
                        },
                        "url": f"{settings.FRONTEND_URL}/tasks/{task['id']}"
                    }
                })
            
            if len(pending_tasks) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_... and {len(pending_tasks) - 5} more tasks_"
                        }
                    ]
                })
        
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Dashboard",
                        "emoji": True
                    },
                    "url": f"{settings.FRONTEND_URL}/dashboard",
                    "style": "primary"
                }
            ]
        })
        
        return {
            "text": f"End of day summary: {completed_today} completed, {len(pending_tasks)} pending",
            "blocks": blocks
        }
    
    @staticmethod
    def personal_mastery_reminder(
        user_id: str,
        skill_area: str,
        learning_goal: str,
        resources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Template for personal mastery reminder."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎯 Personal Mastery Reminder",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}>, time to invest in your growth! 🌱"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Skill Area:*\n{skill_area}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Today's Goal:*\n{learning_goal}"
                    }
                ]
            }
        ]
        
        if resources:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📚 Suggested Resources:*"
                }
            })
            
            for resource in resources[:3]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• {resource}"
                    }
                })
        
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Mark as Complete",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "mastery_complete"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Snooze",
                        "emoji": True
                    },
                    "action_id": "mastery_snooze"
                }
            ]
        })
        
        return {
            "text": f"Personal mastery reminder: {skill_area}",
            "blocks": blocks
        }
    
    @staticmethod
    def development_plan_created(
        user_id: str,
        manager_user_id: str,
        plan_name: str,
        objectives: List[str],
        timeline: str
    ) -> Dict[str, Any]:
        """Template for development plan created notification."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📈 New Development Plan",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}>, a new development plan has been created for you by <@{manager_user_id}>"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Plan:*\n{plan_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timeline:*\n{timeline}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Key Objectives:*"
                }
            }
        ]
        
        for i, objective in enumerate(objectives[:5], 1):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{i}. {objective}"
                }
            })
        
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Full Plan",
                        "emoji": True
                    },
                    "url": f"{settings.FRONTEND_URL}/development-plan",
                    "style": "primary"
                }
            ]
        })
        
        return {
            "text": f"New development plan created: {plan_name}",
            "blocks": blocks
        }
    
    @staticmethod
    def documentation_proposal(
        author_user_id: str,
        commit_sha: str,
        commit_message: str,
        proposed_updates: List[Dict[str, str]],
        pr_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Template for documentation update proposal."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📝 Documentation Update Proposal",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{author_user_id}>, based on your recent commit, we've identified potential documentation updates:"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Commit:*\n`{commit_sha[:8]}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Message:*\n_{commit_message}_"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📋 Proposed Updates:*"
                }
            }
        ]
        
        for update in proposed_updates[:3]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{update['file']}*\n{update['description']}"
                }
            })
        
        if len(proposed_updates) > 3:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_... and {len(proposed_updates) - 3} more updates_"
                    }
                ]
            })
        
        actions = []
        if pr_url:
            actions.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Review PR",
                    "emoji": True
                },
                "url": pr_url,
                "style": "primary"
            })
        
        actions.extend([
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Approve",
                    "emoji": True
                },
                "style": "primary",
                "action_id": "approve_docs"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Suggest Changes",
                    "emoji": True
                },
                "action_id": "suggest_changes"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Dismiss",
                    "emoji": True
                },
                "style": "danger",
                "action_id": "dismiss_docs"
            }
        ])
        
        blocks.append({
            "type": "actions",
            "elements": actions
        })
        
        return {
            "text": f"Documentation update proposal for commit {commit_sha[:8]}",
            "blocks": blocks
        }
    
    @staticmethod
    def commit_analysis_summary(
        author_user_id: str,
        commit_sha: str,
        estimated_points: int,
        estimated_hours: float,
        complexity: str,
        impact_areas: List[str]
    ) -> Dict[str, Any]:
        """Template for commit analysis summary."""
        complexity_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "very_high": "🔴"
        }.get(complexity.lower(), "🟡")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔍 Commit Analysis Complete",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{author_user_id}>, here's the analysis of your commit `{commit_sha[:8]}`:"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Estimated Points:*\n{estimated_points}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Estimated Hours:*\n{estimated_hours:.1f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Complexity:*\n{complexity_emoji} {complexity.title()}"
                    }
                ]
            }
        ]
        
        if impact_areas:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Impact Areas:*\n" + "\n".join([f"• {area}" for area in impact_areas[:5]])
                }
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_This analysis helps track development velocity and plan future work._"
                }
            ]
        })
        
        return {
            "text": f"Commit analysis: {estimated_points} points, {estimated_hours:.1f} hours",
            "blocks": blocks
        }


# Import settings for URL construction
from app.config.settings import settings