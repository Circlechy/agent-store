import os
import io
import asyncio
import base64
from PIL import Image
from openjiuwen.core.component.start_comp import Start
from openjiuwen.core.component.end_comp import End
from openjiuwen.core.component.llm_comp import LLMComponent, LLMCompConfig
from openjiuwen.core.component.common.configs.model_config import ModelConfig
from openjiuwen.core.runner.runner import Runner
from openjiuwen.core.workflow.workflow_config import WorkflowConfig, WorkflowMetadata, WorkflowInputsSchema
from openjiuwen.core.workflow.base import Workflow
from openjiuwen.core.utils.llm.base import BaseModelInfo
from openjiuwen.agent.workflow_agent.workflow_agent import WorkflowAgent
from openjiuwen.agent.config.workflow_config import WorkflowAgentConfig
from openjiuwen.agent.common.schema import WorkflowSchema

from openjiuwen.core.component.llm_comp import LLMExecutable
from openjiuwen_patch import patched_build_user_prompt_content, patched_build_system_prompt
LLMExecutable._build_user_prompt_content = patched_build_user_prompt_content
LLMExecutable._build_system_prompt = patched_build_system_prompt

# print("Successfully patched LLMExecutable for nested interpolation.")

NODE_IP = "10.168.0.20"
os.environ.setdefault('API_BASE', f'http://{NODE_IP}:8000/v1')
os.environ.setdefault('API_KEY', 'EMPTY')
os.environ.setdefault('MODEL_PROVIDER', 'openai')
os.environ.setdefault('MODEL_NAME', 'Qwen/Qwen3-VL-4B-Instruct')

def pil_to_base64(image_path):
    with Image.open(image_path) as img:
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
def build_workflow():
    workflow_config = WorkflowConfig(
        metadata=WorkflowMetadata(
            id='image_query_workflow',
            name='image_query',
            version='1.0',
            description="根据用户输入的文字和图片回答问题"
        ),
        workflow_inputs_schema=WorkflowInputsSchema(
            type='object',
            properties={
                "query": {"type": "string"},
                "image_url": {"type": "string"}
            },
            required=['query', 'image_url']
        )
    )
    flow = Workflow(workflow_config=workflow_config)
    return flow

def build_components(llm_chat_template):
    start = Start({"inputs": [
        {"id": "query", "type": "string", "required": "true"},
        {"id": "image_url", "type": "string", "required": "true"}
    ]})

    end = End({"responseTemplate": "工作流输出: {{output}}"})

    model_config = ModelConfig(
        model_provider=os.getenv('MODEL_PROVIDER'),
        model_info=BaseModelInfo(
            api_key=os.getenv('API_KEY'),
            api_base=os.getenv('API_BASE'),
            model=os.getenv('MODEL_NAME')
        )
    )
    llm_config = LLMCompConfig(
        model=model_config,
        template_content=llm_chat_template,
        response_format={"type": "text"},
        output_config={"output": {"type": "string", "required": True}}
    )
    llm = LLMComponent(llm_config) 

    return start, end, llm



async def generate_response_with_openjiuwen_llm(chat_template, query, image_url):
    flow = build_workflow()
    start, end, llm = build_components(chat_template)

    # register components and link them
    flow.set_start_comp("start", start, inputs_schema={"query": "${query}", "image_url": "${image_url}"})
    flow.add_workflow_comp("llm", llm, inputs_schema={"query": "${start.query}", "image_url": "${start.image_url}"})
    flow.set_end_comp("end", end, inputs_schema={"output": "${llm.output}"})
    flow.add_connection("start", "llm")
    flow.add_connection("llm", "end")

    # create the agent
    schema = WorkflowSchema(
        id=flow.config().metadata.id,
        name=flow.config().metadata.name,
        version=flow.config().metadata.version,
        description=flow.config().metadata.description,
        inputs=flow.config().workflow_inputs_schema.properties
    )
    agent_config = WorkflowAgentConfig(
        id="image_query_agent",
        version="0.1.0",
        description="Image query agent",
        workflows=[schema]
    )
    workflow_agent = WorkflowAgent(agent_config)
    workflow_agent.bind_workflows([flow])


    try:
        invoke_result = await Runner.run_agent(
            workflow_agent,
            {
                "query": query,
                "image_url": image_url
            }
        )
        
        # Output handling
        return invoke_result.get("output").result.get('responseContent')
        # print(f"Output: {output_result.get('responseContent')}")
    except Exception as e:
        return f"An error occurred during inference: {e}"

def main():
    image_path = "service/search/test_image.jpg"
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return
    base64_image = pil_to_base64(image_path)
    image_data_url = f"data:image/jpeg;base64,{base64_image}"
    query = "请描述图片内容"
    chat_template = [
        {
            "role": "system", 
            "content": "你是一个AI助手，根据用户输入的图片和文字回答问题"
        },
        {
            "role": "user", 
            "content": [
                {"type": "text", "text": "{{query}}"},
                {"type": "image_url", "image_url": {"url": "{{image_url}}"}}
            ]
        },
    ]

    result = asyncio.run(generate_response_with_openjiuwen_llm(chat_template, query, image_data_url))
    print(result)
    # image_data_url = "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"

if __name__ == "__main__":
    main()