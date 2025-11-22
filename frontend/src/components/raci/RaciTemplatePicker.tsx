import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RaciMatrixTemplate, RaciMatrixType } from '@/types/entities';
import { cn } from '@/lib/utils';
import { Sparkles, Wand2, FilePlus } from 'lucide-react';

interface Props {
  templates: RaciMatrixTemplate[];
  selectedTemplateId?: string | null;
  selectedType?: RaciMatrixType;
  onSelectTemplate: (template: RaciMatrixTemplate) => void;
  onChooseCustom: () => void;
}

const typeLabels: Record<RaciMatrixType, string> = {
  [RaciMatrixType.INVENTORY_INBOUND]: 'Inventory Inbound',
  [RaciMatrixType.SHIPBOB_ISSUES]: 'ShipBob Issues',
  [RaciMatrixType.DATA_COLLECTION]: 'Data Collection',
  [RaciMatrixType.RETAIL_LOGISTICS]: 'Retail Logistics',
  [RaciMatrixType.CUSTOM]: 'Custom',
};

export const RaciTemplatePicker: React.FC<Props> = ({
  templates,
  selectedTemplateId,
  selectedType,
  onSelectTemplate,
  onChooseCustom,
}) => {
  const grouped = React.useMemo(() => {
    const map = new Map<RaciMatrixType, RaciMatrixTemplate[]>();
    templates.forEach((tpl) => {
      const list = map.get(tpl.matrix_type) || [];
      list.push(tpl);
      map.set(tpl.matrix_type, list);
    });
    return map;
  }, [templates]);

  return (
    <div className="space-y-4">
      {[...grouped.entries()].map(([type, group]) => (
        <div key={type} className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant={selectedType === type ? 'default' : 'outline'}>{typeLabels[type]}</Badge>
            <span className="text-sm text-muted-foreground">{group.length} template{group.length > 1 ? 's' : ''}</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {group.map((tpl) => (
              <Card
                key={tpl.template_id}
                className={cn(
                  'cursor-pointer transition hover:shadow-md',
                  selectedTemplateId === tpl.template_id && 'ring-2 ring-primary'
                )}
                onClick={() => onSelectTemplate(tpl)}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Sparkles className="h-4 w-4 text-primary" />
                    {tpl.name}
                  </CardTitle>
                  <CardDescription className="line-clamp-2">{tpl.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center gap-4 text-sm text-muted-foreground">
                  <Badge variant="secondary">{tpl.activities.length} activities</Badge>
                  <Badge variant="secondary">{tpl.roles.length} roles</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}

      <Card className="border-dashed">
        <CardHeader className="flex-row items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <FilePlus className="h-4 w-4" />
              Start from scratch
            </CardTitle>
            <CardDescription>Create a custom matrix with your own activities and roles.</CardDescription>
          </div>
          <Button variant="outline" type="button" onClick={onChooseCustom}>
            <Wand2 className="h-4 w-4 mr-2" />
            Custom
          </Button>
        </CardHeader>
      </Card>
    </div>
  );
};
