from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    消息模型：对话消息结构
    """
    role: str = Field(..., description="消息角色，例如 user / system / assistant")
    content: str = Field(..., description="消息内容")


class StepType(str, Enum):
    """
    步骤类型枚举
    """
    INFO_COLLECTING = "info_collecting"


class Step(BaseModel):
    '''
    步骤模型：表示计划中的具体执行单元
    '''
    type: StepType = Field(..., description="步骤类型（枚举值）")
    title: str = Field(..., description="步骤标题，简要描述步骤内容")
    description: str = Field(..., description="步骤详细说明，明确指定需要收集的数据或执行的编程步骤")
    step_result: Optional[str] = Field(default=None, description="步骤执行结果，完成后由系统进行填充")


class Plan(BaseModel):
    '''
    计划模型：包含实现目标所需的完整步骤序列和描述
    '''
    language: str = Field(default="zh-CN", description="用户语言：zh-CN、en-US等")
    title: str = Field(..., description="计划标题，概括整体目标")
    thought: str = Field(..., description="计划背后的思考过程，解释步骤顺序和选择的理由")
    is_research_completed: bool = Field(..., description="是否已完成信息收集工作")
    steps: List[Step] = Field(default_factory=list, description="具体执行的步骤")


class SearchContext(BaseModel):
    query: str = Field(default="", description="用户输入问题")
    image_path: str = Field(default="", description="用户上传的图片路径")
    language: str = Field(default="zh-CN", description="语言")
    messages: List[Message] = Field(default_factory=list, description="对话消息列表")

    collected_infos: List[str] = Field(default_factory=list, description="收集到的信息列表")
