import { XIcon } from "lucide-react";
import { useImageAttachments } from "@/lib/useImageAttachments";

export function ImageAttachmentPreview() {
  const { images, removeImage } = useImageAttachments();

  if (images.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 px-3 pb-2">
      {images.map((img) => (
        <div key={img.id} className="relative group">
          <img
            src={img.preview}
            alt={img.name}
            className="h-16 w-16 rounded-lg object-cover border border-border"
          />
          <button
            onClick={() => removeImage(img.id)}
            className="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label="Remove image"
          >
            <XIcon className="size-3" />
          </button>
        </div>
      ))}
    </div>
  );
}

