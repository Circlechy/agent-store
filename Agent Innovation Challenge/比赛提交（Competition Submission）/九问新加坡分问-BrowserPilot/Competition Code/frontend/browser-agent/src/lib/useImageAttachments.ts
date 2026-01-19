import { create } from "zustand";

export interface ImageAttachment {
  id: string;
  name: string;
  mimeType: string;
  data: string; // base64 without prefix
  preview: string; // data URL for display
}

interface ImageAttachmentStore {
  images: ImageAttachment[];
  addImage: (file: File) => Promise<void>;
  removeImage: (id: string) => void;
  clearImages: () => void;
}

export const useImageAttachments = create<ImageAttachmentStore>((set) => ({
  images: [],

  addImage: async (file: File) => {
    if (!file.type.startsWith("image/")) return;

    const reader = new FileReader();
    const dataUrl = await new Promise<string>((resolve) => {
      reader.onload = () => resolve(reader.result as string);
      reader.readAsDataURL(file);
    });

    // Extract base64 data without the prefix
    const [header, base64Data] = dataUrl.split(",");
    const mimeType = header.match(/data:(.*?);/)?.[1] || file.type;

    const attachment: ImageAttachment = {
      id: crypto.randomUUID(),
      name: file.name || "pasted-image.png",
      mimeType,
      data: base64Data,
      preview: dataUrl,
    };

    set((state) => ({ images: [...state.images, attachment] }));
  },

  removeImage: (id: string) => {
    set((state) => ({ images: state.images.filter((img) => img.id !== id) }));
  },

  clearImages: () => {
    set({ images: [] });
  },
}));
