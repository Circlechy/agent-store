import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Settings as SettingsIcon } from "lucide-react";

export function Settings() {
  const [backendUrl, setBackendUrl] = useState("");
  const [language, setLanguage] = useState("en");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Load settings from chrome.storage
    if (chrome?.storage?.sync) {
      chrome.storage.sync.get(["backendUrl", "language"], (items) => {
        if (chrome.runtime.lastError) {
          console.error("Error loading settings:", chrome.runtime.lastError);
        } else {
          if (items.backendUrl) {
            setBackendUrl(items.backendUrl);
            console.log("Backend URL loaded from storage");
          } else {
            console.log("No backend URL found in storage");
          }
          if (items.language) {
            setLanguage(items.language);
            console.log("Language loaded from storage:", items.language);
          }
        }
      });
    } else {
      console.error("Chrome storage API is not available");
    }
  }, []);

  const handleSave = () => {
    if (!backendUrl.trim()) {
      alert("Please enter a backend URL");
      return;
    }

    // Validate URL format
    try {
      new URL(backendUrl.trim());
    } catch {
      alert("Please enter a valid URL (e.g., http://localhost:8000)");
      return;
    }

    chrome.storage.sync.set(
      {
        backendUrl: backendUrl.trim(),
        language: language,
      },
      () => {
        if (chrome.runtime.lastError) {
          console.error("Error saving settings:", chrome.runtime.lastError);
          alert("Failed to save settings: " + chrome.runtime.lastError.message);
        } else {
          console.log("Settings saved successfully");
          setOpen(false);
          // Reload the page to ensure the new settings are picked up
          window.location.reload();
        }
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon">
          <SettingsIcon className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{language === "zh" ? "设置" : "Settings"}</DialogTitle>
          <DialogDescription>
            {language === "zh"
              ? "配置您的代理设置，包括后端 URL 和语言偏好。"
              : "Configure your agent settings including backend URL and language preference."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label htmlFor="backend-url" className="text-sm font-medium">
              {language === "zh" ? "后端 URL" : "Backend URL"}
            </label>
            <Input
              id="backend-url"
              type="url"
              placeholder={
                language === "zh"
                  ? "例如：http://localhost:8000"
                  : "e.g., http://localhost:8000"
              }
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {language === "zh" ? (
                <>
                  输入您的 Python 后端的基础 URL。扩展将向{" "}
                  <code>{backendUrl || "..."}/v1/chat/stream</code> 发送 POST 请求
                </>
              ) : (
                <>
                  Enter the base URL of your Python backend. The extension will POST
                  to <code>{backendUrl || "..."}/v1/chat/stream</code>
                </>
              )}
            </p>
          </div>

          <div className="space-y-2">
            <label htmlFor="language" className="text-sm font-medium">
              {language === "zh" ? "语言" : "Language"}
            </label>
            <select
              id="language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="en">English</option>
              <option value="zh">中文 (Chinese)</option>
            </select>
            <p className="text-xs text-muted-foreground">
              {language === "zh"
                ? "选择代理响应的首选语言。"
                : "Choose your preferred language for the agent responses."}
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              {language === "zh" ? "取消" : "Cancel"}
            </Button>
            <Button onClick={handleSave}>{language === "zh" ? "保存" : "Save"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
