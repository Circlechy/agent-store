import os
import asyncio

from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.branch_comp import BranchComponent
from openjiuwen.core.component.loop_comp import LoopComponent, LoopGroup, BreakComponent
from openjiuwen.core.component.set_variable_comp import SetVariableComponent
from openjiuwen.core.runtime.workflow import WorkflowRuntime

from components import GitCloneComponent


API_BASE = os.getenv("API_BASE", "https://api.modelarts-maas.com/openai/v1")
API_KEY = os.getenv(
    "API_KEY", "LMXROpI6RiTh5gxte1Wde_xO2W8fxr9NMhPIc4171EGFknANCm8-Mo9CQvXyNC38k0uT7zqTMla1S2h4wyICeQ")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-v3.2-exp")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
os.environ['LLM_SSL_VERIFY'] = 'false'
os.environ['RESTFUL_SSL_VERIFY'] = 'false'
os.environ['WORKFLOW_EXECUTE_TIMEOUT']= '300'


def _get_model_config() -> ModelConfig:
    return ModelConfig(
        model_provider=MODEL_PROVIDER,
        model_info=BaseModelInfo(
            model=MODEL_NAME,
            api_base=API_BASE,
            api_key=API_KEY,
            temperature=0.7,
            top_p=0.9,
            timeout=30
        )
    )


def _build_workflow() -> Workflow:
    """
    Build a workflow for git cloning.
    """
    metadata = WorkflowMetadata(
        id="git_clone_workflow_001",
        name="Git Clone Flow",
        description="A workflow to clone a git repository.",
        version="1.0.0"
    )

    inputs_schema = WorkflowInputsSchema(
        type="object",
        properties={
            "repo_url": {"type": "string", "description": "URL of the git repository", "required": True},
            "target_dir": {"type": "string", "description": "Local directory to clone into", "required": False},
            "token": {"type": "string", "description": "GitHub Personal Access Token", "required": False}
        }
    )

    config = WorkflowConfig(
        metadata=metadata,
        workflow_inputs_schema=inputs_schema
    )

    flow = Workflow(workflow_config=config)

    model_config = _get_model_config()
    llm_comp_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": "You are an expert in git version control and troubleshooting."
            },
            {
                "role": "user",
                "content": "The following error occurred during git clone: {{query}}. Please provide a solution. You must respond in JSON format with 'precommand' and 'repo_url' fields. The 'precommand' field should contain any necessary commands to fix the issue (e.g. git config settings), and the 'repo_url' field should contain the corrected URL if applicable, or the original URL."
            }
        ],
        response_format={"type": "json"},
        output_config={
            "precommand": {"type": "string", "description": "The command to fix the issue.", "required": True},
            "repo_url": {"type": "string", "description": "The repository URL to use.", "required": True}
        }
    )

    # Start Node
    flow.set_start_comp(
        "s",
        Start(),
        inputs_schema={
            "repo_url": "${user_inputs.repo_url}",
            "target_dir": "${user_inputs.target_dir}",
            "token": "${user_inputs.token}",
            "precommand": "" # Initialize precommand
        }
    )

    # Loop Group for Cloning
    clone_loop = LoopGroup()
    
    # Clone Component
    clone_loop.add_workflow_comp(
        "git_clone",
        GitCloneComponent(),
        inputs_schema={
            "repo_url": "${clone_loop.repo_url}",
            "target_dir": "${clone_loop.target_dir}",
            "token": "${s.token}",
            "precommand": "${clone_loop.precommand}"
        }
    )

    # Branch Component for Check
    check_comp = BranchComponent()
    
    # Error Branch
    check_comp.add_branch(
        condition='"Failed!!!" in ${git_clone.result}',
        target="error_solver",
        branch_id="error_branch"
    )
    
    # Success Branch (Break)
    break_node = BreakComponent()
    clone_loop.add_workflow_comp("break", break_node)
    
    check_comp.add_branch(
        condition='"Failed!!!" not in ${git_clone.result}',
        target="break",
        branch_id="success_branch"
    )
    
    clone_loop.add_workflow_comp("check_result", check_comp)

    # LLM Solver for Errors
    clone_loop.add_workflow_comp(
        "error_solver",
        LLMComponent(llm_comp_config),
        inputs_schema={"query": "${git_clone.result}"}
    )

    # Set Variable to update loop inputs from LLM
    clone_loop.add_workflow_comp(
        "set_var",
        SetVariableComponent({
            "${clone_loop.repo_url}": "${error_solver.repo_url}",
            "${clone_loop.precommand}": "${error_solver.precommand}",
        }),
    )

    # Connections inside loop
    clone_loop.add_connection("git_clone", "check_result")
    clone_loop.add_connection("error_solver", "set_var")
    
    clone_loop.start_nodes(["git_clone"])
    clone_loop.end_nodes(["set_var"])

    # Wrap LoopGroup in LoopComponent
    clone_loop_comp = LoopComponent(
        clone_loop,
        output_schema={
            "result": "${git_clone.result}",
            "repo_url": "${git_clone.repo_url}"
        }
    )

    # Add Loop Component to Workflow
    flow.add_workflow_comp(
        "clone_loop",
        clone_loop_comp,
        inputs_schema={
            "loop_type": "number",
            "loop_number": 3, # Retry up to 3 times
            "intermediate_var": {
                "repo_url": "${s.repo_url}",
                "target_dir": "${s.target_dir}",
                "precommand": "${s.precommand}"
            }
        }
    )

    # End Node
    flow.set_end_comp(
        "e",
        End(),
        inputs_schema={
            "result": "${clone_loop.result}",
            "repo_url": "${clone_loop.repo_url}"
        }
    )

    # Workflow Connections
    flow.add_connection("s", "clone_loop")
    flow.add_connection("clone_loop", "e")

    return flow


def _build_workflow_agent() -> WorkflowAgent:
    workflow = _build_workflow()
    model_config = _get_model_config()
    workflow_id = workflow.config().metadata.id
    workflow_name = workflow.config().metadata.name
    workflow_version = workflow.config().metadata.version
    
    schema = WorkflowSchema(
        id=workflow_id,
        name=workflow_name,
        version=workflow_version,
        description="Git Clone Agent Workflow",
        inputs={"user_inputs": {"type": "dict"}},
    )
    
    agent_config = WorkflowAgentConfig(
        id="git_agent_001",
        version="0.1.0",
        description="Agent for cloning git repositories",
        workflows=[schema],
        model=model_config,
    )
    
    agent = WorkflowAgent(agent_config)
    agent.add_workflows([workflow])
    return agent


async def main():
    agent = _build_workflow_agent()
    # Example usage
    # For actual CLI input in a real environment, uncomment these:
    # repo_url = input("Enter repo URL: ")
    # target_dir = input("Enter target dir (optional): ") or None
    # token = input("Enter GitHub Token (optional): ") or None
    
    # Hardcoded test default (commented out for safety)
    result = await agent.invoke({
        "user_inputs": {
            "repo_url": "https://github.com/microsoft/SWE-bench-Live.git",
            "target_dir": "./example_codes",
            "token": "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"
        }
    })
    print("Workflow Result:", result)
    
    # Keep it simple for the user to run

if __name__ == "__main__":
    asyncio.run(main())
