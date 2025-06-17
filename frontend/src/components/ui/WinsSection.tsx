import React from 'react';
import { Card } from '@/components/ui/card';
import { Trophy } from 'lucide-react';

interface WinsSectionProps {
  wins: string[];
  className?: string;
}

export const WinsSection: React.FC<WinsSectionProps> = ({
  wins,
  className = ""
}) => {
  return (
    <Card className={`p-6 bg-yellow-100 border-yellow-200 ${className}`}>
      <h3 className="text-lg font-medium mb-6 text-center bg-slate-700 text-white py-2 rounded flex items-center justify-center gap-2">
        <Trophy className="h-5 w-5" />
        Wins
      </h3>
      
      <div className="space-y-4">
        {wins.length > 0 ? (
          wins.map((win, index) => (
            <div key={index} className="bg-yellow-200 p-3 rounded-lg border border-yellow-300">
              <p className="text-sm font-medium text-yellow-900">
                {win}
              </p>
            </div>
          ))
        ) : (
          <div className="text-center text-muted-foreground">
            <Trophy className="h-8 w-8 mx-auto mb-2 text-yellow-600" />
            <p>No wins recorded this week</p>
          </div>
        )}
      </div>
    </Card>
  );
}; 