#!/usr/bin/env python3
"""
Production-like demo of the commit analyzer.
This simulates real GitHub webhook data ingestion and processing.
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set up environment variables for demo
os.environ['TESTING_MODE'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SUPABASE_URL'] = 'http://localhost:8000'
os.environ['SUPABASE_SERVICE_KEY'] = 'demo-key'
os.environ['OPENAI_API_KEY'] = 'demo-key'

print("🚀 Commit Analyzer Production Demo")
print("=" * 60)
print("This demo simulates real GitHub commit data processing")
print("=" * 60)

class ProductionCommitData:
    """Realistic commit data that would come from GitHub webhooks"""
    
    @staticmethod
    def get_sample_commits():
        """Returns realistic commit payloads like those from GitHub webhooks"""
        
        base_time = datetime.now()
        
        return [
            {
                "commit_hash": "abc123def456789",
                "repository_name": "company/user-service",
                "commit_message": "fix: Resolve memory leak in user session management\n\nFixed issue where user sessions weren't being properly cleaned up,\ncausing memory usage to grow over time. Added proper cleanup\nin logout and session timeout handlers.",
                "commit_timestamp": base_time - timedelta(hours=2),
                "commit_url": "https://github.com/company/user-service/commit/abc123def456789",
                "repository_url": "https://github.com/company/user-service",
                "branch": "main",
                "author_email": "sarah.developer@company.com",
                "author_name": "Sarah Chen",
                "author_github_username": "sarah-chen-dev",
                "files_changed": [
                    "src/auth/SessionManager.ts",
                    "src/auth/LogoutHandler.ts",
                    "tests/auth/SessionManager.test.ts"
                ],
                "additions": 23,
                "deletions": 8,
                "commit_diff": """diff --git a/src/auth/SessionManager.ts b/src/auth/SessionManager.ts
index 1234567..abcdefg 100644
--- a/src/auth/SessionManager.ts
+++ b/src/auth/SessionManager.ts
@@ -45,6 +45,12 @@ export class SessionManager {
   
   async cleanupExpiredSessions(): Promise<void> {
     const expiredSessions = await this.getExpiredSessions();
+    
+    // Properly cleanup memory references
+    for (const session of expiredSessions) {
+      this.clearSessionData(session.id);
+      this.removeFromActiveConnections(session.id);
+    }
+    
     await this.database.deleteSessions(expiredSessions.map(s => s.id));
   }
 }"""
            },
            {
                "commit_hash": "def789ghi012345",
                "repository_name": "company/analytics-dashboard",
                "commit_message": "feat: Implement real-time analytics dashboard\n\nAdded comprehensive real-time dashboard with:\n- Live user activity tracking\n- Revenue metrics with WebSocket updates\n- Interactive charts using D3.js\n- Responsive design for mobile devices\n- Redis caching for performance\n\nIncludes complete test suite and documentation.",
                "commit_timestamp": base_time - timedelta(hours=6),
                "commit_url": "https://github.com/company/analytics-dashboard/commit/def789ghi012345",
                "repository_url": "https://github.com/company/analytics-dashboard",
                "branch": "feature/realtime-dashboard",
                "author_email": "mike.senior@company.com",
                "author_name": "Mike Rodriguez",
                "author_github_username": "mike-rodriguez-tech",
                "files_changed": [
                    "src/components/RealtimeDashboard.tsx",
                    "src/services/AnalyticsService.ts",
                    "src/services/WebSocketService.ts",
                    "src/utils/ChartRenderer.ts",
                    "src/hooks/useRealtimeData.ts",
                    "tests/components/RealtimeDashboard.test.tsx",
                    "tests/services/AnalyticsService.test.ts",
                    "docs/analytics-dashboard-api.md"
                ],
                "additions": 487,
                "deletions": 34,
                "commit_diff": """diff --git a/src/components/RealtimeDashboard.tsx b/src/components/RealtimeDashboard.tsx
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/components/RealtimeDashboard.tsx
@@ -0,0 +1,156 @@
+import React, { useEffect, useState } from 'react';
+import { useRealtimeData } from '../hooks/useRealtimeData';
+import { ChartRenderer } from '../utils/ChartRenderer';
+import { AnalyticsService } from '../services/AnalyticsService';
+
+interface DashboardProps {
+  userId: string;
+  refreshInterval?: number;
+}
+
+export const RealtimeDashboard: React.FC<DashboardProps> = ({ 
+  userId, 
+  refreshInterval = 5000 
+}) => {
+  const { data, isConnected, error } = useRealtimeData(userId);
+  const [chartData, setChartData] = useState(null);
+  
+  useEffect(() => {
+    if (data) {
+      const processedData = AnalyticsService.processRealtimeData(data);
+      setChartData(processedData);
+    }
+  }, [data]);
+
+  return (
+    <div className="realtime-dashboard">
+      <div className="status-indicator">
+        <span className={`indicator ${isConnected ? 'connected' : 'disconnected'}`}>
+          {isConnected ? '🟢 Live' : '🔴 Disconnected'}
+        </span>
+      </div>
+      
+      {error && (
+        <div className="error-banner">
+          Error: {error.message}
+        </div>
+      )}
+      
+      <div className="charts-container">
+        {chartData && (
+          <>
+            <ChartRenderer 
+              type="line" 
+              data={chartData.userActivity} 
+              title="Live User Activity"
+            />
+            <ChartRenderer 
+              type="bar" 
+              data={chartData.revenue} 
+              title="Revenue Metrics"
+            />
+          </>
+        )}
+      </div>
+    </div>
+  );
+};"""
            },
            {
                "commit_hash": "ghi345jkl678901",
                "repository_name": "company/payment-processor",
                "commit_message": "refactor: Optimize payment processing pipeline\n\nRefactored payment processing for better performance:\n- Implemented async processing with queue system\n- Added database connection pooling\n- Optimized SQL queries with proper indexing\n- Added monitoring and alerting\n- Improved error handling and retry logic",
                "commit_timestamp": base_time - timedelta(hours=1),
                "commit_url": "https://github.com/company/payment-processor/commit/ghi345jkl678901",
                "repository_url": "https://github.com/company/payment-processor",
                "branch": "optimize/payment-pipeline",
                "author_email": "alex.junior@company.com",
                "author_name": "Alex Thompson",
                "author_github_username": "alex-thompson-dev",
                "files_changed": [
                    "src/processors/PaymentProcessor.ts",
                    "src/database/ConnectionPool.ts",
                    "src/queue/PaymentQueue.ts",
                    "src/monitoring/PaymentMetrics.ts",
                    "migrations/add_payment_indexes.sql"
                ],
                "additions": 156,
                "deletions": 89,
                "commit_diff": """diff --git a/src/processors/PaymentProcessor.ts b/src/processors/PaymentProcessor.ts
index abcdef..123456 100644
--- a/src/processors/PaymentProcessor.ts
+++ b/src/processors/PaymentProcessor.ts
@@ -15,20 +15,35 @@ export class PaymentProcessor {
   }
 
   async processPayment(payment: PaymentRequest): Promise<PaymentResult> {
-    // Old synchronous processing
-    const validation = await this.validatePayment(payment);
-    if (!validation.isValid) {
-      throw new PaymentError(validation.error);
-    }
+    // New async processing with queue
+    try {
+      // Add to processing queue for better throughput
+      const queueResult = await this.paymentQueue.enqueue(payment, {
+        priority: payment.amount > 1000 ? 'high' : 'normal',
+        retryCount: 3,
+        timeout: 30000
+      });
 
-    const result = await this.chargeProvider.charge(payment);
-    await this.database.savePaymentResult(result);
+      // Process with connection pooling
+      const result = await this.processWithRetry(payment, queueResult.id);
+      
+      // Async monitoring (don't block main flow)
+      this.metrics.recordPaymentProcessed(result);
+      
+      return result;
+    } catch (error) {
+      this.metrics.recordPaymentError(error);
+      throw error;
+    }
+  }
+
+  private async processWithRetry(payment: PaymentRequest, queueId: string): Promise<PaymentResult> {
+    // Implementation with proper retry logic and monitoring
+    const connection = await this.connectionPool.acquire();
+    try {
+      // ... processing logic with optimized queries
+    } finally {
+      this.connectionPool.release(connection);
+    }
+  }
-    return result;
-  }
 }"""
            }
        ]

async def simulate_commit_processing():
    """Simulate processing commits like in production"""
    
    print("\n📥 SIMULATING COMMIT INGESTION")
    print("=" * 40)
    
    # Get realistic commit data
    commits = ProductionCommitData.get_sample_commits()
    
    print(f"Received {len(commits)} commits from GitHub webhooks:")
    for i, commit in enumerate(commits, 1):
        print(f"  {i}. {commit['commit_hash'][:8]} - {commit['repository_name']}")
        print(f"     Author: {commit['author_name']} ({commit['author_github_username']})")
        print(f"     Files: {len(commit['files_changed'])}, +{commit['additions']} -{commit['deletions']}")
    
    print("\n🔄 PROCESSING COMMITS THROUGH ANALYZER")
    print("=" * 40)
    
    results = []
    
    for i, commit_data in enumerate(commits, 1):
        print(f"\n📊 Processing Commit {i}/{len(commits)}")
        print(f"Hash: {commit_data['commit_hash']}")
        print(f"Repository: {commit_data['repository_name']}")
        print(f"Author: {commit_data['author_name']} <{commit_data['author_email']}>")
        print(f"Message: {commit_data['commit_message'].split(chr(10))[0]}")  # First line only
        
        # Simulate the AI analysis that would happen in production
        analysis_result = simulate_ai_analysis(commit_data)
        
        # Simulate database storage
        commit_record = create_commit_record(commit_data, analysis_result)
        
        results.append({
            "commit": commit_data,
            "analysis": analysis_result,
            "record": commit_record
        })
        
        print("✅ Processing complete")
        
        # Add small delay to simulate processing time
        await asyncio.sleep(0.1)
    
    return results

def simulate_ai_analysis(commit_data):
    """Simulate AI analysis based on commit complexity"""
    
    # Analyze commit complexity based on realistic factors
    file_count = len(commit_data['files_changed'])
    line_changes = commit_data['additions'] + commit_data['deletions']
    
    # Determine complexity score (1-10)
    if line_changes < 20:
        complexity = 2
        hours = 0.3
        risk = "low"
    elif line_changes < 100:
        complexity = 5
        hours = 2.0
        risk = "medium"
    else:
        complexity = 8
        hours = 6.5
        risk = "medium-high"
    
    # Determine seniority score based on commit quality
    if "fix:" in commit_data['commit_message']:
        seniority = 6  # Good bug fixing
        rationale = "Solid debugging and fix implementation. Shows good problem-solving skills."
    elif "feat:" in commit_data['commit_message'] and line_changes > 200:
        seniority = 9  # Complex feature
        rationale = "Complex feature implementation with multiple components. Shows senior-level architecture thinking."
    elif "refactor:" in commit_data['commit_message']:
        seniority = 7  # Good refactoring
        rationale = "Performance optimization with good understanding of system architecture. Database optimization shows maturity."
    else:
        seniority = 5  # Default
        rationale = "Standard implementation following best practices."
    
    # Extract key changes from commit message and diff
    key_changes = []
    if "memory leak" in commit_data['commit_message'].lower():
        key_changes = ["Fixed memory leak in session management", "Added proper cleanup handlers"]
    elif "real-time" in commit_data['commit_message'].lower():
        key_changes = ["Implemented real-time dashboard", "Added WebSocket integration", "Created responsive charts"]
    elif "optimize" in commit_data['commit_message'].lower():
        key_changes = ["Optimized database queries", "Implemented connection pooling", "Added async processing"]
    else:
        key_changes = ["Code improvements", "Added tests"]
    
    return {
        "complexity_score": complexity,
        "estimated_hours": hours,
        "risk_level": risk,
        "seniority_score": seniority,
        "seniority_rationale": rationale,
        "key_changes": key_changes,
        "analyzed_at": datetime.now().isoformat(),
        "model_used": "gpt-4o-mini",
        "commit_hash": commit_data["commit_hash"],
        "repository": commit_data["repository_name"]
    }

def create_commit_record(commit_data, analysis):
    """Create the commit record that would be stored in database"""
    
    return {
        "id": str(uuid4()),
        "commit_hash": commit_data["commit_hash"],
        "repository_name": commit_data["repository_name"],
        "author_email": commit_data["author_email"],
        "author_name": commit_data["author_name"],
        "author_github_username": commit_data["author_github_username"],
        "commit_message": commit_data["commit_message"],
        "commit_timestamp": commit_data["commit_timestamp"].isoformat(),
        "files_changed": commit_data["files_changed"],
        "additions": commit_data["additions"],
        "deletions": commit_data["deletions"],
        "branch": commit_data["branch"],
        
        # AI Analysis Results
        "ai_points": analysis["complexity_score"],
        "ai_estimated_hours": Decimal(str(analysis["estimated_hours"])),
        "risk_level": analysis["risk_level"],
        "seniority_score": analysis["seniority_score"],
        "seniority_rationale": analysis["seniority_rationale"],
        "key_changes": analysis["key_changes"],
        "model_used": analysis["model_used"],
        "analyzed_at": analysis["analyzed_at"],
        
        # Database fields
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

def display_production_results(results):
    """Display results in a production-like format"""
    
    print("\n📊 COMMIT ANALYSIS RESULTS")
    print("=" * 60)
    
    total_hours = 0
    complexity_scores = []
    seniority_scores = []
    
    for i, result in enumerate(results, 1):
        commit = result["commit"]
        analysis = result["analysis"]
        record = result["record"]
        
        print(f"\n🔍 COMMIT {i}: {commit['commit_hash'][:12]}")
        print("-" * 50)
        
        print(f"📦 Repository: {commit['repository_name']}")
        print(f"👤 Author: {commit['author_name']} (@{commit['author_github_username']})")
        print(f"📅 Date: {commit['commit_timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌿 Branch: {commit['branch']}")
        
        print(f"\n📝 Message:")
        message_lines = commit['commit_message'].split('\n')
        for line in message_lines[:3]:  # Show first 3 lines
            if line.strip():
                print(f"   {line}")
        
        print(f"\n📊 Changes:")
        print(f"   Files Modified: {len(commit['files_changed'])}")
        print(f"   Lines Added: +{commit['additions']}")
        print(f"   Lines Deleted: -{commit['deletions']}")
        
        print(f"\n🤖 AI Analysis:")
        print(f"   Complexity Score: {analysis['complexity_score']}/10")
        print(f"   Estimated Hours: {analysis['estimated_hours']}")
        print(f"   Risk Level: {analysis['risk_level']}")
        print(f"   Seniority Score: {analysis['seniority_score']}/10")
        print(f"   Model Used: {analysis['model_used']}")
        
        print(f"\n💭 Rationale:")
        print(f"   {analysis['seniority_rationale']}")
        
        print(f"\n🔧 Key Changes:")
        for change in analysis['key_changes']:
            print(f"   • {change}")
        
        # Accumulate stats
        total_hours += analysis['estimated_hours']
        complexity_scores.append(analysis['complexity_score'])
        seniority_scores.append(analysis['seniority_score'])
    
    # Display summary
    print(f"\n📈 SUMMARY STATISTICS")
    print("=" * 60)
    print(f"Total Commits Processed: {len(results)}")
    print(f"Total Estimated Hours: {total_hours:.1f}")
    print(f"Average Complexity: {sum(complexity_scores) / len(complexity_scores):.1f}/10")
    print(f"Average Seniority: {sum(seniority_scores) / len(seniority_scores):.1f}/10")
    
    # Risk distribution
    risk_counts = {}
    for result in results:
        risk = result["analysis"]["risk_level"]
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    print(f"Risk Distribution: {dict(risk_counts)}")
    
    print("\n💾 DATABASE RECORDS CREATED")
    print("=" * 60)
    print("The following records would be stored in production:")
    
    for i, result in enumerate(results, 1):
        record = result["record"]
        print(f"{i}. ID: {record['id'][:8]}... | Hash: {record['commit_hash'][:12]}... | Hours: {record['ai_estimated_hours']}")

async def main():
    """Main demo function"""
    
    print("Starting production-like commit processing demo...")
    print("This simulates the full data flow from GitHub webhook to database storage.\n")
    
    try:
        # Process commits
        results = await simulate_commit_processing()
        
        # Display results
        display_production_results(results)
        
        print(f"\n🎉 DEMO COMPLETE")
        print("=" * 60)
        print("✅ All commits processed successfully")
        print("✅ AI analysis completed for all commits")
        print("✅ Database records would be created in production")
        print("\nThis demonstrates the full commit analysis pipeline!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 