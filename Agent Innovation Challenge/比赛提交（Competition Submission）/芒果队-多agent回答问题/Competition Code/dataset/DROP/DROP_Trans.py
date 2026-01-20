from human_eval.data import stream_jsonl, write_jsonl
import openai
import os
import re

# os.environ["http_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
# os.environ["https_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
# os.environ["no_proxy"] = "127.0.0.1,.huawei.com,localhost,local,.local,10.155.97.247,.myhuaweicloud.com"
# os.environ['CURL_CA_BUNDLE'] = ''

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
# client = openai.OpenAI(api_key="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")

# data = list(stream_jsonl("./dataset/DROP/drop_validate.jsonl"))
data = list(stream_jsonl("./dataset/DROP/drop_test.jsonl"))
new_data = []

for item in data:
    
    prompt = item['context']
    ref_text = item['ref_text']
    # workflow = client.chat.completions.create(
    #     # model="gpt-4o-mini",
    #     model="gpt-4o",
    #     messages=[
    #         {
    #             "role": "system", "content": "You are an assistant. Provide workflow steps for tasks without test and verify process. For each step, the content and role description must follow the following format:"
    #             "(<serial number>)Content: <abstraction summary> | <specific content>.\nRole Description: <role> | <related description>.(/<serial number>)"
    #             "The ' | ' part must be included. The \"abstract content\" refers to the abstract action of the step. The \"specific content\" refers to specific content of the step."
    #         },
    #         {
    #             "role": "user",
    #             "content": f"For the task: {prompt} {ref_text}\nGenerate a clear and concise workflow consisting of 1 to 3 steps. Produce a 'minimal-sufficient' workflow that completes the task with the fewest steps. Each step should be actionable and ordered sequentially. For each step, give a role description that can perform this kind of things."
    #         }
    #     ],
    # )

    # workflow = split_task_plan(workflow.choices[0].message.content)
    content = {"task_id": item['id'], 
               "prompt": prompt, 
            #    "workflow": workflow, 
               "workflow": [], 
               "completion": ref_text.split("|")}
    new_data.append(content)

# write_jsonl("./dataset/DROP/validate.jsonl", new_data)
write_jsonl("./dataset/DROP/test.jsonl", new_data)