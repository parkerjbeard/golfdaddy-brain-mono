
import { useState } from 'react';
import { Card } from "@/components/ui/card";
import { KpiCard } from '@/components/ui/KpiCard';
import { Chart } from "@/components/ui/chart";
import { Progress } from "@/components/ui/progress";
import { companyKpis, departmentTaskCompletionData, dailyLogTrendData, achievements } from "@/data/mockData";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TrendingUp, TrendingDown, Minus, Trophy } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const CompanyDashboard = () => {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold mb-4">Company Dashboard</h1>
        <p className="text-muted-foreground mb-6">Overview of company performance metrics and achievements</p>
      </div>

      {/* Top-Level KPI Cards */}
      <div>
        <h2 className="text-lg font-medium mb-4">Key Performance Indicators</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {companyKpis.map((kpi) => (
            <KpiCard 
              key={kpi.id} 
              title={kpi.title} 
              value={kpi.value} 
              description={`Target: ${kpi.target}`} 
              trend={kpi.trend as 'up' | 'down' | 'neutral'} 
              percentageChange={kpi.change}
            />
          ))}
        </div>
      </div>

      {/* Company-Wide Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Department Task Completion Rates */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4">Department Task Completion Rates</h3>
          <Chart 
            data={departmentTaskCompletionData}
            type="bar"
            xKey="name"
            yKeys={[
              { key: "completed", name: "Completed", color: "#4f46e5" },
              { key: "target", name: "Target", color: "#a5b4fc" }
            ]}
            height={300}
          />
        </Card>

        {/* Daily Log Submission Trend */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4">Daily Log Submission Trend</h3>
          <Chart 
            data={dailyLogTrendData}
            type="line"
            xKey="date"
            yKeys={[
              { key: "count", name: "Submissions", color: "#06b6d4" }
            ]}
            height={300}
          />
        </Card>
      </div>

      {/* Quarterly Goals Progress */}
      <Card className="p-6">
        <h3 className="text-lg font-medium mb-6">Quarterly Goals Progress</h3>
        <div className="space-y-6">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">New Customer Acquisition</span>
              <span className="text-sm text-muted-foreground">75%</span>
            </div>
            <Progress value={75} className="h-2" />
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">Revenue Growth</span>
              <span className="text-sm text-muted-foreground">83%</span>
            </div>
            <Progress value={83} className="h-2" />
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">Platform Uptime</span>
              <span className="text-sm text-muted-foreground">99%</span>
            </div>
            <Progress value={99} className="h-2" />
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium">Customer Retention</span>
              <span className="text-sm text-muted-foreground">92%</span>
            </div>
            <Progress value={92} className="h-2" />
          </div>
        </div>
      </Card>

      {/* Recent Achievements / Milestones */}
      <div>
        <h2 className="text-lg font-medium mb-4">Recent Achievements</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[50px]"></TableHead>
                <TableHead>Achievement</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {achievements.map((achievement) => (
                <TableRow key={achievement.id}>
                  <TableCell className="w-[50px]">
                    <Trophy className="h-5 w-5 text-amber-500" />
                  </TableCell>
                  <TableCell className="font-medium">{achievement.title}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{achievement.department}</Badge>
                  </TableCell>
                  <TableCell>{achievement.date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    </div>
  );
};

export default CompanyDashboard;
