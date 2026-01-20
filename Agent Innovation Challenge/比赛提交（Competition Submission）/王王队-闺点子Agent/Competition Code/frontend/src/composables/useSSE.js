import { ref } from "vue";

import config from "../config/app.config.js";
import { getApiUrl } from "../utils/api.js";

const decoder = new TextDecoder();

/**
 * 解析 Python repr 格式的字符串为对象
 * 例如：message_id='xxx' agent='planner' content='...' => { message_id: 'xxx', agent: 'planner', content: '...' }
 */
function parsePythonRepr(str) {
  if (typeof str !== 'string') {
    return null;
  }
  
  
  const result = {};
  // 匹配 key='value' 或 key=数字 的模式
  const regex = /(\w+)=(?:'([^']*(?:\\.[^']*)*)'|(\d+))/g;
  let match;
  
  while ((match = regex.exec(str)) !== null) {
    const key = match[1];
    const stringValue = match[2];
    const numberValue = match[3];
    
    if (stringValue !== undefined) {
      // 字符串值，需要处理转义
      result[key] = stringValue.replace(/\\'/g, "'").replace(/\\n/g, "\n").replace(/\\\\/g, "\\");
    } else if (numberValue !== undefined) {
      // 数字值
      result[key] = parseInt(numberValue, 10);
    }
  }
  
  
  return Object.keys(result).length > 0 ? result : null;
}

export function useSSE() {
  const isConnected = ref(false);
  const isSearching = ref(false);
  const reconnectAttempts = ref(0);
  let controller = null;
  let stopRequested = false;
  let pendingQuery = null;

  const parseChunk = (raw) => {
    const lines = raw
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line);
    const dataLines = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.replace(/^data:\s*/, ""));
    if (!dataLines.length) {
      return null;
    }
    return dataLines.join("\n");
  };

  const handleStream = async ({ reader, onChunk, onComplete, onError }) => {
    let buffer = "";
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done || stopRequested) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const splits = buffer.split("\n\n");
        buffer = splits.pop() || "";
        for (const chunk of splits) {
          const payload = parseChunk(chunk);
          if (payload === null) {
            continue;
          }
          if (payload.trim() === "[DONE]") {
            await onComplete?.();
            return true;
          }
          try {
            const parsed = JSON.parse(payload);
            
            // 如果 JSON 解析的结果是字符串，说明是双重包装，需要再解析一次
            if (typeof parsed === 'string') {
              const pythonParsed = parsePythonRepr(parsed);
              if (pythonParsed) {
                await onChunk?.(pythonParsed);
              } else {
                await onChunk?.(parsed);
              }
            } else {
              // 正常的 JSON 对象
              await onChunk?.(parsed);
            }
          } catch (error) {
            // JSON 解析失败，直接尝试 Python repr
            const pythonParsed = parsePythonRepr(payload);
            if (pythonParsed) {
              await onChunk?.(pythonParsed);
            } else {
              console.warn('⚠️ 无法解析 payload:', payload.substring(0, 100));
              // 如果都无法解析，可能是纯文本，直接传递给 onChunk
              await onChunk?.(payload);
            }
          }
        }
      }
    } catch (error) {
      onError?.(error);
      return false;
    }
    return true;
  };

  const startSearch = async ({ query, file, action, onChunk, onComplete, onError }) => {
    if (isSearching.value) {
      return;
    }
    const currentInput = { query, file, action };
    reconnectAttempts.value = 0;
    stopRequested = false;
    isSearching.value = true;

    while (!stopRequested) {
      controller = new AbortController();
      let response;
      try {
        let url = getApiUrl("/search");
        let options = {
          method: "POST",
          signal: controller.signal
        };

        if (currentInput.action === 'screenshot') {
          url = getApiUrl("/search/screenshot");
          options.body = null; // 截屏接口无需发送体
        } else if (currentInput.file) {
          url = getApiUrl("/search/image");
          const formData = new FormData();
          formData.append('file', currentInput.file);
          options.body = formData;
          // 注意：FormData 不需要手动设置 Content-Type，fetch 会自动设置包含 boundary 的 header
        } else {
          options.headers = { "Content-Type": "application/json" };
          options.body = JSON.stringify({ query: currentInput.query });
        }

        response = await fetch(url, options);

        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          onError?.(
            new Error(
              payload?.message || "无法启动搜索，请稍后重试。"
            )
          );
          break;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("SSE 读取器不可用");
        }

        isConnected.value = true;
        const finished = await handleStream({ reader, onChunk, onComplete, onError });
        if (finished) {
          break;
        }
      } catch (error) {
        if (stopRequested) {
          break;
        }
        reconnectAttempts.value += 1;
        onError?.(error);
        if (reconnectAttempts.value >= config.sse.maxReconnectAttempts) {
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, config.sse.reconnectInterval));
      } finally {
        isConnected.value = false;
        controller = null;
      }
    }

    isSearching.value = false;
  };

  const stopSearch = () => {
    stopRequested = true;
    if (controller) {
      controller.abort();
    }
    isConnected.value = false;
    isSearching.value = false;
  };

  return {
    isConnected,
    isSearching,
    reconnectAttempts,
    startSearch,
    stopSearch
  };
}
