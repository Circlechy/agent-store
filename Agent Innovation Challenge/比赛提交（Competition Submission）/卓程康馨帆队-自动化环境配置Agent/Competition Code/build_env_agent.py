import os
import asyncio

from components import CreateEnvComponent, BuildEnvComponent
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.branch_comp import BranchComponent
from openjiuwen.core.component.loop_comp import LoopComponent, LoopGroup, BreakComponent
from openjiuwen.core.component.set_variable_comp import SetVariableComponent
from openjiuwen.core.runtime.workflow import WorkflowRuntime


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
            timeout=30  # 添加超时设置
        )
    )


def _build_workflow() -> Workflow:
    """
    Build a workflow for setting up an environment agent.

    Returns:
        Workflow: The constructed workflow object.
    """
    # Define the metadata for the workflow
    metadata = WorkflowMetadata(
        id="create_env_workflow_001",
        name="Environment Creating Flow",
        description="A workflow to create an environment.",
        version="1.0.0"
    )

    # Define the input schema for the workflow
    inputs_schema = WorkflowInputsSchema(
        type="object",
        properties={
            "env_name": {"type": "string", "description": "Name of the environment to create", "required": True},
            "version": {"type": "string", "description": "Python version (e.g. python=3.8)", "required": True},
            "args": {"type": "string", "description": "Additional arguments for environment setup", "required": True}
        }
    )

    # Create the workflow configuration
    config = WorkflowConfig(
        metadata=metadata,
        workflow_inputs_schema=inputs_schema
    )

    # Instantiate and return the workflow
    flow = Workflow(workflow_config=config)

    model_config = _get_model_config()
    llm_comp_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": "You are an expert in debugging environment setup issues."
            },
            {
                "role": "user",
                "content": "The following error occurred during environment setup: {{query}}. Please provide a solution. You must respond in JSON format with 'precommand' and 'version' fields. The 'precommand' field should contain any necessary commands to fix the issue, and the 'version' field should specify the correct Python version information, such as \"python=3.10\"."
            }
        ],
        response_format={"type": "json"},
        output_config={
            "precommand": {"type": "string", "description": "The precommand to execute before environment setup.", "required": True},
            "version": {"type": "string", "description": "The version information for the environment setup.", "required": True}
        }
    )
    flow.set_start_comp(
        "s",
        Start(),
        inputs_schema={
            "env_name": "${user_inputs.env_name}",
            "version": "${user_inputs.version}",
            "args": "${user_inputs.args}",
            "precommand": None  # Initialize precommand as None for first iteration
        }
    )
    create_loop = LoopGroup()
    create_loop.add_workflow_comp(
        "create_env",
        CreateEnvComponent(),
        inputs_schema={
            "env_name": "${create_loop.env_name}",
            "precommand": "${create_loop.precommand}",
            "version": "${create_loop.version}"
        }
    )
    create_check_comp = BranchComponent()
    create_check_comp.add_branch(
        condition='"Failed!!!" in ${create_env.result}',
        target="bug_solve_1",
        branch_id="error_branch"
    )
    break_node = BreakComponent()
    create_loop.add_workflow_comp("break", break_node)
    create_check_comp.add_branch(
        condition='"Failed!!!" not in ${create_env.result}',
        target="break",
        branch_id="success_branch"
    )
    create_loop.add_workflow_comp("create_check", create_check_comp)
    create_loop.add_workflow_comp(
        "bug_solve_1",
        LLMComponent(llm_comp_config),
        inputs_schema={"query": "${create_env.result}"}
    )
    create_loop.add_workflow_comp(
        "set_var",
        SetVariableComponent({
            "${create_loop.env_name}": "${create_env.env_name}",
            "${create_loop.precommand}": "${bug_solve_1.precommand}",
            "${create_loop.version}": "${bug_solve_1.version}"
        }),
    )
    create_loop.add_connection("create_env", "create_check")
    create_loop.add_connection("bug_solve_1", "set_var")
    create_loop.start_nodes(["create_env"])
    create_loop.end_nodes(["set_var"])
    create_loop_comp = LoopComponent(
        create_loop,
        output_schema={
            "env_name": "${create_env.env_name}",
            "result": "${create_env.result}",
        }
    )
    flow.add_workflow_comp(
        "create_loop",
        create_loop_comp,
        inputs_schema={
            "loop_type": "number",
            "loop_number": 3,
            "intermediate_var": {
                "env_name": "${s.env_name}",
                "version": "${s.version}",
                "precommand": "${s.precommand}"
            }
        }
    )
    build_loop = LoopGroup()
    build_loop.add_workflow_comp(
        "build_env",
        BuildEnvComponent(),
        inputs_schema={
            "env_name": "${build_loop.env_name}",
            "commands": [
                "${build_loop.args}"
            ]
        }
    )
    build_check_comp = BranchComponent()
    build_check_comp.add_branch(
        condition='"Failed" in ${build_env.result}',
        target="bug_solve_2",
        branch_id="error_branch"
    )
    break_node_2 = BreakComponent()
    build_loop.add_workflow_comp("break", break_node_2)
    build_check_comp.add_branch(
        condition='"Failed" not in ${build_env.result}',
        target="break",
        branch_id="success_branch"
    )
    build_loop.add_workflow_comp("build_check", build_check_comp)
    build_loop.add_workflow_comp(
        "bug_solve_2",
        LLMComponent(llm_comp_config),
        inputs_schema={"query": "${build_env.result}"}
    )
    build_loop.add_workflow_comp(
        "set_var_2",
        SetVariableComponent({
            "${build_loop.env_name}": "${build_env.env_name}",
            "${build_loop.args}": "${bug_solve_2.precommand}",
        }),
    )
    build_loop.add_connection("build_env", "build_check")
    build_loop.add_connection("bug_solve_2", "set_var_2")
    build_loop.start_nodes(["build_env"])
    build_loop.end_nodes(["set_var_2"])
    build_loop_comp = LoopComponent(
        build_loop,
        output_schema={
            "env_name": "${build_env.env_name}",
            "result": "${build_env.result}",
        }
    )
    flow.add_workflow_comp(
        "build_loop",
        build_loop_comp,
        inputs_schema={
            "loop_type": "number",
            "loop_number": 3,
            "intermediate_var": {
                "env_name": "${create_loop.env_name}",
                "args": "${s.args}"
            }
        }
    )
    flow.set_end_comp(
        "e",
        End(),
        inputs_schema={
            "env_name": "${build_loop.env_name}",
            "result": "${build_loop.result}"
        }
    )

    flow.add_connection("s", "create_loop")
    flow.add_connection("create_loop", "build_loop")
    flow.add_connection("build_loop", "e")

    

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
        description="环境创建工作流",
        inputs={"user_inputs": {"type": "dict"}},
    )
    agent_config = WorkflowAgentConfig(
        id="workflow_agent_123",
        version="0.1.0",
        description="环境创建 Agent",
        workflows=[schema],
        model=model_config,
    )
    agent = WorkflowAgent(agent_config)
    agent.add_workflows([workflow])
    return agent


async def main():
    agent = _build_workflow_agent()
    result = await agent.invoke({
        "user_inputs": {
            "env_name": "my_env",
            "version": "python=3.8",
            "args": "pip install tqdm"
        }
    })
    print("Workflow Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
