import os
import asyncio
import json
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

# Control flow components
from openjiuwen.core.component.branch_comp import BranchComponent
from openjiuwen.core.component.loop_comp import LoopComponent, LoopGroup, BreakComponent
from openjiuwen.core.component.set_variable_comp import SetVariableComponent

# Custom components
from components import CondaEnvSaverComponent, CrossPlatformCommandExecutor, RequirementScannerComponent, PythonEnvTestExecutor

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


def env_check_workflow() -> Workflow:
    """
    环境包检查工作流 V2.1 (With Debug Loop)
    1. Scanner: 读取 repo 中的依赖
    2. LLM Generate: 生成完整的 Python 验证脚本
    3. Test Loop (Max 3 retries):
       a. Executor: 执行测试脚本
       b. Judge: 判断结果
       c. Check: 成功则退出，失败则尝试修复 (Debug)
          - Generate Fix (LLM)
          - Execute Fix (Shell)
    """
    metadata = WorkflowMetadata(
        id="EnvCheck_Flow_v2",
        name="EnvCheck Flow V2",
        description="Scan reqs -> generate python script -> test loop (execute -> judge -> debug fix).",
        version="2.1.0"
    )

    inputs_schema = WorkflowInputsSchema(
        type="object",
        properties={
            "user_inputs": {
                "type": "object",
                "properties": {
                    "env_name": {"type": "string", "required": True},
                    "repo_path": {"type": "string", "required": True}
                }
            }
        }
    )

    config = WorkflowConfig(
        metadata=metadata,
        workflow_inputs_schema=inputs_schema
    )

    flow = Workflow(workflow_config=config)
    model_config = _get_model_config()

    # Start Node
    flow.set_start_comp(
        "start",
        Start(),
        inputs_schema={
            "env_name": "${user_inputs.env_name}",
            "repo_path": "${user_inputs.repo_path}",
        }
    )

    # Step 1: Scanner
    flow.add_workflow_comp(
        "scanner",
        RequirementScannerComponent(),
        inputs_schema={
            "repo_path": "${start.repo_path}"
        }
    )

    # Step 2: Generate Script
    generate_script_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": """You are a Python Environment QA Specialist.
Your task is to generate a robust Python script to verify that a list of required packages are installed and importable.

Requirements:
1. The script should iterate through the required packages.
2. Use a `try-except` block for each import to prevent the script from crashing on the first failure.
3. If import succeeds, print "CHECK_SUCCESS: <package_name>".
4. If import fails, print "CHECK_FAILED: <package_name> Error: <error_message>".
5. Handle package name to import name mapping (e.g., 'scikit-learn' -> 'sklearn', 'beautifulsoup4' -> 'bs4') intelligently.
6. SKIP validation for packages that cannot be imported directly (e.g., 'swebench', command-line tools). For these, print "CHECK_SKIPPED: <package_name>".
7. The output must be valid, executable Python code.
"""
            },
            {
                "role": "user",
                "content": """Requirements List:
{{requirements_context}}

Generate the python verification script."""
            }
        ],
        response_format={"type": "json"},
        output_config={
            "script_content": {"type": "string", "description": "The python script code", "required": True},
            "description": {"type": "string", "description": "Brief description", "required": True}
        }
    )

    flow.add_workflow_comp(
        "generate_script",
        LLMComponent(generate_script_config),
        inputs_schema={
            "requirements_context": "${scanner.requirements_context}"
        }
    )

    # Step 3: Test Loop
    test_loop = LoopGroup()

    # 3a. Execute Script
    test_loop.add_workflow_comp(
        "execute_script",
        PythonEnvTestExecutor(),
        inputs_schema={
            "env_name": "${test_loop.env_name}",
            "repo_path": "${test_loop.repo_path}",
            "script_content": "${test_loop.script_content}"
        }
    )

    # 3b. Judge Result
    judge_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": """You are an automated test reporter.
Analyze the stdout/stderr from the package verification script.
Determine which packages passed and which failed. Treat "CHECK_SKIPPED" as a pass or ignore it (do not mark as failure).
Output a JSON summary."""
            },
            {
                "role": "user",
                "content": """Script Description: {{description}}
Executed Command: {{executed_command}}

Execution Result:
Success: {{success}}
Stdout:
{{stdout}}

Stderr:
{{stderr}}

Please provide a structured report in JSON format."""
            }
        ],
        response_format={"type": "json"},
        output_config={
            "all_passed": {"type": "boolean", "description": "True if all attempted imports succeeded", "required": True},
            "passed_packages": {"type": "array", "items": {"type": "string"}, "description": "List of packages that passed", "required": True},
            "failed_packages": {"type": "array", "items": {"type": "string"}, "description": "List of packages that failed", "required": True},
            "summary": {"type": "string", "description": "A concise text summary of the results", "required": True}
        }
    )

    test_loop.add_workflow_comp(
        "judge_result",
        LLMComponent(judge_config),
        inputs_schema={
            "description": "${test_loop.description}",
            "executed_command": "${execute_script.executed_command}",
            "success": "${execute_script.success}",
            "stdout": "${execute_script.stdout}",
            "stderr": "${execute_script.stderr}"
        }
    )

    # 3c. Check Result (Branch)
    check_result_comp = BranchComponent()
    check_result_comp.add_branch(
        condition='${judge_result.all_passed} == True',
        target="break_loop",
        branch_id="success"
    )
    check_result_comp.add_branch(
        condition='${judge_result.all_passed} == False',
        target="bug_solve",
        branch_id="failure"
    )
    test_loop.add_workflow_comp("check_result", check_result_comp)

    # 3d. Break Loop (Success)
    test_loop.add_workflow_comp(
        "break_loop",
        BreakComponent()
    )

    # 3e. Generate Fix (Debug)
    fix_config = LLMCompConfig(
        model=model_config,
        template_content=[
            {
                "role": "system",
                "content": """You are a debugging assistant.
The Python environment verification failed. Analyze the error report.
If packages are missing, provide a shell command to install them.
IMPORTANT: The environment is managed by Conda. You MUST use `conda run -n <env_name> pip install ...` or `conda install -n <env_name> ...` to ensure packages are installed in the correct environment.
Return a single string command in the JSON field `fix_command`.
"""
            },
            {
                "role": "user",
                "content": """Environment: {{env_name}}
Failed Packages: {{failed_packages}}
Summary: {{summary}}

Provide the fix command."""
            }
        ],
        response_format={"type": "json"},
        output_config={
            "fix_command": {"type": "string", "description": "Shell command to fix the environment", "required": True}
        }
    )

    test_loop.add_workflow_comp(
        "bug_solve",
        LLMComponent(fix_config),
        inputs_schema={
            "env_name": "${test_loop.env_name}",
            "failed_packages": "${judge_result.failed_packages}",
            "summary": "${judge_result.summary}"
        }
    )

    # 3f. Execute Fix
    test_loop.add_workflow_comp(
        "execute_fix",
        CrossPlatformCommandExecutor(),
        inputs_schema={
            "command": "${bug_solve.fix_command}",
            "timeout": 300
        }
    )

    # 3g. Update Loop Variables (Prepare next iteration)
    test_loop.add_workflow_comp(
        "set_var",
        SetVariableComponent({
            "${test_loop.env_name}": "${test_loop.env_name}",
            "${test_loop.repo_path}": "${test_loop.repo_path}",
            "${test_loop.script_content}": "${test_loop.script_content}",
            "${test_loop.description}": "${test_loop.description}"
        })
    )

    # Define loop topology
    test_loop.add_connection("execute_script", "judge_result")
    test_loop.add_connection("judge_result", "check_result")
    
    # Branching is handled by BranchComponent internal logic, but we need to start/end nodes
    test_loop.start_nodes(["execute_script"])
    
    # Explicit connections for branch outcomes
    test_loop.add_connection("bug_solve", "execute_fix")
    test_loop.add_connection("execute_fix", "set_var")
    # Loop back happens implicitly after set_var? No, SetVariableComponent usually loops back if it's the end of a path but not a Break.
    # The LoopComponent re-executes start_nodes if not broken.
    
    test_loop.end_nodes(["break_loop", "set_var"])

    # Create Loop Component
    test_loop_comp = LoopComponent(
        test_loop,
        output_schema={
            "final_report": "${judge_result}",
            "execution_output": "${execute_script.stdout}"
        }
    )

    flow.add_workflow_comp(
        "test_loop",
        test_loop_comp,
        inputs_schema={
            "loop_type": "number",
            "loop_number": 3,
            "intermediate_var": {
                "env_name": "${start.env_name}",
                "repo_path": "${start.repo_path}",
                "script_content": "${generate_script.script_content}",
                "description": "${generate_script.description}"
            }
        }
    )

    # End Node
    flow.set_end_comp(
        "end",
        End(),
        inputs_schema={
            "env_name": "${start.env_name}",
            "repo_path": "${start.repo_path}",
            "requirements_found": "${scanner.requirements_context}",
            "generated_script": "${generate_script.script_content}",
            "execution_output": "${test_loop.execution_output}",
            "final_report": "${test_loop.final_report}"
        }
    )

    # Connections
    flow.add_connection("start", "scanner")
    flow.add_connection("scanner", "generate_script")
    flow.add_connection("generate_script", "test_loop")
    flow.add_connection("test_loop", "end")

    return flow


def _build_test_agent() -> WorkflowAgent:
    workflow = env_check_workflow()
    model_config = _get_model_config()

    schema = WorkflowSchema(
        id=workflow.config().metadata.id,
        name=workflow.config().metadata.name,
        version=workflow.config().metadata.version,
        description=workflow.config().metadata.description,
        inputs={"user_inputs": {"type": "dict"}},
    )

    agent_config = WorkflowAgentConfig(
        id="test_env_agent_v2",
        version="2.1.0",
        description="Agent that checks environment packages from repo requirements (Robust)",
        workflows=[schema],
        model=model_config,
    )

    agent = WorkflowAgent(agent_config)
    agent.add_workflows([workflow])
    return agent


async def main():
    agent = _build_test_agent()
    
    # Test params
    env_name = "swe-bench-live" 
    base_dir = os.path.join(os.getcwd(), "tests", "fixtures")
    repo_path = os.path.join(base_dir, "SWE")
    if not os.path.exists(repo_path):
        repo_path = os.getcwd()

    print(f"Starting Test Agent (V2.1 Robust)...")
    print(f"Target Environment: {env_name}")
    print(f"Target Repository: {repo_path}")
    print("=" * 70)

    try:
        result = await agent.invoke({
            "user_inputs": {
                "env_name": env_name,
                "repo_path": repo_path
            }
        })

        if isinstance(result, dict) and 'output' in result:
            output = result['output']
            
            if hasattr(output, 'result') and isinstance(output.result, dict):
                data = output.result.get('output', {})
                
                report = data.get('final_report', {})
                
                # Handle potential list from LoopComponent (taking the last iteration's result)
                if isinstance(report, list) and len(report) > 0:
                    report = report[-1]

                if isinstance(report, str):
                    try:
                        report = json.loads(report)
                    except:
                        report = {"summary": "Failed to parse report", "all_passed": False}
                
                if not isinstance(report, dict):
                    report = {"summary": f"Invalid report format: {type(report)}", "all_passed": False}

                print(f"\n📊 Test Report:")
                print(f"  Summary: {report.get('summary', 'No summary')}")
                print(f"  Passed: {len(report.get('passed_packages', []))}")
                print(f"  Failed: {len(report.get('failed_packages', []))}")
                
                if report.get('failed_packages'):
                    print(f"  ⚠️ Failed Packages: {', '.join(report.get('failed_packages'))}")
                
                if report.get('all_passed'):
                    print("\n  ✅ Environment Verification Passed!")
                else:
                    print("\n  ❌ Environment Verification Failed!")

            else:
                print("Error: Invalid output format from workflow.")
                print(result)
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
