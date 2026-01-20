import os
import asyncio
import json
import subprocess
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.workflow_comp import SubWorkflowComponent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.common.schema import WorkflowSchema
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.utils.llm.base import BaseModelInfo

from components import CondaEnvSaverComponent

# Import existing workflow builders
# Assuming these files are in the same directory and in python path
try:
    from env_planning_agent import _build_workflow as get_planning_workflow
    from build_env_agent import _build_workflow as get_build_workflow
    from test_env_agent import env_check_workflow as get_test_workflow
    from git_clone_agent import _build_workflow as get_clone_workflow
except ImportError:
    # Fallback for running as a script where imports might need package prefix or path adjustment
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from env_planning_agent import _build_workflow as get_planning_workflow
    from build_env_agent import _build_workflow as get_build_workflow
    from test_env_agent import env_check_workflow as get_test_workflow
    from git_clone_agent import _build_workflow as get_clone_workflow

# Reuse configuration logic from existing agents
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
            timeout=60
        )
    )


def _build_merged_workflow() -> Workflow:
    """
    Builds the merged workflow containing planning, building, and testing sub-workflows.
    """
    # 1. Initialize Main Workflow
    metadata = WorkflowMetadata(
        id="merged_env_agent_workflow",
        name="Merged Environment Agent Workflow",
        description="Plans, builds, and tests environment using nested workflows.",
        version="1.0.1"
    )
    
    inputs_schema = WorkflowInputsSchema(
        type="object",
        properties={
            "repo_url": {"type": "string", "description": "URL of the git repository", "required": True},
            "repo_path": {"type": "string", "description": "Path to the repository", "required": True},
            "token": {"type": "string", "description": "GitHub Token", "required": False}
        }
    )

    config = WorkflowConfig(
        metadata=metadata,
        workflow_inputs_schema=inputs_schema
    )
    
    main_workflow = Workflow(workflow_config=config)

    # 2. Prepare Sub-Workflows
    clone_workflow = get_clone_workflow()
    planning_workflow = get_planning_workflow()
    build_workflow = get_build_workflow()
    test_workflow = get_test_workflow()

    # Wrap them in SubWorkflowComponent
    clone_comp = SubWorkflowComponent(clone_workflow)
    planning_comp = SubWorkflowComponent(planning_workflow)
    build_comp = SubWorkflowComponent(build_workflow)
    test_comp = SubWorkflowComponent(test_workflow)

    # 3. Add Components to Main Workflow
    
    # Start Node
    main_workflow.set_start_comp(
        "start", 
        Start(), 
        inputs_schema={
            "repo_url": "${user_inputs.repo_url}",
            "repo_path": "${user_inputs.repo_path}",
            "token": "${user_inputs.token}"
        }
    )

    # Git Clone Sub-Workflow Node
    main_workflow.add_workflow_comp(
        "clone_node",
        clone_comp,
        inputs_schema={
            "user_inputs": {
                "repo_url": "${start.repo_url}",
                "target_dir": "${start.repo_path}",
                "token": "${start.token}"
            }
        }
    )

    # Planning Sub-Workflow Node
    # Input: repo_path from start node
    main_workflow.add_workflow_comp(
        "planning_node",
        planning_comp,
        inputs_schema={
            "repo_path": "${start.repo_path}"
        }
    )

    # Build Sub-Workflow Node
    # Inputs: outputs from planning node
    main_workflow.add_workflow_comp(
        "build_node",
        build_comp,
        inputs_schema={
            "user_inputs":{
                "env_name": "${planning_node.output.env_name}",
                "version": "${planning_node.output.version}",
                "args": "${planning_node.output.args}"
            }
        }
    )

    # Test Sub-Workflow Node
    # Inputs: env_name from build node, repo_path from start node
    main_workflow.add_workflow_comp(
        "test_node",
        test_comp,
        inputs_schema={
            "user_inputs": {
                "env_name": "${planning_node.output.env_name}",
                "repo_path": "${start.repo_path}"
            }
        }
    )

    # Save Environment Node
    # Save the conda environment after testing
    main_workflow.add_workflow_comp(
        "save_env_node",
        CondaEnvSaverComponent(),
        inputs_schema={
            "env_name": "${planning_node.output.env_name}",
            "repo_path": "${start.repo_path}"
        }
    )

    # End Node
    # Output: results from all nodes (build, test, planning, save_env)
    main_workflow.set_end_comp(
        "end",
        End(),
        inputs_schema={
            "build_result": "${build_node.output.result}",
            "test_node_output": "${test_node}",
            "planning_result": "${planning_node}",
            "clone_result": "${clone_node.output.result}",
            "save_env_result": "${save_env_node}",
            "final_env_name": "${planning_node.output.env_name}"
        }
    )

    # 4. Define Topology (Connections)
    main_workflow.add_connection("start", "clone_node")
    main_workflow.add_connection("clone_node", "planning_node")
    main_workflow.add_connection("planning_node", "build_node")
    main_workflow.add_connection("build_node", "test_node")
    main_workflow.add_connection("test_node", "save_env_node")
    main_workflow.add_connection("save_env_node", "end")

    return main_workflow

def _build_merged_agent() -> WorkflowAgent:
    workflow = _build_merged_workflow()
    model_config = _get_model_config()
    
    schema = WorkflowSchema(
        id=workflow.config().metadata.id,
        name=workflow.config().metadata.name,
        version=workflow.config().metadata.version,
        description=workflow.config().metadata.description,
        inputs={"user_inputs": {"type": "dict"}},
    )
    
    agent_config = WorkflowAgentConfig(
        id="merged_env_agent",
        version="1.0.0",
        description="Agent that plans and builds environments",
        workflows=[schema],
        model=model_config,
    )
    
    agent = WorkflowAgent(agent_config)
    agent.add_workflows([workflow])
    return agent

async def main():
    agent = _build_merged_agent()
    
    # Use a default test path or ask user
    # For automation safety, we use a hardcoded path relative to current dir
    base_dir = os.path.join(os.getcwd(), "tests", "fixtures")
    repo_path = os.path.join(base_dir, "SWE")
    repo_url = "https://github.com/microsoft/SWE-bench-Live.git" 
    #repo_url = "https://github.com/mindspore-ai/mindspore.git"
    
    print(f"Starting Merged Agent with repo_path: {repo_path}")
    
    try:
        result = await agent.invoke({
            "user_inputs": {
                "repo_url": repo_url,
                "repo_path": repo_path,
                "token": ""
            }
        })
        

        # 解析并打印结果
        if isinstance(result, dict) and 'output' in result:
            output = result['output']
            
            if hasattr(output, 'result') and isinstance(output.result, dict):
                data = output.result.get('output', {})
                
                print("\n" + "=" * 70)
                print("📋 COMPLETE WORKFLOW RESULTS")
                print("=" * 70)
                
                # Clone Node Results
                if 'clone_result' in data:
                    clone_result = data.get('clone_result', {})
                    print("\n[1] CLONE NODE RESULTS:")
                    if isinstance(clone_result, dict):
                        clone_output = clone_result.get('output', {})
                        if 'success' in clone_output:
                            print(f"  Status: {'✅ Success' if clone_output['success'] else '❌ Failed'}")
                        if 'stdout' in clone_output:
                            print(f"  Output: {clone_output['stdout'][:200]}")
                    else:
                        print(f"  Result: {clone_result}")
                
                # Planning Node Results
                if 'planning_result' in data:
                    planning_result = data.get('planning_result', {})
                    print("\n[2] PLANNING NODE RESULTS:")
                    if isinstance(planning_result, dict):
                        planning_output = planning_result.get('output', {})
                        if 'env_name' in planning_output:
                            print(f"  Environment Name: {planning_output['env_name']}")
                        if 'version' in planning_output:
                            print(f"  Version: {planning_output['version']}")
                        if 'args' in planning_output:
                            print(f"  Args: {planning_output['args']}")
                    else:
                        print(f"  Result: {planning_result}")
                
                # Build Node Results
                if 'build_result' in data:
                    build_result = data.get('build_result', {})
                    print("\n[3] BUILD NODE RESULTS:")
                    if isinstance(build_result, dict):
                        build_output = build_result.get('output', {})
                        if 'success' in build_output:
                            print(f"  Status: {'✅ Success' if build_output['success'] else '❌ Failed'}")
                        if 'stdout' in build_output:
                            print(f"  Output: {build_output['stdout'][:200]}")
                        if 'stderr' in build_output and build_output['stderr']:
                            print(f"  Error: {build_output['stderr'][:200]}")
                    else:
                        print(f"  Result: {build_result}")
                
                # Test Node Results (aligned with test_env_agent)
                if 'test_node_output' in data:
                    test_result = data.get('test_node_output', {})
                    print("\n[4] TEST NODE RESULTS:")
                    
                    if isinstance(test_result, dict):
                        test_output = test_result.get('output', {})
                        
                        # Print intermediate results from test_env_agent
                        if 'env_name' in test_output:
                            print(f"  Environment Name: {test_output['env_name']}")
                        if 'repo_path' in test_output:
                            print(f"  Repository Path: {test_output['repo_path']}")

                        # Parse and display final report
                        report = test_output.get('final_report', {})
                        
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
                        
                        print(f"\n  📊 Final Test Report:")
                        print(f"    Summary: {report.get('summary', 'No summary')}")
                        print(f"    Passed: {len(report.get('passed_packages', []))}")
                        print(f"    Failed: {len(report.get('failed_packages', []))}")
                        
                        if report.get('failed_packages'):
                            print(f"    Failed Packages: {', '.join(report.get('failed_packages'))}")
                        
                        if report.get('all_passed'):
                            print(f"\n  ✅ Environment Verification Passed!")
                        else:
                            print(f"\n  ❌ Environment Verification Failed!")
                    else:
                        print(f"  Result: {test_result}")
                
                # Save Environment Node Results
                if 'save_env_result' in data:
                    save_result = data.get('save_env_result', {})
                    print("\n[5] SAVE ENVIRONMENT NODE RESULTS:")
                    if isinstance(save_result, dict):
                        if 'success' in save_result:
                            print(f"  Status: {'✅ Success' if save_result['success'] else '❌ Failed'}")
                        if 'stdout' in save_result and save_result['stdout']:
                            print(f"  Output: {save_result['stdout']}")
                        if 'export_file' in save_result and save_result['export_file']:
                            print(f"  Export File: {save_result['export_file']}")
                        if 'env_name' in save_result:
                            print(f"  Environment Name: {save_result['env_name']}")
                    else:
                        print(f"  Result: {save_result}")
                
                # Final Environment Name Summary
                if 'final_env_name' in data:
                    final_env = data.get('final_env_name', '')
                    print("\n" + "=" * 70)
                    print(f"🎯 FINAL CONDA ENVIRONMENT: {final_env}")
                    print("=" * 70)
                

            else:
                print("Error: Invalid output format from workflow.")
                print(result)
    
    except Exception as e:
        print(f"An error occurred: {e}")
    

if __name__ == "__main__":
    asyncio.run(main())
