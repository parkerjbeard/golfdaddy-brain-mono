#!/usr/bin/env python3
"""
Comprehensive test for the commit analyzer with real data scenarios.
This test uses realistic commit data and shows actual output formats.
"""

import asyncio
import sys
import os
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set up environment variables for testing
os.environ['TESTING_MODE'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SUPABASE_URL'] = 'http://localhost:8000'
os.environ['SUPABASE_SERVICE_KEY'] = 'test'
os.environ['OPENAI_API_KEY'] = 'test'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealisticTestData:
    """Container for realistic test data scenarios"""
    
    @staticmethod
    def get_users():
        """Get realistic user data"""
        return [
            {
                "id": uuid4(),
                "email": "sarah.dev@company.com",
                "full_name": "Sarah Johnson",
                "github_username": "sarah-j-dev",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "id": uuid4(),
                "email": "mike.senior@company.com", 
                "full_name": "Mike Chen",
                "github_username": "mchen-tech",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "id": uuid4(),
                "email": "alex.junior@company.com",
                "full_name": "Alex Rivera",
                "github_username": "alex-codes",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]
    
    @staticmethod
    def get_commit_scenarios():
        """Get realistic commit scenarios with different complexity levels"""
        users = RealisticTestData.get_users()
        
        return [
            {
                "name": "Simple Bug Fix",
                "user": users[0],  # Sarah - mid-level
                "commit": {
                    "commit_hash": "a1b2c3d4e5f6",
                    "repository_name": "company/web-app",
                    "commit_message": "fix: Correct null pointer exception in user profile\n\nFixed NPE that occurred when user had no profile image",
                    "commit_timestamp": datetime.now() - timedelta(hours=2),
                    "commit_url": "https://github.com/company/web-app/commit/a1b2c3d4e5f6",
                    "repository_url": "https://github.com/company/web-app",
                    "branch": "main",
                    "author_email": "sarah.dev@company.com",
                    "author_name": "Sarah Johnson",
                    "author_github_username": "sarah-j-dev",
                    "files_changed": ["src/components/UserProfile.tsx"],
                    "additions": 5,
                    "deletions": 2,
                    "commit_diff": """diff --git a/src/components/UserProfile.tsx b/src/components/UserProfile.tsx
index 1234567..abcdefg 100644
--- a/src/components/UserProfile.tsx
+++ b/src/components/UserProfile.tsx
@@ -15,7 +15,7 @@ export const UserProfile: React.FC<Props> = ({ user }) => {
   return (
     <div className="user-profile">
       <h2>{user.name}</h2>
-      <img src={user.profileImage} alt="Profile" />
+      <img src={user.profileImage || '/default-avatar.png'} alt="Profile" />
       <p>{user.bio}</p>
     </div>
   );
"""
                },
                "expected_ai_response": {
                    "complexity_score": 2,
                    "estimated_hours": 0.3,
                    "risk_level": "low",
                    "seniority_score": 6,
                    "seniority_rationale": "Simple null check fix. Good defensive programming practice.",
                    "key_changes": ["Added null check for profile image", "Added fallback to default avatar"],
                    "analyzed_at": datetime.now().isoformat(),
                    "model_used": "o4-mini-test",
                    "commit_hash": "a1b2c3d4e5f6",
                    "repository": "company/web-app"
                }
            },
            {
                "name": "Feature Implementation",
                "user": users[1],  # Mike - senior
                "commit": {
                    "commit_hash": "f6e5d4c3b2a1",
                    "repository_name": "company/api-service",
                    "commit_message": "feat: Implement user notification system\n\nAdded comprehensive notification system with:\n- Real-time WebSocket notifications\n- Email fallback for offline users\n- Notification preferences management\n- Rate limiting and batching\n\nIncludes full test coverage and documentation.",
                    "commit_timestamp": datetime.now() - timedelta(hours=4),
                    "commit_url": "https://github.com/company/api-service/commit/f6e5d4c3b2a1",
                    "repository_url": "https://github.com/company/api-service",
                    "branch": "feature/notifications",
                    "author_email": "mike.senior@company.com",
                    "author_name": "Mike Chen",
                    "author_github_username": "mchen-tech",
                    "files_changed": [
                        "src/services/NotificationService.ts",
                        "src/controllers/NotificationController.ts",
                        "src/models/Notification.ts",
                        "src/utils/RateLimiter.ts",
                        "tests/services/NotificationService.test.ts",
                        "docs/api/notifications.md"
                    ],
                    "additions": 234,
                    "deletions": 12,
                    "commit_diff": """diff --git a/src/services/NotificationService.ts b/src/services/NotificationService.ts
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/services/NotificationService.ts
@@ -0,0 +1,156 @@
+import { WebSocket } from 'ws';
+import { EmailService } from './EmailService';
+import { RateLimiter } from '../utils/RateLimiter';
+
+export class NotificationService {
+  private emailService: EmailService;
+  private rateLimiter: RateLimiter;
+  private activeConnections: Map<string, WebSocket> = new Map();
+
+  constructor() {
+    this.emailService = new EmailService();
+    this.rateLimiter = new RateLimiter({ maxRequests: 100, windowMs: 60000 });
+  }
+
+  async sendNotification(userId: string, notification: Notification): Promise<void> {
+    // Check rate limits
+    if (!this.rateLimiter.checkLimit(userId)) {
+      throw new Error('Rate limit exceeded');
+    }
+
+    // Try WebSocket first
+    const connection = this.activeConnections.get(userId);
+    if (connection && connection.readyState === WebSocket.OPEN) {
+      connection.send(JSON.stringify(notification));
+      return;
+    }
+
+    // Fallback to email
+    await this.emailService.sendNotificationEmail(userId, notification);
+  }
+}
"""
                },
                "expected_ai_response": {
                    "complexity_score": 8,
                    "estimated_hours": 6.5,
                    "risk_level": "medium",
                    "seniority_score": 9,
                    "seniority_rationale": "Complex feature implementation with multiple moving parts. Excellent architecture with proper error handling, rate limiting, and fallback mechanisms. Shows senior-level system design thinking.",
                    "key_changes": [
                        "Implemented WebSocket notification system",
                        "Added email fallback mechanism", 
                        "Implemented rate limiting",
                        "Added comprehensive test coverage",
                        "Created API documentation"
                    ],
                    "analyzed_at": datetime.now().isoformat(),
                    "model_used": "o4-mini-test",
                    "commit_hash": "f6e5d4c3b2a1",
                    "repository": "company/api-service"
                }
            },
            {
                "name": "Refactoring with Database Changes",
                "user": users[2],  # Alex - junior
                "commit": {
                    "commit_hash": "9z8y7x6w5v4u",
                    "repository_name": "company/analytics-service",
                    "commit_message": "refactor: Optimize database queries and add caching\n\nRefactored analytics queries to use more efficient joins\nAdded Redis caching layer for frequently accessed data\nUpdated database schema with new indexes",
                    "commit_timestamp": datetime.now() - timedelta(hours=1),
                    "commit_url": "https://github.com/company/analytics-service/commit/9z8y7x6w5v4u",
                    "repository_url": "https://github.com/company/analytics-service", 
                    "branch": "optimize/database-performance",
                    "author_email": "alex.junior@company.com",
                    "author_name": "Alex Rivera",
                    "author_github_username": "alex-codes",
                    "files_changed": [
                        "src/repositories/AnalyticsRepository.ts",
                        "src/services/CacheService.ts",
                        "migrations/007_add_analytics_indexes.sql",
                        "src/config/redis.ts"
                    ],
                    "additions": 89,
                    "deletions": 45,
                    "commit_diff": """diff --git a/src/repositories/AnalyticsRepository.ts b/src/repositories/AnalyticsRepository.ts
index abcdef..123456 100644
--- a/src/repositories/AnalyticsRepository.ts
+++ b/src/repositories/AnalyticsRepository.ts
@@ -10,15 +10,25 @@ export class AnalyticsRepository {
   }
 
   async getUserAnalytics(userId: string, dateRange: DateRange): Promise<UserAnalytics> {
-    const query = `
-      SELECT u.*, 
-             COUNT(e.id) as event_count,
-             AVG(e.duration) as avg_duration
-      FROM users u
-      LEFT JOIN events e ON u.id = e.user_id
-      WHERE u.id = ? AND e.created_at BETWEEN ? AND ?
-      GROUP BY u.id
-    `;
+    // Check cache first
+    const cacheKey = `analytics:${userId}:${dateRange.start}:${dateRange.end}`;
+    const cached = await this.cacheService.get(cacheKey);
+    if (cached) {
+      return cached;
+    }
+
+    // Optimized query with proper indexes
+    const query = `
+      SELECT u.id, u.name, u.email,
+             COUNT(e.id) as event_count,
+             AVG(e.duration) as avg_duration,
+             MIN(e.created_at) as first_event,
+             MAX(e.created_at) as last_event
+      FROM users u
+      INNER JOIN events e ON u.id = e.user_id AND e.created_at BETWEEN ? AND ?
+      WHERE u.id = ?
+      GROUP BY u.id, u.name, u.email
+    `;
"""
                },
                "expected_ai_response": {
                    "complexity_score": 6,
                    "estimated_hours": 3.5,
                    "risk_level": "medium-high",
                    "seniority_score": 7,
                    "seniority_rationale": "Good performance optimization work with caching implementation. Shows understanding of database optimization and caching strategies. Database migrations require careful attention.",
                    "key_changes": [
                        "Optimized database queries with better joins",
                        "Added Redis caching layer",
                        "Created database migration for indexes",
                        "Improved query performance"
                    ],
                    "analyzed_at": datetime.now().isoformat(),
                    "model_used": "o4-mini-test", 
                    "commit_hash": "9z8y7x6w5v4u",
                    "repository": "company/analytics-service"
                }
            }
        ]

async def create_comprehensive_test():
    """Create a comprehensive test that shows real data flow"""
    
    logger.info("🚀 Starting Comprehensive Commit Analyzer Test")
    logger.info("=" * 80)
    
    try:
        from unittest.mock import patch
        from app.schemas.github_event import CommitPayload
        from app.models.commit import Commit
        from app.models.user import User
        from app.models.daily_report import DailyReport
        
        # Get test scenarios
        scenarios = RealisticTestData.get_commit_scenarios()
        
        results = []
        
        # Mock external dependencies but let business logic run
        with patch('app.config.supabase_client.get_supabase_client_safe') as mock_supabase_client, \
             patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class, \
             patch('app.repositories.commit_repository.CommitRepository') as mock_commit_repo_class, \
             patch('app.integrations.ai_integration.AIIntegration') as mock_ai_class, \
             patch('app.services.daily_report_service.DailyReportService') as mock_daily_service, \
             patch('app.services.documentation_update_service.DocumentationUpdateService') as mock_docs_service:
            
            # Configure supabase mock
            mock_supabase_client.return_value = MagicMock()
            
            for i, scenario in enumerate(scenarios, 1):
                logger.info(f"\n📊 Running Scenario {i}/3: {scenario['name']}")
                logger.info("-" * 60)
                
                # Setup user mock
                test_user = User(**scenario['user'])
                mock_user_repo = AsyncMock()
                mock_user_repo.get_user_by_email.return_value = test_user
                mock_user_repo.get_user_by_github_username.return_value = test_user
                mock_user_repo_class.return_value = mock_user_repo
                
                # Setup commit repo mock
                mock_commit_repo = AsyncMock()
                mock_commit_repo.get_commit_by_hash.return_value = None  # New commit
                
                def create_mock_save_commit(expected_ai_response):
                    def mock_save_commit(commit_obj):
                        # Simulate database save and add fields that would be populated
                        commit_obj.id = uuid4()
                        commit_obj.created_at = datetime.now()
                        commit_obj.updated_at = datetime.now()
                        
                        # Convert Decimal fields properly
                        if hasattr(commit_obj, 'ai_estimated_hours') and commit_obj.ai_estimated_hours is not None:
                            commit_obj.ai_estimated_hours = Decimal(str(commit_obj.ai_estimated_hours))
                        
                        logger.info(f"💾 Saving commit to database:")
                        logger.info(f"   Hash: {commit_obj.commit_hash}")
                        logger.info(f"   Author ID: {commit_obj.author_id}")
                        logger.info(f"   AI Hours: {commit_obj.ai_estimated_hours}")
                        logger.info(f"   Seniority Score: {commit_obj.seniority_score}")
                        logger.info(f"   Risk Level: {commit_obj.risk_level}")
                        
                        return commit_obj
                    return mock_save_commit
                
                mock_commit_repo.save_commit.side_effect = create_mock_save_commit(scenario['expected_ai_response'])
                mock_commit_repo_class.return_value = mock_commit_repo
                
                # Setup AI integration mock
                mock_ai_integration = AsyncMock()
                mock_ai_integration.analyze_commit_diff.return_value = scenario['expected_ai_response']
                mock_ai_integration.analyze_commit_code_quality.return_value = {
                    "model_used": "o4-mini-test",
                    "readability_score": 8,
                    "maintainability_score": 7,
                    "overall_assessment_summary": f"Well-structured code for {scenario['name'].lower()}. Good practices followed."
                }
                mock_ai_class.return_value = mock_ai_integration
                
                # Setup daily report service mock  
                summary_text = f"Worked on {scenario['name'].lower()} - made good progress"
                estimated_hours_value = scenario['expected_ai_response']['estimated_hours'] * 1.2
                
                # Create simple objects instead of MagicMock for cleaner value handling
                class MockAIAnalysis:
                    def __init__(self, summary, estimated_hours):
                        self.summary = summary
                        self.estimated_hours = estimated_hours
                        self.key_achievements = ["Made good progress", "Implemented as planned"]
                
                class MockEODReport:
                    def __init__(self, report_id, report_date, ai_analysis):
                        self.id = report_id
                        self.report_date = report_date
                        self.ai_analysis = ai_analysis
                
                mock_eod_report = MockEODReport(
                    report_id=uuid4(),
                    report_date=scenario['commit']['commit_timestamp'].date(),
                    ai_analysis=MockAIAnalysis(summary_text, estimated_hours_value)
                )
                
                mock_daily_service_instance = AsyncMock()
                mock_daily_service_instance.get_user_report_for_date.return_value = mock_eod_report
                mock_daily_service.return_value = mock_daily_service_instance
                
                # Setup docs service mock
                mock_docs_service.return_value = MagicMock()
                
                # Create commit payload
                commit_payload = CommitPayload(**scenario['commit'])
                
                # Import and run the service
                from app.services.commit_analysis_service import CommitAnalysisService
                
                service = CommitAnalysisService(MagicMock())
                
                # Process the commit
                logger.info(f"🔄 Processing commit: {commit_payload.commit_hash}")
                result = await service.process_commit(commit_payload)
                
                if result:
                    logger.info(f"✅ Successfully processed commit!")
                    
                    # Display comprehensive results
                    display_commit_analysis_results(scenario, result)
                    
                    results.append({
                        "scenario": scenario['name'],
                        "success": True,
                        "result": result
                    })
                else:
                    logger.error(f"❌ Failed to process commit")
                    results.append({
                        "scenario": scenario['name'], 
                        "success": False,
                        "result": None
                    })
                
                logger.info(f"Scenario {i} completed")
        
        # Display final summary
        display_test_summary(results)
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return []

def display_commit_analysis_results(scenario, result):
    """Display detailed analysis results"""
    logger.info(f"\n📋 ANALYSIS RESULTS FOR: {scenario['name']}")
    logger.info("=" * 50)
    
    logger.info(f"👤 Developer: {scenario['user']['full_name']} (@{scenario['user']['github_username']})")
    logger.info(f"📦 Repository: {scenario['commit']['repository_name']}")
    logger.info(f"🔗 Commit: {result.commit_hash[:8]}...")
    logger.info(f"📅 Timestamp: {result.commit_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    logger.info(f"\n🤖 AI ANALYSIS:")
    logger.info(f"   Complexity Score: {result.ai_points}/10")
    logger.info(f"   Estimated Hours: {result.ai_estimated_hours}")
    logger.info(f"   Risk Level: {result.risk_level}")
    logger.info(f"   Seniority Score: {result.seniority_score}/10")
    logger.info(f"   Model Used: {result.model_used}")
    
    logger.info(f"\n📝 KEY CHANGES:")
    for change in result.key_changes:
        logger.info(f"   • {change}")
    
    logger.info(f"\n💭 SENIORITY RATIONALE:")
    logger.info(f"   {result.seniority_rationale}")
    
    if hasattr(result, 'code_quality_analysis') and result.code_quality_analysis:
        logger.info(f"\n🎯 CODE QUALITY:")
        quality = result.code_quality_analysis
        if 'readability_score' in quality:
            logger.info(f"   Readability: {quality['readability_score']}/10")
        if 'maintainability_score' in quality:
            logger.info(f"   Maintainability: {quality['maintainability_score']}/10")
        if 'overall_assessment_summary' in quality:
            logger.info(f"   Assessment: {quality['overall_assessment_summary']}")
    
    if hasattr(result, 'eod_report_id') and result.eod_report_id:
        logger.info(f"\n📊 EOD INTEGRATION:")
        logger.info(f"   EOD Report ID: {str(result.eod_report_id)[:8]}...")
        if hasattr(result, 'eod_report_summary'):
            logger.info(f"   EOD Summary: {result.eod_report_summary}")
    
    if hasattr(result, 'comparison_notes') and result.comparison_notes:
        logger.info(f"\n🔍 COMPARISON NOTES:")
        for line in result.comparison_notes.split('\n')[:3]:  # Show first 3 lines
            if line.strip():
                logger.info(f"   {line.strip()}")

def display_test_summary(results):
    """Display test summary"""
    logger.info(f"\n🎯 TEST SUMMARY")
    logger.info("=" * 80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    logger.info(f"✅ Successful: {len(successful)}/{len(results)}")
    logger.info(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        logger.info(f"\n📊 ANALYSIS SUMMARY:")
        total_hours = sum(float(r['result'].ai_estimated_hours or 0) for r in successful if r['result'].ai_estimated_hours)
        avg_complexity = sum(r['result'].ai_points or 0 for r in successful if r['result'].ai_points) / len(successful)
        avg_seniority = sum(r['result'].seniority_score or 0 for r in successful if r['result'].seniority_score) / len(successful)
        
        logger.info(f"   Total Estimated Hours: {total_hours:.2f}")
        logger.info(f"   Average Complexity: {avg_complexity:.1f}/10")
        logger.info(f"   Average Seniority Score: {avg_seniority:.1f}/10")
        
        risk_levels = [r['result'].risk_level for r in successful if r['result'].risk_level]
        risk_summary = {}
        for risk in risk_levels:
            risk_summary[risk] = risk_summary.get(risk, 0) + 1
        
        logger.info(f"   Risk Distribution: {risk_summary}")
    
    if failed:
        logger.info(f"\n❌ FAILED SCENARIOS:")
        for r in failed:
            logger.info(f"   • {r['scenario']}")

async def main():
    """Main test runner"""
    logger.info("🔬 Comprehensive Commit Analyzer Test Suite")
    logger.info("This test runs realistic commit data through the analyzer to show actual output")
    logger.info("=" * 80)
    
    results = await create_comprehensive_test()
    
    logger.info(f"\n🏁 Test completed. Processed {len(results)} scenarios.")
    
    return 0 if all(r['success'] for r in results) else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 