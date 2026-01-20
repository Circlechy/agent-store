import config from "../config/app.config.js";

const getApiUrl = (endpoint) => {
  const prefix = `/api/${config.apiVersion}`;
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${config.apiBaseUrl}${prefix}${normalizedEndpoint}`;
};

export async function checkHealth() {
  const response = await fetch(getApiUrl("/health"));
  if (!response.ok) {
    throw new Error("无法连接到后端服务");
  }
  return response.json();
}

export { getApiUrl };
