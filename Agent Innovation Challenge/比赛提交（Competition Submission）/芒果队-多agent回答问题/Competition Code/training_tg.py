import networkx as nx
import time
from PolicyGradient import PolicyGradient, RL_Environment
# from PPO import PolicyGradient, RL_Environment
from human_eval.evaluation import evaluate_functional_correctness, evaluate_correctness
from human_eval.data import stream_jsonl, write_jsonl
from human_eval.execution import check_correctness
from utilities import parse_steps, get_response, self_consistency_ensemble, get_init_node, get_new_response
from datetime import datetime
from dotenv import load_dotenv
import textgrad as tg
# from textgrad.autograd import MultimodalLLMCall
# from textgrad.tasks import load_task
from textgrad.loss import MultiFieldTokenParsedEvaluation, MultiFieldEvaluation
# from GAIA_Scorer import question_scorer
import sympy as sp
from sympy.parsing.latex import parse_latex
import json
import re
import asyncio
from sentence_transformers import SentenceTransformer
from human_eval.execution import time_limit
model_embedding = SentenceTransformer("./hugging_face/all-MiniLM-L6-v2")
# GPT
# device = torch.device('cuda' if torch.cuda.is_available() else "cpu")

load_dotenv(override=True)
llm_api = tg.get_engine("gpt-4o-mini", is_async = True)
tg.set_backward_engine(llm_api, override=True)
tools = None
skip_k = 1
# browser_toolkit_schema = {'type': 'function', 'function': {'name': 'browse_url', 'description': 'A powerful toolkit which can simulate the browser interaction to\nsolve the task which needs multi-step actions.', 'strict': True, 'parameters': {'properties': {'task_prompt': {'type': 'string', 'description': 'The task prompt to solve.'}, 'start_url': {'type': 'string', 'description': 'The start URL to visit. It should be usually \"https://www.google.com/\", unless website specified.'}, 'round_limit': {'type': ['integer', 'null'], 'description': 'The round limit to solve the task.\n(default: :obj:`12`).'}}, 'required': ['task_prompt', 'start_url', 'round_limit'], 'type': 'object', 'additionalProperties': False}}}
# tools = [
#     browser_toolkit_schema,
#     ImageAnalysisToolkit().get_tools()[1].openai_tool_schema,
#     # DocumentProcessingToolkit().get_tools()[0].openai_tool_schema,
#     # SearchToolkit().get_tools()[2].openai_tool_schema,
#     # ArxivToolkit().get_tools()[0].openai_tool_schema,
# ]

# Train the RL agent to choose correct node in the graph
def Training_RL(f, G:nx.DiGraph, env:RL_Environment, RL_Agent:PolicyGradient, train_ids, train_workflows, train_prompts, train_vecs, tid_to_path):

    num_tasks = len(train_ids)
    for i in range(num_tasks):
        tid = train_ids[i]
        tvec = train_vecs[i] # 每个任务prompt的embedding向量
        task_workflow = train_workflows[i]

        # print(f"\n[TRAININGPG] Training episode = {episode+1} for task {i+1} / {num_tasks}", file=f, flush=True)
        gt_path = tid_to_path[tid]
        current_node = 0
        current_node_neighbours = []
        step_num = 0

        # One task process
        done = False
        while True:
            # print(f"\n[TRAININGPG] Training step = {env.step_num}", file=f, flush=True)
            if step_num < len(task_workflow):
                cur_task = task_workflow[step_num]
            else:
                cur_task = "Give the final answer based on the given information."
            
            # RL Process
            if step_num == 0:
                current_node = gt_path[1]
                current_node_neighbours = list(G.successors(current_node))
                step_num += 1
            else:
                observation = env.get_ob(current_node_neighbours, cur_task, tvec)
                action = RL_Agent.choose_action(observation)
                step_num += 1
                reward, done, _, current_node, current_node_neighbours = env.step(action, step_num, current_node_neighbours, gt_path)
                RL_Agent.store_transition(observation, action, reward)

            if done:
                # print(f"\n[TRAININGPG] Training step = {env.step_num}", file=f, flush=True)
                if len(RL_Agent.ep_as) > 0:
                    RL_Agent.learn()
                break

def Evaluation_RL(f, G:nx.DiGraph, env:RL_Environment, RL_Agent:PolicyGradient, valid_ids, valid_workflows, valid_prompts, valid_vecs, tid_to_path):
    
    start = time.time()
    num_correct = 0
    print(f"\n[EVALUATION] Evaluation", file=f, flush=True)
    num_tasks = len(valid_ids)
    for i in range(num_tasks):
        tid = valid_ids[i]
        tvec = valid_vecs[i] # 任务prompt的embedding向量
        task_workflow = valid_workflows[i]

        # print(f"\n[EVALUATION] Evaluation for task {i+1} / {num_tasks}", file=f, flush=True)
        gt_path = tid_to_path[tid]
        current_node = 0
        current_node_neighbours = []
        step_num = 0

        done = False
        while True:
            # print(f"\n[EVALUATION] Evaluation step = {env.step_num}", file=f, flush=True)
            if step_num < len(task_workflow):
                cur_task = task_workflow[step_num]
            else:
                cur_task = "Give the final answer based on the given information."
                
            # RL Process
            if step_num == 0:
                current_node = gt_path[1]
                current_node_neighbours = list(G.successors(current_node))
                step_num += 1
                reward = 1.0
            else:
                observation = env.get_ob(current_node_neighbours, cur_task, tvec)
                action = RL_Agent.choose_action(observation)
                step_num += 1
                reward, done, _, current_node, current_node_neighbours = env.step(action, step_num, current_node_neighbours, gt_path)

            if reward == 0.0: 
                print(f"Task {tid} Node {current_node} Step {step_num} incorrect.", file=f, flush=True)
                break

            if done:
                # print(f"\n[EVALUATION] Evaluation step = {env.step_num}", file=f, flush=True)
                num_correct += 1
                break
    
    score = num_correct / num_tasks
    return score, time.time() - start

async def Training_RL_TG(f, G:nx.DiGraph, env:RL_Environment, RL_Agent:PolicyGradient, episode, concurrency, max_step, valid_problems, 
               train_ids, train_gts, train_prompts, train_vecs, train_files, train_public_tests, tid_to_path, benchmark_selected=""):

    planner_model = G.nodes[0]['planner_model']
    planner_system_prompt = planner_model.system_prompt

    # plan_optimizer = tg.TextualGradientDescent(engine=llm_api, parameters=[planner_system_prompt], constraints=["Do not grow the system prompt too much"])
    # plan_optimizer = tg.TextualGradientDescent(engine=llm_api, parameters=[planner_system_prompt])
    num_tasks = len(train_prompts)
    plan_losses = []
    updated_nodes = []
    
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [Training_Task(f, G, env, planner_model, RL_Agent, episode, i, num_tasks, updated_nodes, plan_losses, semaphore, max_step, valid_problems, 
               train_ids, train_gts, train_prompts, train_vecs, train_files, train_public_tests, tid_to_path, benchmark_selected) for i in range(num_tasks)]
    await asyncio.gather(*tasks, return_exceptions=False)
    # await asyncio.gather(*tasks, return_exceptions=True)

    # plan_optimizer.zero_grad()
    # total_plan_loss = tg.sum(plan_losses)
    # total_plan_loss.backward()
    # await plan_optimizer.step()
    
    updated_nodes = list(set(updated_nodes))
    optimize_tasks = [executor_optimize(f, G, node_num, semaphore) for node_num in updated_nodes]
    await asyncio.gather(*optimize_tasks, return_exceptions=False)
    # await asyncio.gather(*optimize_tasks, return_exceptions=True)

async def executor_optimize(f, G:nx.DiGraph, node_num, semaphore):
    async with semaphore:
        print(f"Currently optimize node {node_num}", file=f, flush=True)
        executor_model:tg.BlackboxLLM = G.nodes[node_num]["executor_model"]
        updated_system_prompt = executor_model.system_prompt
        # executor_optimizer = tg.TextualGradientDescent(engine=llm_api, parameters=[updated_system_prompt], constraints=["Do not grow the system prompt too much"])
        executor_optimizer = tg.TextualGradientDescent(engine=llm_api, parameters=[updated_system_prompt])
        executor_optimizer.zero_grad()
        total_execute_loss = tg.sum(G.nodes[node_num]["execute_losses"])
        print("Loss: " + total_execute_loss.value, file=f, flush=True)
        total_execute_loss.backward()
        await executor_optimizer.step()
        print("NEW_SYSTEM_PROMPT:", file=f, flush=True)
        print(executor_model.system_prompt.value, file=f, flush=True)
        G.nodes[node_num]["execute_losses"] = []

async def Evaluation_RL_TG(f, G:nx.DiGraph, env:RL_Environment, RL_Agent:PolicyGradient, concurrency, max_step, valid_problems, 
                 valid_ids, valid_gts, valid_prompts, valid_vecs, valid_files, valid_public_tests, tid_to_path, benchmark_selected = ""):
    
    start = time.time()
    answers = []
    
    planner_model = G.nodes[0]['planner_model']
    num_tasks = len(valid_prompts)
    
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [Evaluation_Task(f, G, env, planner_model, RL_Agent, i, num_tasks, answers, semaphore, max_step, 
               valid_ids, valid_gts, valid_prompts, valid_vecs, valid_files, valid_public_tests, tid_to_path, benchmark_selected) for i in range(num_tasks)]
    await asyncio.gather(*tasks, return_exceptions=False)
    # await asyncio.gather(*tasks, return_exceptions=True)

    if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        score, _ = evaluate_correctness(answers, k = [1], problems=valid_problems, timeout=10.0, ignore_incomplete=True)
        score = score['pass@1']
    elif benchmark_selected == "math":
        score = cal_math_acc(answers)
    elif benchmark_selected == "drop":
        score = cal_drop_f1(answers)
    elif benchmark_selected == "gsm8k":
        score = cal_gsm8k_acc(answers)
    elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
        score = cal_gpqa_acc(answers)
        
    return score, time.time() - start

async def Evaluation_Test(f, test_dir, G:nx.DiGraph, env:RL_Environment, RL_Agent:PolicyGradient, concurrency, max_step, starting_nodes_to_vecs, test_problems, 
                    test_ids, test_gts, test_prompts, test_vecs, test_files, test_public_tests, benchmark_selected = ""):
    
    start = time.time()
    answers = []
    num_tasks = len(test_prompts)
    planner_model = G.nodes[0]['planner_model']

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [Test_Task(f, G, env, planner_model, RL_Agent, i, num_tasks, answers, semaphore, max_step, starting_nodes_to_vecs, test_problems, 
               test_ids, test_gts, test_prompts, test_vecs, test_files, test_public_tests, benchmark_selected) for i in range(num_tasks)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    # results = await asyncio.gather(*tasks, return_exceptions=True)
    
    if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        write_jsonl(f"{test_dir}/answer.jsonl", answers)
        score = evaluate_functional_correctness(f"{test_dir}/answer.jsonl", answers, k = [1], problems = test_problems, timeout=10.0, ignore_incomplete=True)['pass@1']
    elif benchmark_selected == "math":
        score = cal_math_acc(answers)
    elif benchmark_selected == "drop":
        score = cal_drop_f1(answers)
    elif benchmark_selected == "gsm8k":
        score = cal_gsm8k_acc(answers)
    elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
        score = cal_gpqa_acc(answers)
    # used for checking bug
    write_jsonl(f"{test_dir}/Test_Ans.jsonl", results)
    return score, time.time() - start

async def plan_loss_fn(task: tg.Variable, total_plan: tg.Variable) -> tg.Variable:
    role_descriptions = [
        "Total query prompt for the task",
        "Total plan for the task"
    ]
    
    evaluation_instruction = "Think about the task and its total plan. In the planner role, is the total plan correct and complete for solving this task?"
    eval_instruction = tg.Variable(evaluation_instruction, requires_grad=False, role_description="evaluation instruction for the task plan")
    # loss_fn = MultiFieldEvaluation(
    loss_fn = MultiFieldTokenParsedEvaluation(
        eval_instruction,
        role_descriptions=role_descriptions,
        engine=llm_api,
        parse_tags=["<PLAN_EVALUATION>", "</PLAN_EVALUATION>"]
    )

    inputs = [task, total_plan]
    return await loss_fn.async_forward(inputs)

async def execute_loss_fn(sub_task: tg.Variable, response: tg.Variable, total_task_answer: tg.Variable) -> tg.Variable:
    role_descriptions = [
        "Separated sub-task prompt",
        "Language model response for the separated sub-task",
        "Total task prompt and its answer"
    ]
    
    evaluation_instruction = "You are a smart language model that evaluates the response for the task. You do not solve task or propose new responses, only evaluate model response critically and give very concise feedback."
    eval_instruction = tg.Variable(evaluation_instruction, requires_grad=False, role_description="evaluation instruction for the task step")
    # loss_fn = MultiFieldEvaluation(
    loss_fn = MultiFieldTokenParsedEvaluation(
        eval_instruction,
        role_descriptions=role_descriptions,
        engine=llm_api,
        parse_tags=["<EXECUTE_EVALUATION>", "</EXECUTE_EVALUATION>"]
    )

    inputs = [sub_task, response, total_task_answer]
    return await loss_fn.async_forward(inputs)

# DROP evaluation
import string
from collections import Counter
def normalize_answer(s: str):
    """
    Normalize answers for evaluation.
    """

    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    return white_space_fix(remove_articles(remove_punc(s.lower())))

def cal_f1(pred, gt):
    prediction_tokens = normalize_answer(pred).split()
    ground_truth_tokens = normalize_answer(gt).split()
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def cal_drop_f1(answers):
    """
    Compute the F1 score between prediction and ground truth answers.
    """
    total_score = 0
    for pred, gt in answers:
        f1_scores = []
        for groud_truth in gt:
            f1_scores.append(cal_f1(pred, groud_truth))
        uni_score = max(f1_scores)
        total_score += uni_score
    total_score /= len(answers)
    return total_score

import re
def extract_number(text: str):
    matches = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?|\d+\.\d+", str(text))
    if matches:
        last_number = matches[-1].replace(",", "")
        try:
            return float(last_number)
        except ValueError:
            return None
    else:
        return None

def cal_gsm8k_acc(answers):
    # assert len(gts) == len(answers), "Number of answers and gts are different."
    correct_num = 0
    for answer, gt in answers:
        if abs(extract_number(answer) - extract_number(gt)) <= 1e-6:
            correct_num += 1
    return correct_num / len(answers)

def cal_math_acc(answers):
    # assert len(gts) == len(answers), "Number of answers and gts are different."
    correct_num = 0
    for answer, gt in answers:
        if len(gt) == 1:
            if is_latex_correct(answer, gt[0]):
                correct_num += 1
        else:
            if gt == ["-1", "2"] and ("-1" in answer and "2" in answer):
                correct_num += 1
            elif gt == ["\\frac{\\pi}{4}", "\\frac{5\\pi}{4}"] and ("\\frac{\\pi}{4}" in answer and "\\frac{5\\pi}{4}" in answer):
                correct_num += 1
    return correct_num / len(answers)

def cal_gpqa_acc(answers):
    correct_num = 0
    for answer, gt in answers:
        if answer == gt:
            correct_num += 1
    return correct_num / len(answers)

def is_latex_correct(ans: str, gt: str, tol: float = 1e-6) -> bool:
    try:
        # 尝试把 latex 解析成 Sympy 表达式
        ans_expr = parse_latex(ans)
        gt_expr = parse_latex(gt)

        # 先尝试符号化简比较
        if sp.simplify(ans_expr - gt_expr) == 0:
            return True

        # 如果是数值，尝试数值比较
        ans_val = sp.N(ans_expr)
        gt_val = sp.N(gt_expr)
        if abs(ans_val - gt_val) < tol:
            return True
        return False
    except Exception as e:
        # 如果解析失败，就 fallback 用字符串比较
        return ans.strip() == gt.strip()

def save_system_prompt(G:nx.DiGraph, PG_dir):
    # Save Executor prompt
    system_prompts = []
    for node in G:
        if node != 0:
            system_prompts.append({node: G.nodes[node]['updated_system_prompt'].value})
    write_jsonl(PG_dir + '/prompt.jsonl', system_prompts)
    
    # Save Planner prompt
    planner_model: tg.BlackboxLLM = G.nodes[0]['planner_model']
    with open(PG_dir + '/planner_system_prompt.txt', "w", encoding="utf-8") as f:
        f.write(planner_model.system_prompt.value)

def load_system_prompt(G:nx.DiGraph, PG_dir):
    # Load Executor prompt
    system_prompts = stream_jsonl(PG_dir + '/prompt.jsonl')
    for system_prompt in system_prompts:
        node, updated_system_prompt = next(iter(system_prompt.items()))
        node = int(node)
        # updated_system_prompt = tg.Variable(updated_system_prompt, requires_grad=True, role_description="structured system prompt to a somewhat capable language model that specifies the behavior and strategies for the QA task.")
        updated_system_prompt = tg.Variable(updated_system_prompt, requires_grad=True, role_description="structured system prompt to a language model that specifies the behavior and strategies for the QA task. Its content will be updated.")
        G.nodes[node]['updated_system_prompt'] = updated_system_prompt
        G.nodes[node]['executor_model'].system_prompt = updated_system_prompt
    
    # Load Planner prompt
    planner_model:tg.BlackboxLLM = G.nodes[0]['planner_model']
    with open(PG_dir + '/planner_system_prompt.txt', "r", encoding="utf-8") as f:
        planner_system_prompt = f.read()
    # planner_system_prompt = tg.Variable(planner_system_prompt, requires_grad=True, role_description="structured system prompt to a somewhat capable language model that specifies task plan for the QA task.")
    planner_system_prompt = tg.Variable(planner_system_prompt, requires_grad=True, role_description="structured system prompt to a somewhat capable language model that specifies the behavior and strategies for the QA task.")
    planner_model.system_prompt = planner_system_prompt
    
    # # Load Executor prompt
    # system_prompts = stream_jsonl(PG_dir + '/prompt.jsonl')
    # for system_prompt in system_prompts:
    #     node, updated_system_prompt = next(iter(system_prompt.items()))
    #     node = int(node)
    #     updated_system_prompt = tg.Variable(updated_system_prompt, requires_grad=True, role_description="structured system prompt to a somewhat capable language model that specifies the behavior and strategies for the QA task.")
    #     G.nodes[node]['updated_system_prompt'] = updated_system_prompt
    #     if node != 1:
    #         G.nodes[node]['executor_model'].system_prompt = tg.sum([G.nodes[node]["fixed_system_prompt"], updated_system_prompt])
    #     else:
    #         G.nodes[node]['executor_model'].system_prompt = updated_system_prompt
    
    # # Load Planner prompt
    # planner_model:tg.BlackboxLLM = G.nodes[0]['planner_model']
    # with open(PG_dir + '/planner_system_prompt.txt', "r", encoding="utf-8") as f:
    #     planner_system_prompt = f.read()
    # planner_system_prompt = tg.Variable(planner_system_prompt, requires_grad=True, role_description="structured system prompt to a somewhat capable language model that specifies task plan for the QA task.")
    # planner_model.system_prompt = planner_system_prompt
    
async def Training_Task(f, G:nx.DiGraph, env:RL_Environment, planner_model, 
               RL_Agent:PolicyGradient, episode, task_i, num_tasks, updated_nodes, plan_losses, semaphore, max_step, valid_problems, 
               train_ids, train_gts, train_prompts, train_vecs, train_files, train_public_tests, 
               tid_to_path, benchmark_selected=""):
    async with semaphore:
        tid = train_ids[task_i]
        task_prompt = train_prompts[task_i]
        file_path = train_files[task_i]
        gt_path = tid_to_path[tid]
        current_node = 0
        current_node_neighbours = []
        step_num = 0
        tvec = train_vecs[task_i] # 每个任务prompt的embedding向量
        public_tests = train_public_tests[task_i] if train_public_tests else None

        print(f"\n[TRAININGPG] Training episode = {episode+1} for task {task_i+1} / {num_tasks}", file=f, flush=True)
        print(f"\n[TRAININGPG] Training episode = {episode+1} for task {task_i+1} / {num_tasks}")
        print(f"\n[TRAININGPG] Training_RL_TG step = 0", file=f, flush=True)
        print(f"Problem: {task_prompt}", file=f, flush=True)

        history_info = []
        history_message = []
        plan_list = []
        rest_task = ""
        path = [0]
        # One task process
        history_message.append({"role": "user", "content": f"TOTAL_TASK: {task_prompt}"})
        planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
        planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
        cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
        print(cur_plan.value, file=f, flush=True)
        split_plan = parse_steps(cur_plan.value)
        
        done = False
        t = 0
        while t < len(split_plan):
            cur_task = split_plan[t]
            if step_num == 0:
                current_node = gt_path[1]
                current_node_neighbours, current_node_neighbours_step = env.get_neighbours(current_node, skip_k)
                skip_steps = 1
                step_num += 1
            else:
                observation = env.get_ob(current_node_neighbours, cur_task, tvec)
                action = RL_Agent.choose_action(observation)
                step_num += 1
                _, done, _, current_node, current_node_neighbours, current_node_neighbours_step, skip_steps = env.step_k(action, step_num, current_node_neighbours, current_node_neighbours_step, gt_path, skip_k)
                # RL_Agent.store_transition(observation, action, reward)
            
            path.append(current_node)
            
            if done:
                rest_task = "\n".join(split_plan[t:])
                break
            
            next_t = t + skip_steps
            cur_task = "\n".join(split_plan[t:next_t])
            t = next_t
            plan_list.append(cur_task)
            
            print(f"\n[TRAININGPG] Training_RL_TG step = {step_num}", file=f, flush=True)
            print(f"Current task: {cur_task}", file=f, flush=True)
            if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nPay attention to the order of edge cases and generate a clear and concise result."
            else:
                # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nFocus on solving the CURRENT_STEP and generate a clear and concise result."
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nFocus on solving the CURRENT_STEP and generate a concise result."
            executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
            executor_model = G.nodes[current_node]["executor_model"]

            retry_times = 1
            while retry_times <= 10:
                try:
                    res = await executor_model.async_forward(executor_prompt, tools=tools, temperature=0.7, file_path=file_path, memory=history_message)
                    response = res.value
                    # res_dict = json.loads(res.value)
                    # response = str(res_dict['response'])
                    break
                except Exception as e:
                    print(f"Retry times = {retry_times} / 10")
                    print(e)
                    print(f"Response: {res.value}", file=f, flush=True)
                retry_times += 1
            print(f"Response: {res.value}", file=f, flush=True)
            history_message.append({"role": "user", "content": cur_task})
            history_message.append({"role": "assistant", "content": response})
            res = tg.Variable(response, requires_grad=False, role_description="prompt for current sub-task")
            history_info.append(res)
            
            # if not res_dict.get("successful"):
            #     planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
            #     planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
            #     cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
            #     print("New plan:\n" + cur_plan.value, file=f, flush=True)
            #     split_plan = parse_steps(cur_plan.value)
        
        if not done:
            current_node = 1
            path.append(1)
        else:
            if rest_task != "":
                print("Rest plan:\n" + rest_task, file=f, flush=True)
                history_message.append({"role": "user", "content": rest_task})
                rest_answer = await get_response(history_message)
                history_message.append({"role": "assistant", "content": rest_answer})
                rest_task = "\n" + rest_task

        # Target node: get final answer
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Based on previous messages, generate an executable Python function to solve the TOTAL_TASK. Ensure the function name matches the one specified in the TOTAL_TASK. Without code block tags and main function."
            # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK.  Without prints, comments, descriptions, code block tags, test code or main function."
        elif benchmark_selected == "math":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK in Latex format. Do not include any thought process, title and unit. If the answer is only number(s), give the number(s) itself without any wrapper, such as: () and []. Simplify the fraction or sqrt number to its simplest form."
        elif benchmark_selected == "drop":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Just the required number, word or phrase without unit. If you can use number, do not use number word. Please simplify redundant zeros."
        elif benchmark_selected == "gsm8k":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Ensure that your final answer is a single numerical value without any units or additional text."
        elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Output the option letter based on TOTAL_TASK. Ensure only option letter."
            
        # print(f"\n[TRAININGPG] Training_RL_TG step = {step_num}", file=f, flush=True)
        executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
        executor_model = G.nodes[1]["executor_model"]
        
        response = await executor_model.async_forward(executor_prompt, temperature=0.7, memory=history_message)
        # if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", response.value, flags=re.IGNORECASE).group(1)
        print("Final Answer: \n" + response.value, file=f, flush=True)
        
        # # consistency ensemble
        # solutions = []
        # for _ in range(3):
        #     response = executor_model(executor_prompt, temperature=0.7, memory=history_message)
        #     solutions.append(response.value)
        # response.value = self_consistency_ensemble(problem=task_prompt, solutions=solutions)
        # print("Final Answer: \n" + response.value, file=f, flush=True)
        
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            response.value = "import math\n" + response.value
            
            # error = Exec_Code(f, response.value, public_tests)
            # if error != "":
            #     FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
            #     fixed_prompt = f"Problem: {task_prompt}Failed solution:\n{response.value}\nError: {error}"
            #     print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
            #     # code = await get_response([{"role": "user", "content": fixed_prompt}])
            #     code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #     # code = await get_response([{"role": "system", "content": IMPROVE_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
            #     # response = await Infer(f, G, env, planner_model, RL_Agent, task_i, fixed_prompt, file_path, tvec, num_tasks, max_step, starting_nodes_to_vecs, benchmark_selected)
            #     print("Fixed Answer: \n" + response.value, file=f, flush=True)
            
            correctness = check_correctness(valid_problems[tid], response.value, timeout=10.0)
            correct, report = correctness["passed"], correctness["result"]
        elif benchmark_selected == "math":
            correct = cal_math_acc([(response.value, train_gts[task_i])]) == 1.0
        elif benchmark_selected == "drop":
            correct = cal_drop_f1([(response.value, train_gts[task_i])]) == 1.0
        elif benchmark_selected == "gsm8k":
            correct = abs(extract_number(response.value) - extract_number(train_gts[task_i])) <= 1e-6
        elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            correct = response.value == train_gts[task_i]
        
        history_info.append(response)
        
        # if len(RL_Agent.ep_as) > 0:
        #     print('[TRAINING] ===> Policy Learning', file=f, flush=True)
        #     if correct:
        #         for b in range(len(RL_Agent.ep_rs)):
        #             RL_Agent.ep_rs[b] += 1.0
        #     RL_Agent.learn()
        
        if not correct:
            
            print(f'The generated result is not correct. TextGrad Optimization, Path: {path}', file=f, flush=True)
            path_len = len(path)
            task = tg.Variable(task_prompt, requires_grad=False, role_description="total task prompt")
            
            total_plan = "\n".join(plan_list)
            total_plan += rest_task
            # 更新汇点提示词
            for j in range(path_len - 1, 0, -1):
                node = path[j]
                if node != 1:
                    updated_nodes.append(node)
                response = history_info[j-1]
                
                role_description = G.nodes[node]['role_description']
                role_description = tg.Variable(role_description, requires_grad=False, role_description="description of the role this agent responses for")
                
                if j != path_len - 1:
                    sub_task = tg.Variable(plan_list[j-1], requires_grad=False, role_description="sub_task prompt")

                if j == path_len - 1:
                    if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
                        executor_loss = tg.Variable("The generated function is not correct. The error is:\n" + report, requires_grad=False, role_description="evaluation of the answer")
                    else:
                        executor_loss = tg.Variable("The generated result is not correct. The correct answer is:\n" + str(train_gts[task_i]), requires_grad=False, role_description="evaluation of the answer")
                else:
                    total_task_answer = task_prompt + str(train_gts[task_i])
                    total_task_answer = tg.Variable(total_task_answer, requires_grad=False, role_description="evaluation of the answer")
                    executor_loss = await execute_loss_fn(sub_task, response, total_task_answer)
                    G.nodes[node]["execute_losses"].append(executor_loss)

            print("total plan: \n" + total_plan, file=f, flush=True)
            # total_plan = tg.Variable(total_plan, requires_grad=False, role_description="sub_task prompt")
            # plan_loss = await plan_loss_fn(task, total_plan)
            # plan_losses.append(plan_loss)

async def Evaluation_Task(f, G:nx.DiGraph, env:RL_Environment, planner_model, 
               RL_Agent:PolicyGradient, task_i, num_tasks, answers, semaphore, max_step, 
               valid_ids, valid_gts, valid_prompts, valid_vecs, valid_files, valid_public_tests, 
               tid_to_path, benchmark_selected=""):
    async with semaphore:
        tid = valid_ids[task_i]
        task_prompt = valid_prompts[task_i]
        file_path = valid_files[task_i]
        gt_path = tid_to_path[tid]
        current_node = 0
        current_node_neighbours = []
        step_num = 0
        tvec = valid_vecs[task_i] # 每个任务prompt的embedding向量
        public_tests = valid_public_tests[task_i] if valid_public_tests else None

        print(f"\n[EVALUATION] for evaluation task {task_i+1} / {num_tasks}", file=f, flush=True)
        print(f"\n[EVALUATION] for evaluation task {task_i+1} / {num_tasks}")
        print(f"\n[EVALUATION] Evaluation step = 0", file=f, flush=True)
        print(f"Problem: {task_prompt}", file=f, flush=True)

        history_message = []
        rest_task = ""
        # One task process
        history_message.append({"role": "user", "content": f"TOTAL_TASK: {task_prompt}"})
        planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
        planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
        cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
        print(cur_plan.value, file=f, flush=True)
        split_plan = parse_steps(cur_plan.value)
        
        done = False
        t = 0
        while t < len(split_plan):
            cur_task = split_plan[t]
            if step_num == 0:
                current_node = gt_path[1]
                current_node_neighbours, current_node_neighbours_step = env.get_neighbours(current_node, skip_k)
                skip_steps = 1
                step_num += 1
            else:
                observation = env.get_ob(current_node_neighbours, cur_task, tvec)
                action = RL_Agent.choose_action(observation)
                step_num += 1
                _, done, _, current_node, current_node_neighbours, current_node_neighbours_step, skip_steps = env.step_k(action, step_num, current_node_neighbours, current_node_neighbours_step, [], skip_k)

            if done:
                rest_task = "\n".join(split_plan[t:])
                break
            
            next_t = t + skip_steps
            cur_task = "\n".join(split_plan[t:next_t])
            t = next_t
            
            print(f"\n[EVALUATION] Evaluation step = {step_num}", file=f, flush=True)
            print(f"Current task: {cur_task}", file=f, flush=True)
            if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nPay attention to the order of edge cases and generate a clear and concise result."
            else:
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nFocus on solving the CURRENT_STEP and generate a concise result."
            executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
            executor_model = G.nodes[current_node]["executor_model"]

            retry_times = 1
            while retry_times <= 10:
                try:
                    res = await executor_model.async_forward(executor_prompt, tools=tools, temperature=0.7, file_path=file_path, memory=history_message)
                    response = res.value
                    # res_dict = json.loads(res.value)
                    # response = str(res_dict['response'])
                    break
                except Exception as e:
                    print(f"Retry times = {retry_times} / 10")
                    print(e)
                    print(f"Response: {res.value}", file=f, flush=True)
                retry_times += 1
            print(f"Response: {res.value}", file=f, flush=True)
            history_message.append({"role": "user", "content": cur_task})
            history_message.append({"role": "assistant", "content": response})
            res = tg.Variable(response, requires_grad=False, role_description="prompt for current sub-task")
            
            # if not res_dict.get("successful"):
            #     planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
            #     planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
            #     cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
            #     print("New plan:\n" + cur_plan.value, file=f, flush=True)
            #     split_plan = parse_steps(cur_plan.value)
        
        if not done:
            current_node = 1
        else:
            if rest_task != "":
                print("Rest plan:\n" + rest_task, file=f, flush=True)
                history_message.append({"role": "user", "content": rest_task})
                rest_answer = await get_response(history_message)
                history_message.append({"role": "assistant", "content": rest_answer})

        # Target node: get final answer
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Based on previous messages, generate an executable Python function to solve the TOTAL_TASK. Ensure the function name matches the one specified in the TOTAL_TASK and the necessary libraries imported. Without code block tags and main function."
            # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK. Without print, comment, description, test code or main function."
        elif benchmark_selected == "math":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK in Latex format. Do not include any thought process, title and unit. If the answer is only number(s), give the number(s) itself without any wrapper, such as: () and []. Simplify the fraction or sqrt number to its simplest form."
        elif benchmark_selected == "drop":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Just the required number, word or phrase without unit. If you can use number, do not use number word. Please simplify redundant zeros."
        elif benchmark_selected == "gsm8k":
            # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer for the TOTAL_TASK. Do not include any thought process, title and unit. If the answer is only number(s), give the number(s) itself without any wrapper, such as: () and []. Simplify the fraction or sqrt number to its simplest form."
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Ensure that your final answer is a single numerical value without any units or additional text."
        elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Output the option letter based on TOTAL_TASK. Ensure only option letter."
        # print(f"\n[EVALUATION] Evaluation step = {step_num}", file=f, flush=True)
        executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
        executor_model = G.nodes[1]["executor_model"]
        
        response = await executor_model.async_forward(executor_prompt, temperature=0.7, memory=history_message)
        # if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", response.value, flags=re.IGNORECASE).group(1)
        print("Final Answer: \n" + response.value, file=f, flush=True)
        
        # # consistency ensemble
        # solutions = []
        # for _ in range(3):
        #     response = executor_model(executor_prompt, temperature=0.7, memory=history_message)
        #     solutions.append(response.value)
        # response.value = self_consistency_ensemble(problem=task_prompt, solutions=solutions)
        # print("Final Answer: \n" + response.value, file=f, flush=True)
        
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            response.value = "import math\n" + response.value
            
            # for _ in range(3):
            #     error = Exec_Code(f, response.value, public_tests)
            #     if error != "":
            #         FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
            #         fixed_prompt = f"Problem: {task_prompt}Failed solution:\n{response.value}\nError: {error}"
            #         print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
            #         code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #         # code = await get_response([{"role": "system", "content": "You are a code developer. For the Problem, you will fix the Failed Solution based on its Error and give the new solution."}, {"role": "user", "content": fixed_prompt}])
            #         response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
            #         # response.value = "import math\n" + await get_response([{"role": "system", "content": "You will give the final code for a coding question without any thought process and title. Do not include any test process and print content, just the required function."}, {"role": "user", "content": fixed_prompt}])
            #         print("Fixed Answer: \n" + response.value, file=f, flush=True)
            #     else:
            #         break
            # error = Exec_Code(f, response.value, public_tests)
            # if error != "":
            #     FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
            #     fixed_prompt = f"Problem: {task_prompt}Failed solution:\n{response.value}\nError: {error}"
            #     print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
            #     code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #     # code = await get_response([{"role": "system", "content": "You are a code developer. For the Problem, you will fix the Failed Solution based on its Error and give the new solution."}, {"role": "user", "content": fixed_prompt}])
            #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
            #     # response.value = "import math\n" + await get_response([{"role": "system", "content": "You will give the final code for a coding question without any thought process and title. Do not include any test process and print content, just the required function."}, {"role": "user", "content": fixed_prompt}])
            #     print("Fixed Answer: \n" + response.value, file=f, flush=True)
            answers.append({"task_id": tid, "completion": response.value})
        elif benchmark_selected == "gaia" or benchmark_selected == "math" or benchmark_selected == "drop" or benchmark_selected == "gsm8k" or benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            # if benchmark_selected == "gsm8k":
            #     response.value = await get_response([{"role": "system", "content": "Check the Given Answer by plugging it back into the Question. If correct, return the Given Answer; else resolve the Question and give a new answer. Ensure your answer is a single numerical value without any units or additional text."}, {"role": "user", "content": f"Question: {task_prompt}\nGiven Answer: {response.value}"}])
            answers.append((response.value, valid_gts[task_i]))
        
async def Test_Task(f, G:nx.DiGraph, env:RL_Environment, planner_model, 
               RL_Agent:PolicyGradient, task_i, num_tasks, answers, semaphore, max_step, starting_nodes_to_vecs, test_problems, 
               test_ids, test_gts, test_prompts, test_vecs, test_files, test_public_tests, benchmark_selected=""):
    async with semaphore:
        tid = test_ids[task_i]
        task_prompt = test_prompts[task_i]
        file_path = test_files[task_i]
        public_tests = test_public_tests[task_i] if test_public_tests else None
        tvec = test_vecs[task_i] # 每个任务prompt的embedding向量
        
        current_node = 0
        current_node_neighbours = []
        step_num = 0

        print(f"\n[TEST] for test task {task_i+1} / {num_tasks}", file=f, flush=True)
        print(f"\n[TEST] for test task {task_i+1} / {num_tasks}")
        print(f"\n[TEST] Test step = 0", file=f, flush=True)

        history_message = []
        rest_task = ""
        # One task process
        history_message.append({"role": "user", "content": f"TOTAL_TASK: {task_prompt}"})
        planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
        planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
        cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
        print(cur_plan.value, file=f, flush=True)
        split_plan = parse_steps(cur_plan.value)
        
        done = False
        t = 0
        while t < len(split_plan):
            cur_task = split_plan[t]
            if step_num == 0:
                # current_node = tid_to_init_node_dict[tid]
                first_step_vec = model_embedding.encode(cur_task)
                current_node = get_init_node(starting_nodes_to_vecs, first_step_vec)
                current_node_neighbours, current_node_neighbours_step = env.get_neighbours(current_node, skip_k)
                skip_steps = 1
                step_num += 1
            else:
                observation = env.get_ob(current_node_neighbours, cur_task, tvec)
                action = RL_Agent.choose_action(observation)
                step_num += 1
                _, done, _, current_node, current_node_neighbours, current_node_neighbours_step, skip_steps = env.step_k(action, step_num, current_node_neighbours, current_node_neighbours_step, [], skip_k)
            
            if done:
                rest_task = "\n".join(split_plan[t:])
                break
            
            next_t = t + skip_steps
            cur_task = "\n".join(split_plan[t:next_t])
            t = next_t
            
            print(f"\n[TEST] Test step = {step_num}", file=f, flush=True)
            print(f"Current task: {cur_task}", file=f, flush=True)
            if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nPay attention to the order of edge cases and generate a clear and concise result."
            else:
                executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nFocus on solving the CURRENT_STEP and generate a concise result."
            executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
            executor_model = G.nodes[current_node]["executor_model"]

            retry_times = 1
            while retry_times <= 10:
                try:
                    res = await executor_model.async_forward(executor_prompt, tools=tools, temperature=0.7, file_path=file_path, memory=history_message)
                    response = res.value
                    # res_dict = json.loads(res.value)
                    # response = str(res_dict['response'])
                    break
                except Exception as e:
                    print(f"Retry times = {retry_times} / 10")
                    print(e)
                    print(f"Response: {res.value}", file=f, flush=True)
                retry_times += 1
            print(f"Response: {res.value}", file=f, flush=True)
            history_message.append({"role": "user", "content": cur_task})
            history_message.append({"role": "assistant", "content": response})
            res = tg.Variable(response, requires_grad=False, role_description="prompt for current sub-task")
            
            # if not res_dict.get("successful"):
            #     planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
            #     planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
            #     cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
            #     print("New plan:\n" + cur_plan.value, file=f, flush=True)
            #     split_plan = parse_steps(cur_plan.value)
        
        if not done:
            current_node = 1
        else:
            if rest_task != "":
                print("Rest plan:\n" + rest_task, file=f, flush=True)
                history_message.append({"role": "user", "content": rest_task})
                rest_answer = await get_response(history_message)
                history_message.append({"role": "assistant", "content": rest_answer})

        # Target node: get final answer
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK. Without print, comment, description, code block tag, test code or main function."
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Based on previous messages, generate an executable Python function to solve the TOTAL_TASK. Ensure the function name matches the one specified in the TOTAL_TASK and the necessary libraries imported. Without code block tags and main function."
            # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK. Without print, comment, description, test or main function."
        elif benchmark_selected == "math":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK in Latex format. Do not include any thought process, title and unit. If the answer is only number(s), give the number(s) itself without any wrapper, such as: () and []. Simplify the fraction or sqrt number to its simplest form."
        elif benchmark_selected == "drop":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Just the required number, word or phrase without unit. If you can use number, do not use number word. Please simplify redundant zeros."
        elif benchmark_selected == "gsm8k":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Ensure that your final answer is a single numerical value without any units or additional text."
        elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Output the option letter based on TOTAL_TASK. Ensure only option letter."
        # print(f"\n[TEST] Test step = {step_num}", file=f, flush=True)
        executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
        executor_model = G.nodes[1]["executor_model"]
        
        response = await executor_model.async_forward(executor_prompt, temperature=0.7, memory=history_message)
        # if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", response.value, flags=re.IGNORECASE).group(1)
        print("Final Answer: \n" + response.value, file=f, flush=True)
        
        # # consistency ensemble
        # solutions = []
        # for _ in range(3):
        #     response = executor_model(executor_prompt, temperature=0.7, memory=history_message)
        #     solutions.append(response.value)
        # response.value = self_consistency_ensemble(problem=task_prompt, solutions=solutions)
        # print("Final Answer: \n" + response.value, file=f, flush=True)
        
        if benchmark_selected == "humaneval":
            response.value = "import math\n" + response.value
            # correctness = check_correctness(test_problems[tid], response.value, timeout=10.0)
            # correct, error = correctness["passed"], correctness["result"]
            
            correct = False
            for _ in range(3):
                error = Exec_Code(f, response.value, public_tests)
                if error != "":
                    # FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
                    fixed_prompt = f"Problem: {task_prompt}Wrong Answer:\n{response.value}\nError: {error}"
                    print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
                    # code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
                    # code = await get_response([{"role": "system", "content": "You are a software developer.I will give you a problem, wrong answer and its error. Please fix the wrong code."}, {"role": "user", "content": fixed_prompt}])
                    code = await get_response([{"role": "system", "content": "You are a software developer.I will give you a problem. Solve it and pay attention to the order of edge cases."}, {"role": "user", "content": task_prompt}])
                    response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
                    print("Fixed Answer: \n" + response.value, file=f, flush=True)
                else:
                    correct = True
                    break
            # error = Exec_Code(f, response.value, public_tests)
            # if error != "":
            #     FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
            #     # fixed_prompt = f"Problem: {task_prompt}Failed solution:\n{response.value}\nError: {error}\n{FIX_CODE_PROMPT}"
            #     fixed_prompt = f"Problem: {task_prompt}Failed solution:\n{response.value}\nError: {error}"
            #     print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
            #     # code = await get_response([{"role": "user", "content": fixed_prompt}])
            #     code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #     # code = await get_response([{"role": "system", "content": IMPROVE_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
            #     response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
            #     # response = await Infer(f, G, env, planner_model, RL_Agent, task_i, fixed_prompt, file_path, tvec, num_tasks, max_step, starting_nodes_to_vecs, token_usage, benchmark_selected)
            #     print("Fixed Answer: \n" + response.value, file=f, flush=True)
            answers.append({"task_id": tid, "completion": response.value, "pulic_test_correct": correct})
        elif benchmark_selected == "mbpp":
            response.value = "import math\n" + response.value
            # correctness = check_correctness(test_problems[tid], response.value, timeout=10.0)
            # correct, error = correctness["passed"], correctness["result"]
            
            correct = False
            for _ in range(3):
                error = Exec_Code(f, response.value, public_tests)
                if error != "":
                    FIX_CODE_PROMPT = "The solution failed to pass the tests. According to the problem and error, generate new code. Ensure the function name unchanged and the necessary libraries imported. Do not include test code and print content."
                    fixed_prompt = f"Problem: {task_prompt}Wrong Answer:\n{response.value}\nError: {error}"
                    print("Fixed_prompt: " + fixed_prompt, file=f, flush=True)
                    code = await get_response([{"role": "system", "content": FIX_CODE_PROMPT}, {"role": "user", "content": fixed_prompt}])
                    # code = await get_response([{"role": "system", "content": "You are a software developer.I will give you a problem, wrong answer and its error. Please fix the wrong code."}, {"role": "user", "content": fixed_prompt}])
                    # code = await get_response([{"role": "system", "content": "You are a software developer.I will give you a problem. Solve it and pay attention to the order of edge cases."}, {"role": "user", "content": task_prompt}])
                    response.value = "import math\n" + re.search(r"(?s)```python\s*\r?\n(.*?)```", code, flags=re.IGNORECASE).group(1)
                    print("Fixed Answer: \n" + response.value, file=f, flush=True)
                else:
                    correct = True
                    break
            answers.append({"task_id": tid, "completion": response.value, "pulic_test_correct": correct})
        elif benchmark_selected == "gaia" or benchmark_selected == "math" or benchmark_selected == "drop" or benchmark_selected == "gsm8k" or benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            if benchmark_selected == "gsm8k":
                # response.value = await get_response([{"role": "system", "content": "Check the Given Answer by plugging it back into the Question. If correct, return the Given Answer; else resolve the Question and give a new answer. Ensure your answer is a single numerical value without any units or additional text."}, {"role": "user", "content": f"Question: {task_prompt}\nGiven Answer: {response.value}"}])
                response.value = await get_response([{"role": "system", "content": "Substitute the answer into the original Question to verify. If correct, return the Given Answer; else solve the Question and provide a new answer. Ensure your answer is a single numerical value without any units or additional text."}, {"role": "user", "content": f"Question: {task_prompt}\nGiven Answer: {response.value}"}])
            if benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
                new_response = await get_new_response([{"role": "system", "content": "Check the answer into the original Question to verify. If correct, return the option letter; else solve the Question and provide a new option letter. Ensure the \"choice\" is only a letter."}, {"role": "user", "content": f"Question: {task_prompt}\nGiven Answer: {response.value}"}])
                new_response = json.loads(new_response)
                response.value = new_response["choice"]
            answers.append((response.value, test_gts[task_i]))
        if benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            return {"tid": tid, "process": new_response["thought_process"], "answer": response.value, "gt": test_gts[task_i]}
        return {"tid": tid, "answer": response.value, "gt": test_gts[task_i]}

async def Infer(f, G:nx.DiGraph, env:RL_Environment, planner_model, RL_Agent:PolicyGradient, 
                task_i, task_prompt, file_path, tvec, num_tasks, max_step, starting_nodes_to_vecs, benchmark_selected=""):
    current_node = 0
    current_node_neighbours = []
    step_num = 0
    print(f"\n[TEST] for test task {task_i+1} / {num_tasks}", file=f, flush=True)
    print(f"\n[TEST] for test task {task_i+1} / {num_tasks}")
    print(f"\n[TEST] Test step = 0", file=f, flush=True)

    history_message = []
    rest_task = ""
    # One task process
    history_message.append({"role": "user", "content": f"TOTAL_TASK: {task_prompt}"})
    planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
    planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
    cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
    print(cur_plan.value, file=f, flush=True)
    split_plan = parse_steps(cur_plan.value)
    
    done = False
    t = 0
    while t < len(split_plan):
        cur_task = split_plan[t]
        if step_num == 0:
            # current_node = tid_to_init_node_dict[tid]
            first_step_vec = model_embedding.encode(cur_task)
            current_node = get_init_node(starting_nodes_to_vecs, first_step_vec)
            current_node_neighbours, current_node_neighbours_step = env.get_neighbours(current_node, skip_k)
            skip_steps = 1
            step_num += 1
        else:
            observation = env.get_ob(current_node_neighbours, cur_task, tvec)
            action = RL_Agent.choose_action(observation)
            step_num += 1
            _, done, _, current_node, current_node_neighbours, current_node_neighbours_step, skip_steps = env.step_k(action, step_num, current_node_neighbours, current_node_neighbours_step, [], skip_k)
        
        if done:
            rest_task = "\n".join(split_plan[t:])
            break
        
        next_t = t + skip_steps
        cur_task = "\n".join(split_plan[t:next_t])
        t = next_t
        
        print(f"\n[TEST] Test step = {step_num}", file=f, flush=True)
        print(f"Current task: {cur_task}", file=f, flush=True)
        if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nPay attention to the order of edge cases and generate a clear and concise result."
        else:
            executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: {cur_task}\nFocus on solving the CURRENT_STEP and generate a concise result."
        executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
        executor_model = G.nodes[current_node]["executor_model"]

        retry_times = 1
        while retry_times <= 10:
            try:
                res = await executor_model.async_forward(executor_prompt, tools=tools, temperature=0.7, file_path=file_path, memory=history_message)
                response = res.value
                # res_dict = json.loads(res.value)
                # response = str(res_dict['response'])
                break
            except Exception as e:
                print(f"Retry times = {retry_times} / 10")
                print(e)
                print(f"Response: {res.value}", file=f, flush=True)
            retry_times += 1
        print(f"Response: {res.value}", file=f, flush=True)
        history_message.append({"role": "user", "content": cur_task})
        history_message.append({"role": "assistant", "content": response})
        res = tg.Variable(response, requires_grad=False, role_description="prompt for current sub-task")
        
        # if not res_dict.get("successful"):
        #     planner_prompt = f"For the TOTAL_TASK, generate a clear and concise workflow consisting of 1 to {max_step} steps. Each step must start with \"(<serial number>)\" and end with \"(/<serial number>)\". Do not provide final answer."
        #     planner_prompt = tg.Variable(planner_prompt, requires_grad=False, role_description="prompt for current sub-task")
        #     cur_plan = await planner_model.async_forward(planner_prompt, temperature=0.7, memory=history_message)
        #     print("New plan:\n" + cur_plan.value, file=f, flush=True)
        #     split_plan = parse_steps(cur_plan.value)
    
    if not done:
        current_node = 1
    else:
        if rest_task != "":
            print("Rest plan:\n" + rest_task, file=f, flush=True)
            history_message.append({"role": "user", "content": rest_task})
            rest_answer = await get_response(history_message)
            history_message.append({"role": "assistant", "content": rest_answer})

    # Target node: get final answer
    if benchmark_selected == "humaneval" or benchmark_selected == "mbpp":
        # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK. Without print, comment, description, code block tag, test code or main function."
        executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Based on previous messages, generate an executable Python function to solve the TOTAL_TASK. Ensure the function name matches the one specified in the TOTAL_TASK and the necessary libraries imported. Without code block tags and main function."
        # executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the code based on TOTAL_TASK and history message. Ensure the function name matches the one specified in the TOTAL_TASK. Without print, comment, description, test or main function."
    elif benchmark_selected == "math":
        executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK in Latex format. Do not include any thought process, title and unit. If the answer is only number(s), give the number(s) itself without any wrapper, such as: () and []. Simplify the fraction or sqrt number to its simplest form."
    elif benchmark_selected == "drop":
        executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Just the required number, word or phrase without unit. If you can use number, do not use number word. Please simplify redundant zeros."
    elif benchmark_selected == "gsm8k":
        executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Give the final answer based on TOTAL_TASK. Ensure that your final answer is a single numerical value without any units or additional text."
    elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
        executor_prompt = f"TOTAL_TASK: {task_prompt}\nCURRENT_STEP: Output the option letter based on TOTAL_TASK. Ensure only option letter."
    # print(f"\n[TEST] Test step = {step_num}", file=f, flush=True)
    executor_prompt = tg.Variable(executor_prompt, requires_grad=False, role_description="prompt for current sub-task")
    executor_model = G.nodes[1]["executor_model"]
    
    # 1 result
    response = await executor_model.async_forward(executor_prompt, temperature=0.7, memory=history_message)
    print("Retry Answer: \n" + response.value, file=f, flush=True)
    return response

def Exec_Code(f, solution, public_tests):
    # global_dict = {
    #     "math": __import__("math"),
    #     "hashlib": __import__("hashlib"),
    #     "re": __import__("re")
    # }
    error_information = ""
    for public_test in public_tests:
        code = solution + "\n" + public_test
        try:
            # with time_limit(timeout=60.0):
            exec(code, globals())
            # exec(code, global_dict)
        except AssertionError as e:
            error_information += f"The code cannot get the correct result for sample: {public_test}\n"
        except Exception as e:
            error_information += f"For the sample: {public_test} Error: {str(e)}\n"
    return error_information

IMPROVE_CODE_PROMPT = "The previous solution failed some test cases. Please analyze the problem carefully and provide an improved solution that addresses all edge cases and requirements."