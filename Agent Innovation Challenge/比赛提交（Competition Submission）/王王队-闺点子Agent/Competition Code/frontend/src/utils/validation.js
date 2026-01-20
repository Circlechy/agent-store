import config from "../config/app.config.js";

export function validateQuery(query) {
  const trimmed = query?.trim?.() || "";
  if (!trimmed) {
    return { valid: false, error: "请输入有效的查询内容。" };
  }
  if (trimmed.length < config.validation.minQueryLength) {
    return { valid: false, error: "查询内容过短，请输入至少一个字符。" };
  }
  if (trimmed.length > config.validation.maxQueryLength) {
    return { valid: false, error: "查询内容过长，请缩短后再试。" };
  }
  if (config.validation.forbiddenChars.test(trimmed)) {
    return { valid: false, error: "查询内容包含非法字符，请检查后重新提交。" };
  }
  return { valid: true, error: null };
}
