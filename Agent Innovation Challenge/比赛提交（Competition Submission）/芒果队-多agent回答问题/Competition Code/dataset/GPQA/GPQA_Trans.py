from human_eval.data import stream_jsonl, write_jsonl
import openai
import os
import re

# os.environ["http_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
# os.environ["https_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
# os.environ["no_proxy"] = "127.0.0.1,.huawei.com,localhost,local,.local,10.155.97.247,.myhuaweicloud.com"
os.environ['CURL_CA_BUNDLE'] = ''

def split_task_plan(text):
    
    pattern = re.compile(r'\(\s*(\d+)\s*\)(.*?)\(/\s*\1\s*\)', re.DOTALL)
    matches = pattern.findall(text)
    return [content.strip() for _, content in matches]

def grab_boxed(text: str):
    out = []
    i = 0
    while True:
        k = text.find(r'\boxed', i)
        if k == -1:
            break
        j = k + 6  # 跳过 '\boxed'
        while j < len(text) and text[j].isspace():
            j += 1
        if j >= len(text) or text[j] != '{':
            i = j
            continue
        # 进入花括号并做配对计数
        depth = 1
        j += 1
        start = j
        while j < len(text) and depth > 0:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
            j += 1
        if depth == 0:
            out.append(text[start:j-1])  # 不含最外层花括号
        i = j
    
    return out

client = openai.OpenAI(api_key="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")

data = list(stream_jsonl("./dataset/MBPP/mbpp_validate.jsonl"))
# data = list(stream_jsonl("./dataset/MBPP/mbpp_test.jsonl"))
new_data = []

for item in data:
    
    prompt = item['prompt']
    prompt = "\n\"\"\"" + prompt + "\"\"\"\n"
    test = item['test']
    entry_point = item["entry_point"]
    test = test.replace('def check()', f'def check({entry_point})')
    workflow = client.chat.completions.create(
        # model="gpt-4o-mini",
        model="gpt-4o",
        messages=[
            {
                "role": "system", "content": "You are an assistant. Provide workflow steps for tasks without test and verify process. For each step, the content and role description must follow the following format:"
                # "(<serial number>) Content: <abstraction summary> - <specific content>.\nRole Description: <role> - <related description>.\nChosen LLM: <LLM>.",
                "(<serial number>)Content: <abstraction summary> | <specific content>.\nRole Description: <role> | <related description>.(/<serial number>)"
            },
            {
                "role": "user",
                # "content": f"Give a workflow for the following task within 6 steps: \n{prompt}\n For each step, give a role description that can do this kind of thing and give a most suitable LLM(Among GPT, Gemini, Deepseek...)."
                "content": f"For the task: {prompt}\nGenerate a clear and concise workflow consisting of 1 to 4 steps. Produce a 'minimal-sufficient' workflow that completes the task with the fewest steps. Each step should be actionable and ordered sequentially. For each step, give a role description that can perform this kind of things."
            }
        ],
    )

    workflow = split_task_plan(workflow.choices[0].message.content)
    content = {"task_id": item['task_id'], 
               "prompt": prompt, 
               "test_imports": item['test_imports'], 
               "entry_point": entry_point, 
               "workflow": workflow, 
            #    "workflow": [], 
               "completion": item['code'], 
               "test": test}
    new_data.append(content)

write_jsonl("./dataset/MBPP/validate.jsonl", new_data)
# write_jsonl("./dataset/MBPP/test.jsonl", new_data)