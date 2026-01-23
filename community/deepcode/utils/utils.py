
import json
import re

def extract_clean_json(llm_output: str) -> str:
    """
    从LLM输出中提取干净的JSON字符串，依次尝试多种提取策略

    Args:
        llm_output: LLM生成的原始输出字符串

    Returns:
        str: 提取的有效JSON字符串，若所有策略失败则返回原始输出
    """
    # 策略1：尝试直接解析整个输出
    def try_full_parse(text: str) -> str | None:
        try:
            text = text.strip()
            json.loads(text)
            return text
        except (json.JSONDecodeError, ValueError):
            return None

    result = try_full_parse(llm_output)
    if result:
        return result

    # 策略2：提取Markdown JSON代码块
    def extract_markdown_json(text: str) -> str | None:
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
            return try_full_parse(json_text)
        return None

    result = extract_markdown_json(llm_output)
    if result:
        return result

    # 策略3：按行匹配JSON对象（括号计数法）
    def extract_line_based_json(text: str) -> str | None:
        lines = text.split("\n")
        json_lines = []
        in_json = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()
            if not in_json:
                if stripped.startswith("{"):
                    in_json = True
                    json_lines = [line]
                    brace_count = stripped.count("{") - stripped.count("}")
            else:
                json_lines.append(line)
                brace_count += stripped.count("{") - stripped.count("}")
                if brace_count == 0:
                    break

        if json_lines:
            json_text = "\n".join(json_lines).strip()
            return try_full_parse(json_text)
        return None

    result = extract_line_based_json(llm_output)
    if result:
        return result

    # 策略4：正则表达式匹配JSON结构（递归匹配花括号）
    def extract_regex_json(text: str) -> str | None:
        # 改进的正则表达式，支持嵌套花括号（非完全严谨，但更实用）
        pattern = r"\{(?:[^{}]|(?R))*\}"
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            parsed = try_full_parse(match)
            if parsed:
                return parsed
        return None

    result = extract_regex_json(llm_output)
    if result:
        return result

    # 所有策略失败，返回原始输出
    return llm_output