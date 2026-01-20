import pandas as pd
from human_eval.data import stream_jsonl, write_jsonl
import random
import openai
import re

def split_task_plan(text):
    
    pattern = re.compile(r'\(/\s*(\d+)\s*\)(.*?)\(/\s*\1\s*\)', re.DOTALL)
    matches = pattern.findall(text)
    return [content.strip() for _, content in matches]

def main():
    # df = pd.read_csv("C:/Users/l84405517/Desktop/Mango/Mango/dataset/GPQA/dataset/gpqa_diamond.csv")
    # data = []
    # num = 0
    # for _, row in df.iterrows():
    #     prompt, answer_1, answer_2, answer_3, correct_answer = row['Question'], row['Incorrect Answer 1'], row['Incorrect Answer 2'], row['Incorrect Answer 3'], row['Correct Answer']
    #     choices = [answer_1, answer_2, answer_3, correct_answer]
    #     random.shuffle(choices)
    #     choices_prompt = "\nA. " + choices[0] + "\nB. " + choices[1] + "\nC. " + choices[2] + "\nD. " + choices[3]
    #     prompt += choices_prompt
    #     print(prompt)
        
    #     content = {"task_id": "test_" + str(num), 
    #             "prompt": prompt, 
    #             # "workflow": workflow, 
    #             "workflow": [], 
    #             "gt": correct_answer}
    #     data.append(content)
    #     num += 1
    # write_jsonl("./dataset/GPQA/test.jsonl", data)
    client = openai.OpenAI(api_key="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")
    # df = pd.read_csv("C:/Users/l84405517/Desktop/Mango/Mango/dataset/GPQA/dataset/gpqa_main.csv")
    df = pd.read_csv("C:/Users/l84405517/Desktop/Mango/Mango/dataset/GPQA/dataset/gpqa_diamond.csv")
    data = []
    num = 0
    for _, row in df.iterrows():
        prompt, answer_1, answer_2, answer_3, correct_answer = row['Question'], row['Incorrect Answer 1'], row['Incorrect Answer 2'], row['Incorrect Answer 3'], row['Correct Answer']
        choices = [answer_1, answer_2, answer_3, correct_answer]
        random.shuffle(choices)
        correct_answer = chr(ord("A") + choices.index(correct_answer))
        choices_prompt = "\nA. " + choices[0] + "\nB. " + choices[1] + "\nC. " + choices[2] + "\nD. " + choices[3]
        prompt += choices_prompt
        
        # workflow = client.chat.completions.create(
        #     # model="gpt-4o-mini",
        #     model="gpt-4o",
        #     messages=[
        #         {
        #             "role": "system", "content": "You are an assistant. Provide workflow steps for tasks without test and verify process. For each step, the content and role description must follow the following format:"
        #             "(/<serial number>)Content: <abstraction summary> | <specific content>.\nRole Description: <role> | <related description>.(/<serial number>)"
        #             "The ' | ' part must be included. The \"abstract content\" refers to the abstract action of the step. The \"specific content\" refers to specific content of the step."
        #         },
        #         {
        #             "role": "user",
        #             "content": f"For the task: {prompt}\nGenerate a clear and concise workflow consisting of 1 to 4 steps. Produce a 'minimal-sufficient' workflow that completes the task with the fewest steps. Each step should be actionable and ordered sequentially. For each step, give a role description that can perform this kind of things."
        #         }
        #     ],
        # )

        # workflow = split_task_plan(workflow.choices[0].message.content)
        
        content = {"task_id": "test_" + str(num), 
                "prompt": prompt, 
                # "workflow": workflow, 
                "workflow": [], 
                "gt": correct_answer}
        data.append(content)
        num += 1
    # write_jsonl("./dataset/GPQA/validate.jsonl", data)
    write_jsonl("./dataset/GPQA/test.jsonl", data)
    
main()