"""工具模块"""


def normalize_agent_mode(agent_mode_str: str) -> str:
    """
    规范化 agent_mode 字符串，保持向后兼容
    
    Args:
        agent_mode_str: 原始 agent_mode 字符串
    
    Returns:
        规范化后的 agent_mode 字符串（react/workflow/multi_agent）
    """
    # 向后兼容：将 "agent" 映射到 "react"
    if agent_mode_str == "agent":
        return "react"
    return agent_mode_str