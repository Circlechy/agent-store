import pandas as pd
from human_eval.data import stream_jsonl, write_jsonl
import random
import openai
import re
from pathlib import Path
def split_task_plan(text):
    
    pattern = re.compile(r'\(/\s*(\d+)\s*\)(.*?)\(/\s*\1\s*\)', re.DOTALL)
    matches = pattern.findall(text)
    return [content.strip() for _, content in matches]

def main():

    client = openai.OpenAI(api_key="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")

    # folder = Path("dataset/MMLU/data/dev")
    folder = Path("dataset/MMLU/data/val")
    # folder = Path("dataset/MMLU/data/test")
    files = folder.rglob("*.csv")
    dfs = []
    for f in files:
        df = pd.read_csv(f, encoding="utf-8", header=None)   # 根据需要调整 encoding
        n = 0
        for _, row in df.iterrows():
            if n < 5:
                dfs.append(row)
            n += 1
    
    data = []
    num = 0
    for row in dfs:
        prompt, A, B, C, D, correct_answer = row[0], str(row[1]), str(row[2]), str(row[3]), str(row[4]), row[5]
        choices_prompt = "\nA. " + A + "\nB. " + B + "\nC. " + C + "\nD. " + D
        prompt += choices_prompt
        
        workflow = client.chat.completions.create(
            # model="gpt-4o-mini",
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an assistant. Provide workflow steps for tasks without test and verify process. For each step, the content and role description must follow the following format:"
                    "(/<serial number>)Content: <abstraction summary> | <specific content>.\nRole Description: <role> | <related description>.(/<serial number>)"
                    "The ' | ' part must be included. The \"abstract content\" refers to the abstract action of the step. The \"specific content\" refers to specific content of the step."
                },
                {
                    "role": "user",
                    "content": f"For the task: {prompt}\nGenerate a clear and concise workflow consisting of 1 to 4 steps. Produce a 'minimal-sufficient' workflow that completes the task with the fewest steps. Each step should be actionable and ordered sequentially. For each step, give a role description that can perform this kind of things."
                }
            ],
        )

        workflow = split_task_plan(workflow.choices[0].message.content)
        content = {
            # "task_id": "train_" + str(num), 
            "task_id": "valid_" + str(num), 
            # "task_id": "test_" + str(num), 
            "prompt": prompt, 
            "workflow": workflow, 
            # "workflow": [], 
            "gt": correct_answer
        }
        data.append(content)
        num += 1
    
    # write_jsonl("./dataset/MMLU/train.jsonl", data)
    write_jsonl("./dataset/MMLU/validate.jsonl", data)
    # write_jsonl("./dataset/MMLU/test.jsonl", data)
    
main()