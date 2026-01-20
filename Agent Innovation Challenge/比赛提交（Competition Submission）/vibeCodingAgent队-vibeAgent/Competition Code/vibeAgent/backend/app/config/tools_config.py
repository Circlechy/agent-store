"""
工具配置管理

从 available_tools_info.json 加载可用工具列表，供规划阶段使用
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


def load_available_tools(config_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    加载可用工具列表
    
    Args:
        config_path: 配置文件路径（可选，默认使用 app/config/available_tools_info.json）
    
    Returns:
        工具列表，每个工具包含 id, name, description, category, method, path, params 等字段
    """
    if config_path is None:
        # 默认查找 app/config/available_tools_info.json
        config_path = Path(__file__).parent / "available_tools_info.json"
    
    if not config_path.exists():
        logger.warning(f"工具配置文件不存在: {config_path}，返回空列表")
        return []
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        if not config_data or "tools" not in config_data:
            logger.warning(f"工具配置文件格式错误: {config_path}，返回空列表")
            return []
        
        tools = config_data["tools"]
        logger.info(f"✅ 成功加载 {len(tools)} 个可用工具")
        return tools
    except json.JSONDecodeError as e:
        logger.error(f"解析工具配置文件失败: {config_path}, 错误: {e}")
        return []
    except Exception as e:
        logger.error(f"加载工具配置文件失败: {config_path}, 错误: {e}")
        return []


def _format_tool_params(params: Dict[str, Any]) -> str:
    """
    格式化工具参数信息
    
    Args:
        params: 参数字典，包含 properties 和 required 字段
    
    Returns:
        格式化的参数字符串
    """
    if not params or 'properties' not in params:
        return ""
    
    params_text = ""
    properties = params['properties']
    required = params.get('required', [])
    
    for param_name, param_info in properties.items():
        param_type = param_info.get('type', 'string')
        param_desc = param_info.get('description', '无描述')
        is_required = param_name in required
        required_str = "必需" if is_required else "可选"
        params_text += f"    - {param_name} ({param_type}, {required_str}): {param_desc}\n"
    
    return params_text


def format_tools_for_planning(tools: List[Dict[str, Any]]) -> str:
    """
    格式化工具列表，用于规划阶段的提示词
    
    Args:
        tools: 工具列表
    
    Returns:
        格式化的工具信息字符串
    """
    if not tools:
        return "可用工具列表：无（不使用工具）\n"
    
    tools_info = f"可用工具列表（共 {len(tools)} 个）：\n\n"
    
    for idx, tool in enumerate(tools, 1):
        tool_name = tool.get('name', 'unknown')
        tool_id = tool.get('id', 'unknown')
        tool_desc = tool.get('description', '无描述')
        tool_category = tool.get('category', '未分类')
        
        tools_info += f"工具 {idx}：{tool_name} (ID: {tool_id})\n"
        tools_info += f"  描述：{tool_desc}\n"
        tools_info += f"  类别：{tool_category}\n"
        
        # 参数信息
        params = tool.get('params', {})
        if params:
            params_text = _format_tool_params(params)
            if params_text:
                tools_info += "  参数：\n"
                tools_info += params_text
        
        # 备注信息
        if tool.get('notes'):
            tools_info += f"  备注：{tool.get('notes')}\n"
        
        tools_info += "\n"
    
    return tools_info


def get_tools_by_category(tools: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """
    根据类别筛选工具
    
    Args:
        tools: 工具列表
        category: 类别名称
    
    Returns:
        筛选后的工具列表
    """
    return [tool for tool in tools if tool.get('category') == category]


def get_tool_by_name(tools: List[Dict[str, Any]], tool_name: str) -> Optional[Dict[str, Any]]:
    """
    根据名称获取工具
    
    Args:
        tools: 工具列表
        tool_name: 工具名称
    
    Returns:
        工具字典，如果不存在则返回 None
    """
    return next((tool for tool in tools if tool.get('name') == tool_name), None)


def get_tool_by_id(tools: List[Dict[str, Any]], tool_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取工具
    
    Args:
        tools: 工具列表
        tool_id: 工具 ID
    
    Returns:
        工具字典，如果不存在则返回 None
    """
    return next((tool for tool in tools if tool.get('id') == tool_id), None)


# 全局工具列表缓存
_available_tools_cache: Optional[List[Dict[str, Any]]] = None


def get_available_tools(force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    获取可用工具列表（带缓存）
    
    Args:
        force_reload: 是否强制重新加载
    
    Returns:
        工具列表
    """
    global _available_tools_cache
    
    if _available_tools_cache is None or force_reload:
        _available_tools_cache = load_available_tools()
    
    return _available_tools_cache
