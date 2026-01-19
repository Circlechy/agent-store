/// <reference types="vite/client" />

declare namespace chrome {
  namespace storage {
    interface StorageArea {
      get(
        keys: string | string[] | { [key: string]: any } | null,
        callback: (items: { [key: string]: any }) => void
      ): void;
      set(items: { [key: string]: any }, callback?: () => void): void;
    }
    const sync: StorageArea;
  }
  namespace sidePanel {
    function setPanelBehavior(options: {
      openPanelOnActionClick: boolean;
    }): Promise<void>;
  }
}




