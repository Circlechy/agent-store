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
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.component.base import WorkflowComponent
from openjiuwen.core.runtime.base import ComponentExecutable, Input, Output
from components import ReadmeScannerComponent, PlanDisplayComponent, PlanValidatorAndFallbackComponent


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
            temperature=0.7, # Lower temperature for planning
            top_p=0.9,
            timeout=60
        )
    )


def _build_workflow() -> Workflow:
    metadata = WorkflowMetadata(
        id="env_planning_workflow_001",
        name="Environment Planning Flow",
        description="Analyzes repo and plans environment setup with two-step approach: README first, then config files.",
        version="2.0.0"
    )

    inputs_schema = WorkflowInputsSchema(
        type="object",
        properties={
            "repo_path": {"type": "string", "description": "Local path to the repository", "required": True}
        }
    )

    config = WorkflowConfig(
        metadata=metadata,
        workflow_inputs_schema=inputs_schema
    )

    flow = Workflow(workflow_config=config)
    model_config = _get_model_config()

    # LLM for README-based planning
    readme_llm_comp_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": """You are an expert DevOps engineer and Python environment specialist.
Your task is to analyze the README file from a Python repository and extract installation instructions to generate a precise plan to set up the environment.

**⚠️ CRITICAL RULE: NEVER SIMPLIFY COMMANDS. Extract commands EXACTLY as written, character by character.**

You need to output a JSON object with exactly three fields:
1. "env_name": A suitable name for the conda environment (e.g., derived from the repo name).
2. "version": The python version string for conda create (e.g., "python=3.8"). If not specified in README, default to "python=3.10".
3. "args": The shell command string to install dependencies, prefixed with a directory change (e.g., "cd /path/to/repo && pip install ...").

NOTE: The system that executes your plan works in two steps:
Step 1: Run `conda create -n {env_name} {version} -y`
Step 2: Run `conda activate {env_name}` AND THEN execute your `{args}` command.

**MANDATORY EXTRACTION RULES:**
1. **PRIORITY: Look for sections titled "Installation", "Getting Started", "Setup", "Quick Start". The context may have an "INSTALLATION SECTION (PRIORITY)" marker - use that content first.**
2. **NEVER SIMPLIFY: If README shows `pip install -e ".[torch,metrics]" --no-build-isolation`, your output MUST be `cd <path> && pip install -e ".[torch,metrics]" --no-build-isolation`. NEVER output just `pip install -e .` or `pip install -e`**
3. **PRESERVE EVERYTHING: Keep ALL quotes, brackets, commas, flags, options, arguments exactly as written:**
   - `pip install -e ".[torch,metrics]" --no-build-isolation` → Keep ALL: `-e`, `".[torch,metrics]"`, `--no-build-isolation`
   - `pip install package[extra1,extra2] --flag` → Keep brackets, commas, flag
   - `pip install "package>=1.0" --index-url https://...` → Keep quotes, version, URL
4. **CHARACTER-BY-CHARACTER: Copy the installation command EXACTLY, then only prepend `cd <repo_path> && `**
5. **NO SHORTCUTS: Do NOT assume what the command "should" be. Use ONLY what is written in README.**

ALWAYS prepend `cd <repo_path> && ` to your args, where <repo_path> is the Target Repository Path found in the context. Use the exact path provided.
If README mentions specific Python version, use it for "version".
If README provides installation commands, convert them to your "args" format with the cd prefix, but keep ALL original command parts intact - every character, every flag, every option.
If the README specifies multiple installation steps, combine them properly with `&&` while preserving all original command details exactly.
If you cannot find clear installation instructions in the Installation/Getting Started sections, search other sections, but always preserve commands exactly as written.
"""
            },
            {
                "role": "user",
                "content": "README Analysis Context:\n{{context}}\n\nRepo Name Suggestion: {{repo_name}}\n\n**⚠️ CRITICAL INSTRUCTIONS:**\n1. **PRIORITY: Use the \"INSTALLATION SECTION (PRIORITY)\" if present in the context above.**\n2. **EXACT EXTRACTION: Extract installation commands EXACTLY as written - character by character.**\n3. **NO SIMPLIFICATION: If you see `pip install -e \".[torch,metrics]\" --no-build-isolation`, output `cd <path> && pip install -e \".[torch,metrics]\" --no-build-isolation`. NEVER simplify to `pip install -e .` or `pip install -e`.**\n4. **PRESERVE ALL: Keep ALL quotes, brackets [], commas, flags (--xxx), options (-x), and arguments exactly as shown.**\n5. **VERBATIM COPY: Copy the command exactly, then only prepend `cd <repo_path> && `**\n\nPlease analyze the README and provide the JSON plan. Extract the installation command EXACTLY as written in the README."
            }
        ],
        response_format={"type": "json"},
        output_config={
            "env_name": {"type": "string", "description": "Name of the environment", "required": True},
            "version": {"type": "string", "description": "Python version (e.g. python=3.9)", "required": True},
            "args": {"type": "string", "description": "Installation commands", "required": True}
        }
    )

    # LLM for config file-based planning (fallback)
    config_llm_comp_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": """You are an expert DevOps engineer and Python environment specialist.
Your task is to analyze the provided configuration file contents from a Python repository and generate a precise plan to set up the environment.

You need to output a JSON object with exactly three fields:
1. "env_name": A suitable name for the conda environment (e.g., derived from the repo name).
2. "version": The python version string for conda create (e.g., "python=3.8"). If not specified in files, default to "python=3.10".
3. "args": The shell command string to install dependencies, prefixed with a directory change (e.g., "cd /path/to/repo && pip install ...").

NOTE: The system that executes your plan works in two steps:
Step 1: Run `conda create -n {env_name} {version} -y`
Step 2: Run `conda activate {env_name}` AND THEN execute your `{args}` command.

Strategy:
- ALWAYS prepend `cd <repo_path> && ` to your args, where <repo_path> is the Target Repository Path found in the context. Use the exact path provided.
- If `environment.yml` exists: Extract the python version for "version", and set "args" to `cd <repo_path> && conda env update -n {env_name} -f environment.yml` (since the env is already created in Step 1, we just update/install deps).
- If `requirements.txt` exists: Set "args" to `cd <repo_path> && pip install -r requirements.txt`.
- If `setup.py` exists: Set "args" to `cd <repo_path> && pip install .` or `cd <repo_path> && pip install -e .`.
- If multiple exist, prioritize `environment.yml` > `requirements.txt`.
- If no config found, just return `pip install --upgrade pip` as a safe placeholder.
"""
            },
            {
                "role": "user",
                "content": "Repository Analysis Context:\n{{context}}\n\nRepo Name Suggestion: {{repo_name}}\n\nPlease provide the JSON plan based on configuration files."
            }
        ],
        response_format={"type": "json"},
        output_config={
            "env_name": {"type": "string", "description": "Name of the environment", "required": True},
            "version": {"type": "string", "description": "Python version (e.g. python=3.9)", "required": True},
            "args": {"type": "string", "description": "Installation commands", "required": True}
        }
    )

    # Start Node
    flow.set_start_comp(
        "s",
        Start(),
        inputs_schema={
            "repo_path": "${repo_path}"
        }
    )

    # Step 1: README Scanner
    flow.add_workflow_comp(
        "readme_scanner",
        ReadmeScannerComponent(),
        inputs_schema={
            "repo_path": "${s.repo_path}"
        }
    )

    # Step 2: README-based Planner
    flow.add_workflow_comp(
        "readme_planner",
        LLMComponent(readme_llm_comp_config),
        inputs_schema={
            "context": "${readme_scanner.context}",
            "repo_name": "${readme_scanner.repo_name}"
        }
    )
    
    # Step 2.5: Display README Plan
    flow.add_workflow_comp(
        "readme_plan_display",
        PlanDisplayComponent(),
        inputs_schema={
            "env_name": "${readme_planner.env_name}",
            "version": "${readme_planner.version}",
            "args": "${readme_planner.args}"
        }
    )

    # Step 3: Plan Validator and Fallback Handler
    # 这个组件会验证 README 生成的 plan，如果无效则自动执行回退到配置文件逻辑（使用LLM）
    flow.add_workflow_comp(
        "plan_validator_fallback",
        PlanValidatorAndFallbackComponent(config_llm_comp_config),
        inputs_schema={
            "env_name": "${readme_plan_display.env_name}",
            "version": "${readme_plan_display.version}",
            "args": "${readme_plan_display.args}",
            "repo_path": "${s.repo_path}",
            "repo_name": "${readme_scanner.repo_name}"
        }
    )

    # End Node
    flow.set_end_comp(
        "e",
        End(),
        inputs_schema={
            "env_name": "${plan_validator_fallback.env_name}",
            "version": "${plan_validator_fallback.version}",
            "args": "${plan_validator_fallback.args}"
        }
    )

    # Connections
    flow.add_connection("s", "readme_scanner")
    flow.add_connection("readme_scanner", "readme_planner")
    flow.add_connection("readme_planner", "readme_plan_display")
    flow.add_connection("readme_plan_display", "plan_validator_fallback")
    flow.add_connection("plan_validator_fallback", "e")

    return flow


def _build_workflow_agent() -> WorkflowAgent:
    workflow = _build_workflow()
    model_config = _get_model_config()
    
    schema = WorkflowSchema(
        id=workflow.config().metadata.id,
        name=workflow.config().metadata.name,
        version=workflow.config().metadata.version,
        description="Environment Planning Agent",
        inputs={"repo_path": {"type": "string"}},
    )
    
    agent_config = WorkflowAgentConfig(
        id="env_planner_agent_001",
        version="0.1.0",
        description="Agent for planning python environment setup",
        workflows=[schema],
        model=model_config,
    )
    
    agent = WorkflowAgent(agent_config)
    agent.add_workflows([workflow])
    return agent


async def main():
    agent = _build_workflow_agent()
    repo_path = "C:/Users/admin/Desktop/LLaMA-Factory-main"
    
    print("\n" + "="*60)
    print("="*60)
    
    result = await agent.invoke({"repo_path": repo_path})
    final_output = result.get('output').result.get('output')
    print(final_output)

if __name__ == "__main__":
    asyncio.run(main())