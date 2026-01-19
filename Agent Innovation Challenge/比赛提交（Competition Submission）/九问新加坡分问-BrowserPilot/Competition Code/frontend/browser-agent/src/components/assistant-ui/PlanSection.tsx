import { ListIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

interface PlanSectionProps {
  content: string;
}

/**
 * Extracts and displays the #PLAN# section from assistant messages
 */
export function PlanSection({ content }: PlanSectionProps) {
  const [isMinimized, setIsMinimized] = useState(false);

  if (!content) return null;

  // Look for #PLAN# section with more specific pattern
  // Match #PLAN# followed by numbered items until we hit a double newline or non-numbered line
  const planMatch = content.match(/#PLAN#\s*((?:\d+\..*\n?)*)/i);
  if (!planMatch) return null;

  // Extract numbered items from plan
  const planItems = planMatch[1]
    .split(/\n/)
    .filter((line) => /^\d+\./.test(line.trim()))
    .map((line) => line.trim());

  if (planItems.length === 0) return null;

  return (
    <div className="mb-4 rounded-lg border border-purple-200 bg-purple-50/50 dark:border-purple-800 dark:bg-purple-950/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-purple-100/50 dark:bg-purple-900/30 border-b border-purple-200 dark:border-purple-800">
        <ListIcon className="size-4 text-purple-600 dark:text-purple-400" />
        <span className="font-medium text-sm flex-grow">Plan</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 hover:bg-purple-200 dark:hover:bg-purple-800"
          onClick={() => setIsMinimized(!isMinimized)}
          title={isMinimized ? "Expand" : "Minimize"}
        >
          {isMinimized ? (
            <ChevronDownIcon className="size-3.5" />
          ) : (
            <ChevronUpIcon className="size-3.5" />
          )}
        </Button>
      </div>

      {/* Content - only show when not minimized */}
      {!isMinimized && (
        <div className="px-4 py-3">
          <ol className="space-y-2 list-none">
            {planItems.map((item, index) => {
              // Remove the number prefix for display
              const text = item.replace(/^\d+\.\s*/, '');
              return (
                <li key={index} className="text-sm flex gap-2">
                  <span className="text-purple-600 dark:text-purple-400 font-medium shrink-0">
                    {index + 1}.
                  </span>
                  <span className="text-muted-foreground">{text}</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
