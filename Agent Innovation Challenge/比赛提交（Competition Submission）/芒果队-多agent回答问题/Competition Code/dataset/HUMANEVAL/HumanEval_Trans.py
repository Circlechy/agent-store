def main():    
    from human_eval.data import stream_jsonl, write_jsonl
    import openai
    import os
    import re
    from human_eval.evaluation import evaluate_functional_correctness, check_correctness
    # os.environ["http_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
    # os.environ["https_proxy"] = "http://w00820712:%40Wz106477@10.155.96.165:8080/"
    # os.environ["no_proxy"] = "127.0.0.1,.huawei.com,localhost,local,.local,10.155.97.247,.myhuaweicloud.com"
    # os.environ['CURL_CA_BUNDLE'] = ''

    def split_task_plan(text):
        
        pattern = re.compile(r'\(/\s*(\d+)\s*\)(.*?)\(/\s*\1\s*\)', re.DOTALL)
        matches = pattern.findall(text)
        return [content.strip() for _, content in matches]

    def extract_between_split(s: str, start: str = "Content:", end: str = "Role Description:") -> str:
        try:
            middle = s.split(start, 1)[1].split(end, 1)[0]
            return middle.strip().strip('|').strip()
        except IndexError:
            return ""
    # client = openai.OpenAI(api_key="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")
    client = openai.OpenAI(api_key="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")
    data = list(stream_jsonl("./dataset/HumanEval/humaneval_validate.jsonl"))
    # data = list(stream_jsonl("./dataset/HumanEval/humaneval_test.jsonl"))
    new_data = []

    for item in data:
        prompt = item['prompt']
        title = prompt.split(":\n")[0] + ":\n"
        gt = title + item['canonical_solution']
        entry_point = item["entry_point"]
        
        num = 1
        correct = False
        while num <= 2:
            workflow = client.chat.completions.create(
                # model="gpt-4o-mini",
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", "content": "You are an assistant. Provide workflow steps for tasks without test and verify process. For each step, the content and role description must follow the following format:"
                        "(/<serial number>)Content: <abstract content> | <specific content>.\nRole Description: <role> | <related description>.(/<serial number>)"
                        "The ' | ' part must be included. The \"abstract content\" refers to the abstract action of the step. The \"specific content\" refers to specific content of the step."
                    },
                    {
                        "role": "user",
                        "content": f"For the task: {prompt}\nBased on the correct answer: {gt}\nGenerate a clear and concise workflow consisting of 1 to 3 steps. Produce a 'minimal-sufficient' workflow that completes the task with the fewest steps. Each step should be actionable and ordered sequentially."
                    }
                ],
                # response_format={
                #     "type": "json_schema",
                #     "json_schema": json_schema,
                # }
            )
            workflow = split_task_plan(workflow.choices[0].message.content)
            workflow_list = [extract_between_split(w) for w in workflow]
            code = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", "content": "You are a coder. Please provide the executable code for the given workflow, without any thought process and title. Do not include any test process and print content, just the required function. Do not include ```python```."
                    },
                    {
                        "role": "user", "content": f"Solve the task:\n{prompt}\nWith the workflow:\n" + "".join(workflow_list)
                    }
                ],
            )
            
            if check_correctness(item, code.choices[0].message.content, 3.0)["passed"]:
                correct = True
                break
            num += 1
        
        content = {"task_id": item['task_id'], 
                "prompt": prompt, 
                "entry_point": entry_point, 
                "workflow": workflow, 
                # "workflow": [], 
                "completion": gt, 
                "test": item['test'],
                "correct": correct}
        new_data.append(content)

    write_jsonl("./dataset/HumanEval/validate.jsonl", new_data)
    # write_jsonl("./dataset/HumanEval/test.jsonl", new_data)

if __name__ == "__main__":
    main()