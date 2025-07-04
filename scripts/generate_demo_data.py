#!/usr/bin/env python3
"""
Generate Demo Data for GolfDaddy Brain
=====================================
This script populates the database with realistic demo data for demonstrations
without requiring actual GitHub commits or external integrations.
"""

import os
import sys
import random
import requests
from datetime import datetime, timedelta
from faker import Faker
import json
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fake = Faker()

class DemoDataGenerator:
    def __init__(self, api_url: str = "http://localhost:8000", auth_token: str = None):
        self.api_url = api_url
        self.session = requests.Session()
        if auth_token:
            self.session.headers.update({"Authorization": f"Bearer {auth_token}"})
        
        # Sample data templates
        self.commit_messages = [
            "feat: Add user authentication with JWT tokens",
            "fix: Resolve memory leak in payment processor",
            "refactor: Optimize database queries for better performance",
            "feat: Implement real-time notifications using WebSockets",
            "fix: Correct timezone handling in scheduling module",
            "docs: Update API documentation with new endpoints",
            "test: Add comprehensive unit tests for auth service",
            "feat: Add export functionality for analytics dashboard",
            "fix: Handle edge case in data validation",
            "refactor: Migrate legacy code to TypeScript",
            "feat: Implement role-based access control",
            "perf: Optimize image loading with lazy loading",
            "fix: Resolve race condition in concurrent updates",
            "feat: Add dark mode support to UI",
            "chore: Update dependencies to latest versions",
        ]
        
        self.file_paths = [
            "src/services/auth.py",
            "src/components/Dashboard.tsx",
            "src/api/endpoints.py",
            "src/utils/validators.py",
            "src/models/user.py",
            "tests/test_auth.py",
            "frontend/components/Header.jsx",
            "backend/services/payment.py",
            "docs/api/authentication.md",
            "src/lib/database.py",
        ]
        
        self.developers = [
            {"name": "Alice Johnson", "email": "alice@example.com", "github": "alicej"},
            {"name": "Bob Smith", "email": "bob@example.com", "github": "bobsmith"},
            {"name": "Carol Williams", "email": "carol@example.com", "github": "carolw"},
            {"name": "David Brown", "email": "david@example.com", "github": "davidb"},
            {"name": "Eve Davis", "email": "eve@example.com", "github": "eved"},
        ]
        
        self.repositories = [
            "main-application",
            "mobile-app",
            "analytics-service",
            "payment-gateway",
            "documentation",
        ]
    
    def generate_all(self, days: int = 30):
        """Generate all demo data"""
        print("🚀 Starting demo data generation...")
        
        # Generate commits
        commits = self.generate_commits(days)
        print(f"✅ Generated {len(commits)} commits")
        
        # Generate daily reports
        reports = self.generate_daily_reports(days)
        print(f"✅ Generated {len(reports)} daily reports")
        
        # Generate documentation
        docs = self.generate_documentation()
        print(f"✅ Generated {len(docs)} documentation entries")
        
        # Generate analytics data
        self.generate_analytics_data()
        print("✅ Generated analytics data")
        
        print("\n🎉 Demo data generation complete!")
        print(f"   - Commits: {len(commits)}")
        print(f"   - Daily reports: {len(reports)}")
        print(f"   - Documentation: {len(docs)}")
        
        return {
            "commits": commits,
            "reports": reports,
            "documentation": docs
        }
    
    def generate_commits(self, days: int) -> List[Dict[str, Any]]:
        """Generate realistic commit data"""
        commits = []
        
        for day in range(days):
            date = datetime.now() - timedelta(days=day)
            
            # Generate 5-15 commits per day
            daily_commits = random.randint(5, 15)
            
            for _ in range(daily_commits):
                developer = random.choice(self.developers)
                
                commit = {
                    "sha": fake.sha1()[:40],
                    "message": random.choice(self.commit_messages),
                    "author": developer["name"],
                    "author_email": developer["email"],
                    "timestamp": (date + timedelta(
                        hours=random.randint(8, 18),
                        minutes=random.randint(0, 59)
                    )).isoformat(),
                    "repository": random.choice(self.repositories),
                    "additions": random.randint(10, 500),
                    "deletions": random.randint(0, 200),
                    "files_changed": random.randint(1, 10),
                    
                    # AI analysis results
                    "complexity": round(random.uniform(3, 9), 1),
                    "ai_hours": round(random.uniform(0.5, 8), 1),
                    "seniority_score": round(random.uniform(5, 9), 1),
                    "risk_level": random.choice(["low", "medium", "high"]),
                    "key_changes": self.generate_key_changes(),
                }
                
                commits.append(commit)
                
                # Send to API if connected
                try:
                    response = self.session.post(
                        f"{self.api_url}/api/v1/commits",
                        json=commit
                    )
                    if response.status_code != 200:
                        print(f"Warning: Failed to create commit: {response.text}")
                except Exception as e:
                    print(f"Warning: Could not connect to API: {e}")
        
        return commits
    
    def generate_key_changes(self) -> List[str]:
        """Generate key changes for a commit"""
        changes = [
            "Added input validation",
            "Improved error handling",
            "Optimized database queries",
            "Added unit tests",
            "Refactored for better readability",
            "Implemented caching",
            "Fixed security vulnerability",
            "Added logging",
            "Improved performance",
            "Updated documentation",
        ]
        
        return random.sample(changes, k=random.randint(2, 4))
    
    def generate_daily_reports(self, days: int) -> List[Dict[str, Any]]:
        """Generate daily EOD reports"""
        reports = []
        
        for day in range(days):
            date = datetime.now() - timedelta(days=day)
            
            # Skip weekends
            if date.weekday() >= 5:
                continue
            
            for developer in self.developers:
                # 80% chance of report submission
                if random.random() > 0.8:
                    continue
                
                report = {
                    "user_email": developer["email"],
                    "date": date.date().isoformat(),
                    "tasks_completed": self.generate_tasks(),
                    "hours_worked": round(random.uniform(6, 10), 1),
                    "blockers": self.generate_blockers() if random.random() > 0.7 else [],
                    "tomorrow_plan": self.generate_tomorrow_plan(),
                    "notes": fake.paragraph() if random.random() > 0.5 else None,
                }
                
                reports.append(report)
                
                # Send to API if connected
                try:
                    response = self.session.post(
                        f"{self.api_url}/api/v1/daily-reports",
                        json=report
                    )
                    if response.status_code != 200:
                        print(f"Warning: Failed to create report: {response.text}")
                except Exception as e:
                    print(f"Warning: Could not connect to API: {e}")
        
        return reports
    
    def generate_tasks(self) -> List[str]:
        """Generate completed tasks"""
        task_templates = [
            "Implemented {feature} feature",
            "Fixed bug in {component}",
            "Reviewed PR for {feature}",
            "Updated documentation for {component}",
            "Attended {meeting} meeting",
            "Deployed {service} to production",
            "Optimized {component} performance",
            "Wrote tests for {feature}",
        ]
        
        features = ["authentication", "payment", "notification", "search", "export"]
        components = ["dashboard", "API", "database", "frontend", "backend"]
        meetings = ["sprint planning", "standup", "architecture", "design review"]
        services = ["auth service", "API gateway", "worker service", "web app"]
        
        tasks = []
        for _ in range(random.randint(3, 6)):
            template = random.choice(task_templates)
            task = template.format(
                feature=random.choice(features),
                component=random.choice(components),
                meeting=random.choice(meetings),
                service=random.choice(services)
            )
            tasks.append(task)
        
        return tasks
    
    def generate_blockers(self) -> List[str]:
        """Generate blockers"""
        blocker_templates = [
            "Waiting for API design approval",
            "Need access to production database",
            "Dependency on {team} team's changes",
            "Unclear requirements for {feature}",
            "Performance issues with {component}",
            "Need code review from senior developer",
        ]
        
        teams = ["backend", "frontend", "DevOps", "QA", "design"]
        features = ["payment integration", "user management", "reporting", "export"]
        components = ["search service", "authentication", "data pipeline", "UI framework"]
        
        blockers = []
        for _ in range(random.randint(1, 2)):
            template = random.choice(blocker_templates)
            blocker = template.format(
                team=random.choice(teams),
                feature=random.choice(features),
                component=random.choice(components)
            )
            blockers.append(blocker)
        
        return blockers
    
    def generate_tomorrow_plan(self) -> List[str]:
        """Generate tomorrow's plan"""
        plan_templates = [
            "Continue working on {feature}",
            "Start implementation of {component}",
            "Code review for {developer}'s PR",
            "Write tests for {feature}",
            "Deploy {service} to staging",
            "Document {component} API",
            "Investigate {issue}",
            "Attend {meeting}",
        ]
        
        features = ["user profiles", "notifications", "analytics", "settings"]
        components = ["auth module", "payment gateway", "email service", "cache layer"]
        developers = ["Alice", "Bob", "Carol", "David"]
        services = ["API", "worker", "webhook handler", "scheduler"]
        issues = ["memory leak", "slow queries", "flaky tests", "build failures"]
        meetings = ["sprint review", "1:1", "tech talk", "planning session"]
        
        plans = []
        for _ in range(random.randint(2, 4)):
            template = random.choice(plan_templates)
            plan = template.format(
                feature=random.choice(features),
                component=random.choice(components),
                developer=random.choice(developers),
                service=random.choice(services),
                issue=random.choice(issues),
                meeting=random.choice(meetings)
            )
            plans.append(plan)
        
        return plans
    
    def generate_documentation(self) -> List[Dict[str, Any]]:
        """Generate documentation entries"""
        docs = []
        
        doc_templates = [
            {
                "title": "API Authentication Guide",
                "content": "# API Authentication\n\nOur API uses JWT tokens for authentication...",
                "path": "docs/api/authentication.md",
                "quality_score": 8.5,
            },
            {
                "title": "Database Schema",
                "content": "# Database Schema\n\n## Users Table\n\nStores user information...",
                "path": "docs/database/schema.md",
                "quality_score": 9.0,
            },
            {
                "title": "Deployment Guide",
                "content": "# Deployment Guide\n\n## Prerequisites\n\n- Docker\n- Kubernetes...",
                "path": "docs/deployment/guide.md",
                "quality_score": 8.0,
            },
            {
                "title": "Contributing Guidelines",
                "content": "# Contributing\n\n## Code Style\n\nWe use Black for Python...",
                "path": "CONTRIBUTING.md",
                "quality_score": 7.5,
            },
            {
                "title": "Architecture Overview",
                "content": "# Architecture\n\n## Microservices\n\nOur system consists of...",
                "path": "docs/architecture/overview.md",
                "quality_score": 9.5,
            },
        ]
        
        for template in doc_templates:
            doc = {
                **template,
                "created_at": fake.date_time_between(start_date="-30d", end_date="now").isoformat(),
                "updated_at": fake.date_time_between(start_date="-7d", end_date="now").isoformat(),
                "author": random.choice(self.developers)["name"],
                "embeddings_generated": True,
                "version": f"1.{random.randint(0, 5)}",
            }
            
            docs.append(doc)
            
            # Send to API if connected
            try:
                response = self.session.post(
                    f"{self.api_url}/api/v1/documentation",
                    json=doc
                )
                if response.status_code != 200:
                    print(f"Warning: Failed to create doc: {response.text}")
            except Exception as e:
                print(f"Warning: Could not connect to API: {e}")
        
        return docs
    
    def generate_analytics_data(self):
        """Generate analytics and metrics data"""
        # This would typically be calculated from the generated data
        # For demo purposes, we'll just print a summary
        
        analytics = {
            "total_commits": random.randint(150, 300),
            "total_hours": round(random.uniform(800, 1200), 1),
            "avg_complexity": round(random.uniform(5.5, 7.5), 1),
            "documentation_coverage": round(random.uniform(65, 85), 1),
            "active_developers": len(self.developers),
            "repositories": len(self.repositories),
        }
        
        print("\n📊 Analytics Summary:")
        for key, value in analytics.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")
        
        return analytics


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate demo data for GolfDaddy Brain")
    parser.add_argument("--days", type=int, default=30, help="Number of days of data to generate")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--auth-token", help="Authentication token")
    parser.add_argument("--output", help="Save data to JSON file")
    
    args = parser.parse_args()
    
    # Check if faker is installed
    try:
        from faker import Faker
    except ImportError:
        print("Installing required package: faker")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "faker"])
        print("Please run the script again")
        sys.exit(0)
    
    generator = DemoDataGenerator(api_url=args.api_url, auth_token=args.auth_token)
    data = generator.generate_all(days=args.days)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Data saved to {args.output}")


if __name__ == "__main__":
    main()