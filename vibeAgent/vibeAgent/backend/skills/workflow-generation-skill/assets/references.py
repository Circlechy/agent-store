
# 参考示例代码（来自 jiuwen/examples/workflow_agent/build_workflow_agent.ipynb）

references_file_path_dict = {
    "generate_config_file": ["app/agents/prompts/references/config_file_reference.py"],  
    "generate_component": ["app/agents/prompts/references/generate_component_reference.py"],
    "generate_workflow_builder": [
        "app/agents/prompts/references/config_file_reference.py",
        "app/agents/prompts/references/components.py",
        "app/agents/prompts/references/generate_workflow_builder_reference.py",
    ],
    "generate_main_file": ["app/agents/prompts/references/generate_main_file_reference.py"],
}