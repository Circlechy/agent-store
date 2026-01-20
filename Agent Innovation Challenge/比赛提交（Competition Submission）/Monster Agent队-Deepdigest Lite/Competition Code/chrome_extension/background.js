/**
 * DeepDigest Collector - Chrome Extension Background Script
 * 
 * 功能：右键菜单采集网页选中文字，发送到本地 DeepDigest API
 */

// ===================== 配置 =====================
const API_ENDPOINT = "http://localhost:8787/capture";

// ===================== 初始化：创建右键菜单 =====================
chrome.runtime.onInstalled.addListener(() => {
  // 创建右键菜单项
  chrome.contextMenus.create({
    id: "save_to_deepdigest",
    title: "🧠 存入 DeepDigest",
    contexts: ["selection"]  // 只在选中文字时显示
  });
  
  console.log("✅ DeepDigest Collector 插件已安装");
});

// ===================== 右键菜单点击事件 =====================
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "save_to_deepdigest") return;
  
  // 获取选中的文字
  const selectedText = info.selectionText;
  if (!selectedText || !selectedText.trim()) {
    console.warn("⚠️ 没有选中任何文字");
    showNotification(tab.id, "⚠️ 请先选中一些文字", "warning");
    return;
  }
  
  // 获取当前页面信息
  const pageUrl = tab.url || "";
  const pageTitle = tab.title || "";
  
  console.log("📡 正在发送到 DeepDigest...");
  console.log(`   标题: ${pageTitle}`);
  console.log(`   链接: ${pageUrl}`);
  console.log(`   内容: ${selectedText.substring(0, 100)}...`);
  
  try {
    // 发送 POST 请求到本地 API
    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: selectedText,
        url: pageUrl,
        title: pageTitle
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log("✅ 保存成功:", result);
      showNotification(tab.id, "✅ 已存入 DeepDigest", "success");
    } else {
      const error = await response.text();
      console.error("❌ 保存失败:", response.status, error);
      showNotification(tab.id, `❌ 保存失败: ${response.status}`, "error");
    }
  } catch (error) {
    console.error("❌ 网络错误:", error);
    showNotification(tab.id, "❌ 连接失败，请确保 DeepDigest API 已启动", "error");
  }
});

// ===================== 页面通知函数 =====================
/**
 * 在页面上显示通知提示
 * @param {number} tabId - 标签页 ID
 * @param {string} message - 通知消息
 * @param {string} type - 通知类型: success | warning | error
 */
async function showNotification(tabId, message, type = "success") {
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: (msg, notifyType) => {
        // 创建通知元素
        const notification = document.createElement("div");
        notification.id = "deepdigest-notification";
        
        // 根据类型设置背景色
        const bgColors = {
          success: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          warning: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
          error: "linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%)"
        };
        
        // 样式设置
        notification.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          padding: 16px 24px;
          background: ${bgColors[notifyType] || bgColors.success};
          color: white;
          font-size: 14px;
          font-weight: 600;
          border-radius: 12px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
          z-index: 2147483647;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          animation: slideIn 0.3s ease-out;
          cursor: pointer;
        `;
        
        // 添加动画样式
        const style = document.createElement("style");
        style.textContent = `
          @keyframes slideIn {
            from {
              transform: translateX(100%);
              opacity: 0;
            }
            to {
              transform: translateX(0);
              opacity: 1;
            }
          }
          @keyframes slideOut {
            from {
              transform: translateX(0);
              opacity: 1;
            }
            to {
              transform: translateX(100%);
              opacity: 0;
            }
          }
        `;
        document.head.appendChild(style);
        
        notification.textContent = msg;
        
        // 移除已存在的通知
        const existing = document.getElementById("deepdigest-notification");
        if (existing) existing.remove();
        
        document.body.appendChild(notification);
        
        // 点击关闭
        notification.onclick = () => {
          notification.style.animation = "slideOut 0.3s ease-in forwards";
          setTimeout(() => notification.remove(), 300);
        };
        
        // 3秒后自动消失
        setTimeout(() => {
          if (notification.parentNode) {
            notification.style.animation = "slideOut 0.3s ease-in forwards";
            setTimeout(() => notification.remove(), 300);
          }
        }, 3000);
      },
      args: [message, type]
    });
  } catch (error) {
    // 如果无法注入脚本（如 chrome:// 页面），忽略错误
    console.log("无法在此页面显示通知:", error.message);
  }
}
