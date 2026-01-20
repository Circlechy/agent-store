"""
Mermaid 流程图 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger
from typing import Dict, List

from app.utils.mermaid_generator import MermaidGenerator

router = APIRouter()
generator = MermaidGenerator()


class GenerateMermaidFromCodeRequest(BaseModel):
    """从代码生成 Mermaid 请求"""
    code: str


class GenerateMermaidFromWorkflowRequest(BaseModel):
    """从工作流数据生成 Mermaid"""
    workflow: dict


def _build_success_response(mermaid_code: str) -> Dict[str, str]:
    """构建成功响应"""
    return {
        "success": True,
        "mermaid": mermaid_code,
        "format": "mermaid"
    }


def _normalize_workflow_data(workflow: dict) -> Dict[str, List]:
    """标准化工作流数据格式"""
    nodes = [
        {
            "id": node.get("id", ""),
            "label": node.get("name", node.get("id", "")),
            "type": node.get("type", "process")
        }
        for node in workflow.get("nodes", [])
    ]
    
    edges = [
        {
            "from": edge.get("source", edge.get("from", "")),
            "to": edge.get("target", edge.get("to", "")),
            "label": edge.get("label", "")
        }
        for edge in workflow.get("edges", [])
    ]
    
    return {"nodes": nodes, "edges": edges}


def _handle_generation_error(e: Exception, context: str) -> None:
    """统一处理生成错误"""
    logger.error(f"生成 Mermaid 流程图失败 ({context}): {e}", exc_info=True)
    raise HTTPException(status_code=500, detail=f"生成流程图失败: {str(e)}")


@router.post("/generate-from-code")
async def generate_mermaid_from_code(request: GenerateMermaidFromCodeRequest):
    """从工作流代码生成 Mermaid 流程图"""
    try:
        mermaid_code = generator.generate_from_code(request.code)
        return _build_success_response(mermaid_code)
    except Exception as e:
        _handle_generation_error(e, "从代码生成")


@router.post("/generate-from-workflow")
async def generate_mermaid_from_workflow(request: GenerateMermaidFromWorkflowRequest):
    """从工作流数据生成 Mermaid 流程图"""
    try:
        workflow_data = _normalize_workflow_data(request.workflow)
        mermaid_code = generator.generate_mermaid(workflow_data)
        return _build_success_response(mermaid_code)
    except Exception as e:
        _handle_generation_error(e, "从工作流数据生成")
