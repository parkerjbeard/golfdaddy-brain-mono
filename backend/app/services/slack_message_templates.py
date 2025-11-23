"""
Slack message templates using Slack Block Kit for rich formatting.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


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
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Template for task created notification."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🆕 New Task Created", "emoji": True}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Task:*\n{task_name}"},
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority.upper()}"},
                    {"type": "mrkdwn", "text": f"*Responsible:*\n<@{responsible_user_id}>"},
                    {"type": "mrkdwn", "text": f"*Accountable:*\n<@{accountable_user_id}>"},
                ],
            },
        ]

        if description:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Description:*\n{description}"}})

        if due_date:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"📅 Due: {due_date.strftime('%B %d, %Y')}"}],
                }
            )

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Task", "emoji": True},
                        "url": f"{settings.FRONTEND_URL}/tasks/{task_id}",
                        "style": "primary",
                    }
                ],
            }
        )

        return {"text": f"New task created: {task_name}", "blocks": blocks}

    @staticmethod
    def task_blocked(
        task_name: str,
        task_id: str,
        blocked_by_user_id: str,
        responsible_user_id: str,
        accountable_user_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Template for task blocked notification."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🚫 Task Blocked", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{task_name}* has been blocked"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Blocked by:*\n<@{blocked_by_user_id}>"},
                    {"type": "mrkdwn", "text": f"*Responsible:*\n<@{responsible_user_id}>"},
                    {"type": "mrkdwn", "text": f"*Accountable:*\n<@{accountable_user_id}>"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"}},
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Task", "emoji": True},
                        "url": f"{settings.FRONTEND_URL}/tasks/{task_id}",
                        "style": "danger",
                    }
                ],
            },
        ]

        return {"text": f"Task blocked: {task_name}", "blocks": blocks}

    @staticmethod
    def task_summary_reminder(
        user_id: str, pending_tasks: List[Dict[str, Any]], completed_today: int = 0
    ) -> Dict[str, Any]:
        """Template for task summary reminder."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🌅 End of Day Summary", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Hey <@{user_id}>! Here's your daily wrap-up:"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*✅ Completed Today:*\n{completed_today} tasks"},
                    {"type": "mrkdwn", "text": f"*📋 Pending Tasks:*\n{len(pending_tasks)} tasks"},
                ],
            },
        ]

        if pending_tasks:
            blocks.append({"type": "divider"})
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Your pending tasks:*"}})

            for task in pending_tasks[:5]:  # Show max 5 tasks
                priority_emoji = {"URGENT": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    task.get("priority", "MEDIUM"), "🟡"
                )

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{priority_emoji} *{task['name']}*\n_{task.get('status', 'pending')}_",
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View", "emoji": True},
                            "url": f"{settings.FRONTEND_URL}/tasks/{task['id']}",
                        },
                    }
                )

            if len(pending_tasks) > 5:
                blocks.append(
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": f"_... and {len(pending_tasks) - 5} more tasks_"}],
                    }
                )

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Dashboard", "emoji": True},
                        "url": f"{settings.FRONTEND_URL}/dashboard",
                        "style": "primary",
                    }
                ],
            }
        )

        return {
            "text": f"End of day summary: {completed_today} completed, {len(pending_tasks)} pending",
            "blocks": blocks,
        }

    @staticmethod
    def development_plan_created(
        user_id: str, manager_user_id: str, plan_name: str, objectives: List[str], timeline: str
    ) -> Dict[str, Any]:
        """Template for development plan created notification."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "📈 New Development Plan", "emoji": True}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{user_id}>, a new development plan has been created for you by <@{manager_user_id}>",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Plan:*\n{plan_name}"},
                    {"type": "mrkdwn", "text": f"*Timeline:*\n{timeline}"},
                ],
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*Key Objectives:*"}},
        ]

        for i, objective in enumerate(objectives[:5], 1):
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{i}. {objective}"}})

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Plan", "emoji": True},
                        "url": f"{settings.FRONTEND_URL}/development-plan",
                        "style": "primary",
                    }
                ],
            }
        )

        return {"text": f"New development plan created: {plan_name}", "blocks": blocks}

    @staticmethod
    def doc_agent_approval(
        approval_id: str,
        commit_hash: str,
        repository: str,
        commit_message: str,
        diff_preview: str,
        files_affected: int,
        additions: int,
        deletions: int,
        dashboard_url: Optional[str] = None,
        pr_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Template for doc agent approval request with interactive buttons, risk indicators, and deep links."""
        if len(diff_preview) > 2000:
            diff_preview = diff_preview[:2000] + "\n... (truncated)"

        # Simple risk heuristics
        risk_level = "LOW"
        warnings: List[str] = []
        if files_affected > 3 or deletions > 10 or additions > 100:
            risk_level = "HIGH"
        elif files_affected > 1 or deletions > 0 or additions > 20:
            risk_level = "MEDIUM"
        if risk_level == "HIGH":
            warnings.append("Large change scope detected")
        if deletions > 0:
            warnings.append("Deletions present")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📝 Documentation Update Request", "emoji": True},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Repository:* `{repository}`\n*Commit:* `{commit_hash[:8]}`\n*Message:* _{commit_message}_",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Files Affected:*\n{files_affected}"},
                    {"type": "mrkdwn", "text": f"*Changes:*\n+{additions} -{deletions}"},
                    {"type": "mrkdwn", "text": f"*Risk:*\n{risk_level}"},
                ],
            },
        ]

        if warnings:
            blocks.extend(
                [
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "*⚠️ Warnings:*\n" + "\n".join([f"• {w}" for w in warnings])},
                    },
                ]
            )

        blocks.extend(
            [
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": "*📋 Proposed Documentation Changes:*"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"```\n{diff_preview}\n```"}},
                {
                    "type": "actions",
                    "block_id": f"doc_approval_{approval_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve & Create PR", "emoji": True},
                            "style": "primary",
                            "action_id": "approve_doc_update",
                            "value": approval_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "⚡ Quick Approve", "emoji": True},
                            "action_id": "quick_approve_doc_update",
                            "value": approval_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                            "style": "danger",
                            "action_id": "reject_doc_update",
                            "value": approval_id,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "👀 View Full Diff", "emoji": True},
                            "action_id": "view_full_diff",
                            "value": approval_id,
                        },
                    ],
                },
            ]
        )

        link_elements: List[Dict[str, Any]] = []
        if dashboard_url:
            link_elements.append({"type": "mrkdwn", "text": f"🔗 <{dashboard_url}|View in Dashboard>"})
        if pr_url:
            link_elements.append({"type": "mrkdwn", "text": f"🔗 <{pr_url}|View PR>"})
        if link_elements:
            blocks.append({"type": "context", "elements": link_elements})

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_This request will expire in 24 hours if no action is taken._"}
                ],
            }
        )

        return {"text": f"Documentation update request for {repository}@{commit_hash[:8]}", "blocks": blocks}

    @staticmethod
    def documentation_proposal(
        author_user_id: str,
        commit_sha: str,
        commit_message: str,
        proposed_updates: List[Dict[str, str]],
        pr_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Template for documentation update proposal."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📝 Documentation Update Proposal", "emoji": True},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{author_user_id}>, based on your recent commit, we've identified potential documentation updates:",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Commit:*\n`{commit_sha[:8]}`"},
                    {"type": "mrkdwn", "text": f"*Message:*\n_{commit_message}_"},
                ],
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*📋 Proposed Updates:*"}},
        ]

        for update in proposed_updates[:3]:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{update['file']}*\n{update['description']}"}}
            )

        if len(proposed_updates) > 3:
            blocks.append(
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"_... and {len(proposed_updates) - 3} more updates_"}],
                }
            )

        actions = []
        if pr_url:
            actions.append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Review PR", "emoji": True},
                    "url": pr_url,
                    "style": "primary",
                }
            )

        actions.extend(
            [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_docs",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Suggest Changes", "emoji": True},
                    "action_id": "suggest_changes",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Dismiss", "emoji": True},
                    "style": "danger",
                    "action_id": "dismiss_docs",
                },
            ]
        )

        blocks.append({"type": "actions", "elements": actions})

        return {"text": f"Documentation update proposal for commit {commit_sha[:8]}", "blocks": blocks}

    @staticmethod
    def commit_analysis_summary(
        author_user_id: str,
        commit_sha: str,
        estimated_points: int,
        estimated_hours: float,
        complexity: str,
        impact_areas: List[str],
    ) -> Dict[str, Any]:
        """Template for commit analysis summary."""
        complexity_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴"}.get(complexity.lower(), "🟡")

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🔍 Commit Analysis Complete", "emoji": True}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<@{author_user_id}>, here's the analysis of your commit `{commit_sha[:8]}`:",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Estimated Points:*\n{estimated_points}"},
                    {"type": "mrkdwn", "text": f"*Estimated Hours:*\n{estimated_hours:.1f}"},
                    {"type": "mrkdwn", "text": f"*Complexity:*\n{complexity_emoji} {complexity.title()}"},
                ],
            },
        ]

        if impact_areas:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Impact Areas:*\n" + "\n".join([f"• {area}" for area in impact_areas[:5]]),
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_This analysis helps track development velocity and plan future work._"}
                ],
            }
        )

        return {"text": f"Commit analysis: {estimated_points} points, {estimated_hours:.1f} hours", "blocks": blocks}

    @staticmethod
    def eod_reminder(
        user_id: str, user_name: str, today_commits_count: int = 0, last_commit_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Template for EOD report reminder."""
        greeting = f"Hi {user_name}! 👋"

        if today_commits_count > 0:
            commit_text = f"I see you made {today_commits_count} commit{'s' if today_commits_count > 1 else ''} today"
            if last_commit_time:
                commit_text += f" (last one at {last_commit_time.strftime('%I:%M %p')})"
            commit_text += "."
        else:
            commit_text = "I didn't see any commits from you today."

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🌅 End of Day Report", "emoji": True}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{greeting}\n\nIt's time for your daily report. {commit_text}\n\nWhat else did you work on today? (meetings, planning, code reviews, debugging, etc.)",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Submit Report", "emoji": True},
                        "style": "primary",
                        "action_id": "start_eod_report",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Skip Today", "emoji": True},
                        "action_id": "skip_eod_report",
                    },
                ],
            },
        ]

        return {"text": "Time for your daily report!", "blocks": blocks}

    @staticmethod
    def eod_clarification(
        user_name: str, report_id: str, clarification_requests: List[Dict[str, Any]], original_summary: str
    ) -> Dict[str, Any]:
        """Template for EOD report clarification request."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🤔 Clarification Needed", "emoji": True}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Thanks for your report, {user_name}! I need a bit more information to accurately track your work:",
                },
            },
        ]

        # Add clarification requests
        for i, request in enumerate(clarification_requests[:5], 1):
            question = request.get("question", "")
            context = request.get("context", "")
            block_text = f"*{i}.* {question}"
            if context:
                block_text += f"\n_Context: {context}_"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": block_text}})

        blocks.append({"type": "divider"})
        context_elements: List[Dict[str, Any]] = [
            {
                "type": "mrkdwn",
                "text": "_Please reply to this message with clarifications, and I'll update your report._",
            }
        ]
        blocks.append({"type": "context", "elements": context_elements})
        return {"text": "I need some clarification on your daily report", "blocks": blocks}

    @staticmethod
    def eod_summary(
        user_name: str,
        report_id: str,
        summary: str,
        estimated_hours: float,
        commit_hours: float,
        additional_hours: float,
        linked_commits: int = 0,
    ) -> Dict[str, Any]:
        """Template for EOD report summary after processing."""
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "✅ Daily Report Processed", "emoji": True}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Thanks {user_name}! I've processed your report. Here's the summary:",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Estimated Hours:*\n{estimated_hours:.1f}"},
                    {"type": "mrkdwn", "text": f"*From Commits:*\n{commit_hours:.1f}"},
                    {"type": "mrkdwn", "text": f"*Additional Work:*\n{additional_hours:.1f}"},
                ],
            },
        ]

        if linked_commits > 0:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_🔗 Linked to {linked_commits} commit{'s' if linked_commits != 1 else ''}_",
                        }
                    ],
                }
            )
        if summary:
            blocks.append({"type": "divider"})
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*📝 Summary:*\n{summary}"}})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_Your report has been saved and will be included in weekly summaries._"}
                ],
            }
        )
        return {"text": f"Daily report processed: {estimated_hours:.1f} hours total", "blocks": blocks}


# Import settings for URL construction
from app.config.settings import settings
