import { ImageOff } from 'lucide-react';

interface EmptyStateProps {
    title?: string;
    description?: string;
}

export function EmptyState({
    title = '暂无内容',
    description = '这里还没有任何内容'
}: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-background-secondary flex items-center justify-center mb-4">
                <ImageOff className="text-foreground-subtle" size={28} />
            </div>
            <p className="text-foreground font-medium mb-1">{title}</p>
            <p className="text-sm text-foreground-muted">{description}</p>
        </div>
    );
}
