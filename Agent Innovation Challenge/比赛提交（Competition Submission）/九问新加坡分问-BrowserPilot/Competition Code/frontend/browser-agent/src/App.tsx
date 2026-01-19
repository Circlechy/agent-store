import { AssistantRuntimeProvider } from "@assistant-ui/react";
import type { ThreadMessage } from "@assistant-ui/react";
import { Thread } from "@/components/assistant-ui/thread";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Settings } from "@/components/Settings";
import { useCustomRuntime, clearPersistedMessages, loadPersistedMessages } from "@/lib/useCustomRuntime";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import { useState, useEffect } from "react";

function AppContent({ initialMessages }: { initialMessages: ThreadMessage[] }) {
  const runtime = useCustomRuntime(initialMessages);

  const handleNewChat = async () => {
    await clearPersistedMessages();
    window.location.reload();
  };

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-screen w-full flex-col">
        <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNewChat}
            title="New Chat"
            className="shrink-0"
          >
            <PlusIcon className="h-5 w-5" />
          </Button>
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage>Browser Agent</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <div className="ml-auto">
            <Settings />
          </div>
        </header>
        <div className="flex-1 overflow-hidden">
          <Thread />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}

function App() {
  const [initialMessages, setInitialMessages] = useState<ThreadMessage[] | null>(null);

  useEffect(() => {
    loadPersistedMessages().then(setInitialMessages);
  }, []);

  // Show loading screen while messages are being loaded
  if (initialMessages === null) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return <AppContent initialMessages={initialMessages} />;
}

export default App;

