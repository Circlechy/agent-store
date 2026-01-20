import os
# os.environ["http_proxy"] = "http://l84405517:19650322Lzn@@10.155.96.165:8080/"
# os.environ["https_proxy"] = "http://l84405517:19650322Lzn@@10.155.96.165:8080/"
# os.environ["no_proxy"] = "127.0.0.1,.huawei.com,localhost,local,.local,10.155.97.247,.myhuaweicloud.com"
# os.environ["CUDA_VISIBLE_DEVICES"] = "2"
# llm_emb_model_name = "all-MiniLM-L6-v2"
# embed_model = SentenceTransformer(llm_emb_model_name)
# embed_model = SentenceTransformer(llm_emb_model_name, cache_folder="embedding_model")

def main():
    
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="sentence-transformers/all-MiniLM-L6-v2",
        local_dir="./hugging_face/all-MiniLM-L6-v2",
        local_dir_use_symlinks=False,
        # local_files_only=False,
        resume_download=True,
        force_download=False,
    )

    os.environ["OPENAI_API_KEY"] = "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"
    os.environ["OPENAI_API_BASE"] = "https://api.openai.com/v1"
    # os.environ["OPENAI_API_KEY"] = "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"
    # os.environ["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    import sys
    root_dir = "C:\\Users\\l84405517\\Desktop\\Mango"
    sys.path.append(root_dir)
    import warnings
    warnings.filterwarnings('ignore')
    # from langchain_huggingface import HuggingFaceEmbeddings
    from human_eval.data import stream_jsonl, read_problems
    
    import argparse
    from utilities import build_graph, build_init_node_dict, get_dataset_info
    from training_tg import Training_RL, Evaluation_RL, Training_RL_TG, Evaluation_RL_TG, Evaluation_Test, save_system_prompt, load_system_prompt
    from PolicyGradient import PolicyGradient, RL_Environment
    from sentence_transformers import SentenceTransformer
    import time
    from datetime import datetime
    from token_usage import TokenUsageTracker, TOKEN_USAGE

    import asyncio

    embed_model = SentenceTransformer("./hugging_face/all-MiniLM-L6-v2")
    
    def parse_args():
        parser = argparse.ArgumentParser(description="MANGO Optimizer")
        parser.add_argument("--benchmark_selected", type=str, default="mbpp", help="the benchmark selected")
        parser.add_argument("--data_train_percent", type=float, default=0.8, help="dataset partition percent")
        parser.add_argument("--threshold", type=float, default=0.7, help="the benchmark selected")
        parser.add_argument("--concurrency", type=int, default=40, help="async concurrency")
        parser.add_argument("--num_rl_episodes", type=float, default=100, help="rl episode")
        parser.add_argument("--num_tg_episodes", type=float, default=5, help="tg episode")
        parser.add_argument("--result_dir", type=str, default="ckpt/", help="tg episode")
        return parser.parse_args()
    
    # train_benchmark_selected = ""
    # test_benchmark_selected = ""
    
    # benchmark_selected = "math"
    benchmark_selected = "mbpp"
    # benchmark_selected = "humaneval"
    # benchmark_selected = "drop"
    # benchmark_selected = "gsm8k"
    # benchmark_selected = "gpqa"
    # benchmark_selected = "mmlu"
    
    # data_filename = "./dataset/MATH/validate2.jsonl"
    # test_data_filename = "./dataset/MATH/test.jsonl"
    # data_filename = "MATH_valid.jsonl"
    # test_data_filename = "MATH_test.jsonl"
    
    data_filename = f"./dataset/{benchmark_selected.upper()}/validate.jsonl"
    test_data_filename = f"./dataset/{benchmark_selected.upper()}/test.jsonl"
    # if benchmark_selected == "humaneval": 
    #     data_filename = f"./dataset/MBPP/validate.jsonl"
    # data_filename = f"./dataset/{benchmark_selected.upper()}/validate_try.jsonl"
    # test_data_filename = f"./dataset/{benchmark_selected.upper()}/test_try.jsonl"
    ##################################################
    # Import data                                    #
    ##################################################

    data = list(stream_jsonl(data_filename))
    test_data = list(stream_jsonl(test_data_filename))
    # np.random.shuffle(data)

    num_data = len(data)
    
    data_train_percent = 0.8
    # if benchmark_selected == "mmlu":
    #     data_train_percent = 0.5
    # elif benchmark_selected == "mbpp" and benchmark_selected == "humaneval":
    #     data_train_percent = 0.75
    num_train_tasks = round(data_train_percent*num_data)
    ##################################################
    # Preprocessing data                             #
    ##################################################
    train_public_tests, valid_public_tests, test_public_tests = None, None, None
    if benchmark_selected == "math":
        task_ids = [item['task_id'] for item in data]
        task_prompts = [item['prompt'] for item in data]
        # if benchmark_selected + "_train" in cache:
        #     task_prompts_vecs = cache[benchmark_selected + "_train"]
        # else:
        #     task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        #     cache[benchmark_selected + "_train"] = task_prompts_vecs
        task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        # task_types = [item['type'] for item in data]
        task_workflows = [item['workflow'] for item in data]
        task_solutions = [item['solution'] for item in data]
        task_gts = [item['gt'] for item in data]

        # train use
        train_tasks_endpoint = num_train_tasks
        # train_data = data[:train_tasks_endpoint]
        train_ids = task_ids[:train_tasks_endpoint]
        train_prompts = task_prompts[:train_tasks_endpoint]
        train_prompts_vecs = task_prompts_vecs[:train_tasks_endpoint]
        train_workflows = task_workflows[:train_tasks_endpoint]
        # train_prompts_vecs = [embed_model.embed_query(question) for question in train_prompts]
        train_gts = task_gts[:train_tasks_endpoint]
        train_files = [""]*len(train_ids)

        # validation use
        # valid_data = data[train_tasks_endpoint:]
        valid_ids = task_ids[train_tasks_endpoint:]
        valid_prompts = task_prompts[train_tasks_endpoint:]
        valid_prompts_vecs = task_prompts_vecs[train_tasks_endpoint:]
        valid_workflows = task_workflows[train_tasks_endpoint:]
        # train_prompts_vecs = [embed_model.embed_query(question) for question in train_prompts]
        valid_gts = task_gts[train_tasks_endpoint:]
        valid_files = [""]*len(valid_ids)

        test_ids = [item['task_id'] for item in test_data]
        test_prompts = [item['prompt'] for item in test_data]
        test_prompts_vecs = [embed_model.encode(question) for question in test_prompts]
        # test_types = [item['type'] for item in test_data]
        test_solutions = [item['solution'] for item in test_data]
        test_gts = [item['gt'] for item in test_data]
        test_files = [""]*len(test_ids)

    elif benchmark_selected == "mbpp" or benchmark_selected == "humaneval":
        task_ids = [item['task_id'] for item in data]
        task_entry_points = [item['entry_point'] for item in data]
        task_prompts = [item['prompt'] for item in data]
        task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        task_workflows = [item['workflow'] for item in data]
        task_gts = [item['completion'] for item in data]
        task_public_tests = [item['public_test'] for item in data]

        # train use
        train_tasks_endpoint = num_train_tasks
        # train_data = data[:train_tasks_endpoint]
        train_ids = task_ids[:train_tasks_endpoint]
        train_entry_points = task_entry_points[:train_tasks_endpoint]
        train_prompts = task_prompts[:train_tasks_endpoint]
        train_prompts_vecs = task_prompts_vecs[:train_tasks_endpoint]
        train_workflows = task_workflows[:train_tasks_endpoint]
        # train_prompts_vecs = [embed_model.embed_query(question) for question in train_prompts]
        train_gts = task_gts[:train_tasks_endpoint]
        train_public_tests = task_public_tests[:train_tasks_endpoint]
        train_files = [""]*len(train_ids)

        # validation use
        # valid_data = data[train_tasks_endpoint:]
        valid_ids = task_ids[train_tasks_endpoint:]
        valid_entry_points = task_entry_points[train_tasks_endpoint:]
        valid_prompts = task_prompts[train_tasks_endpoint:]
        valid_prompts_vecs = task_prompts_vecs[train_tasks_endpoint:]
        valid_workflows = task_workflows[train_tasks_endpoint:]
        # train_prompts_vecs = [embed_model.embed_query(question) for question in train_prompts]
        valid_gts = task_gts[train_tasks_endpoint:]
        valid_public_tests = task_public_tests[train_tasks_endpoint:]
        valid_files = [""]*len(valid_ids)

        test_ids = [item['task_id'] for item in test_data]
        test_entry_points = [item['entry_point'] for item in test_data]
        test_prompts = [item['prompt'] for item in test_data]
        test_prompts_vecs = [embed_model.encode(question) for question in test_prompts]
        test_gts = [item['completion'] for item in test_data]
        test_public_tests = [item['public_test'] for item in test_data]
        test_files = [""]*len(test_ids)
    elif benchmark_selected == "drop":
        task_ids = [item['task_id'] for item in data]
        task_prompts = [item['prompt'] for item in data]
        task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        task_workflows = [item['workflow'] for item in data]
        task_gts = [item['completion'] for item in data]
        
        # train use
        train_tasks_endpoint = num_train_tasks
        train_ids = task_ids[:train_tasks_endpoint]
        train_prompts = task_prompts[:train_tasks_endpoint]
        train_prompts_vecs = task_prompts_vecs[:train_tasks_endpoint]
        train_workflows = task_workflows[:train_tasks_endpoint]
        train_gts = task_gts[:train_tasks_endpoint]
        train_files = [""]*len(train_ids)

        # validation use
        valid_ids = task_ids[train_tasks_endpoint:]
        valid_prompts = task_prompts[train_tasks_endpoint:]
        valid_prompts_vecs = task_prompts_vecs[train_tasks_endpoint:]
        valid_workflows = task_workflows[train_tasks_endpoint:]
        valid_gts = task_gts[train_tasks_endpoint:]
        valid_files = [""]*len(valid_ids)

        test_ids = [item['task_id'] for item in test_data]
        test_prompts = [item['prompt'] for item in test_data]
        test_prompts_vecs = [embed_model.encode(question) for question in test_prompts]
        test_gts = [item['completion'] for item in test_data]
        test_files = [""]*len(test_ids)
    elif benchmark_selected == "gsm8k":
        task_ids = [item['task_id'] for item in data]
        task_prompts = [item['prompt'] for item in data]
        task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        task_workflows = [item['workflow'] for item in data]
        task_gts = [item['gt'] for item in data]
        
        # train use
        train_tasks_endpoint = num_train_tasks
        train_ids = task_ids[:train_tasks_endpoint]
        train_prompts = task_prompts[:train_tasks_endpoint]
        train_prompts_vecs = task_prompts_vecs[:train_tasks_endpoint]
        train_workflows = task_workflows[:train_tasks_endpoint]
        train_gts = task_gts[:train_tasks_endpoint]
        train_files = [""]*len(train_ids)

        # validation use
        valid_ids = task_ids[train_tasks_endpoint:]
        valid_prompts = task_prompts[train_tasks_endpoint:]
        valid_prompts_vecs = task_prompts_vecs[train_tasks_endpoint:]
        valid_workflows = task_workflows[train_tasks_endpoint:]
        valid_gts = task_gts[train_tasks_endpoint:]
        valid_files = [""]*len(valid_ids)

        # test use
        test_ids = [item['task_id'] for item in test_data]
        test_prompts = [item['prompt'] for item in test_data]
        test_prompts_vecs = [embed_model.encode(question) for question in test_prompts]
        test_gts = [item['gt'] for item in test_data]
        test_files = [""]*len(test_ids)
    elif benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
        task_ids = [item['task_id'] for item in data]
        task_prompts = [item['prompt'] for item in data]
        task_prompts_vecs = [embed_model.encode(question) for question in task_prompts]
        task_workflows = [item['workflow'] for item in data]
        task_gts = [item['gt'] for item in data]
        
        # train use
        train_tasks_endpoint = num_train_tasks
        train_ids = task_ids[:train_tasks_endpoint]
        train_prompts = task_prompts[:train_tasks_endpoint]
        train_prompts_vecs = task_prompts_vecs[:train_tasks_endpoint]
        train_workflows = task_workflows[:train_tasks_endpoint]
        train_gts = task_gts[:train_tasks_endpoint]
        train_files = [""]*len(train_ids)

        # validation use
        valid_ids = task_ids[train_tasks_endpoint:]
        valid_prompts = task_prompts[train_tasks_endpoint:]
        valid_prompts_vecs = task_prompts_vecs[train_tasks_endpoint:]
        valid_workflows = task_workflows[train_tasks_endpoint:]
        valid_gts = task_gts[train_tasks_endpoint:]
        valid_files = [""]*len(valid_ids)

        # test use
        test_ids = [item['task_id'] for item in test_data]
        test_prompts = [item['prompt'] for item in test_data]
        test_prompts_vecs = [embed_model.encode(question) for question in test_prompts]
        test_gts = [item['gt'] for item in test_data]
        test_files = [""]*len(test_ids)

    if benchmark_selected == "mbpp" or benchmark_selected == "humaneval":
        valid_problems = read_problems(data_filename)
        test_problems = read_problems(test_data_filename)
    else:
        valid_problems = None
        test_problems = None
#################################################################
# Create graph                                              #
#################################################################
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d-%H-%M-%S")
    test_dir = f"dataset/{benchmark_selected.upper()}/test/{date_str}"
    os.makedirs(test_dir, exist_ok=True)
    log_file = f"{test_dir}/log.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        
        if benchmark_selected == "math" or benchmark_selected == "gpqa" or benchmark_selected == "mmlu":
            max_step = 4
        # elif benchmark_selected == "mbpp" or benchmark_selected == "humaneval":
        #     max_step = 2
        else:
            max_step = 3
        
        threshold = 0.7
        concurrency = 30
        print("Building graph starts")
        token_usage = TOKEN_USAGE
        G, node_to_vecs, node_to_rd_vecs, query_to_edge, starting_nodes, tid_to_path = build_graph(f, task_ids, task_workflows, benchmark_selected, threshold=threshold)

        n_features = 4  # Number of features in the observation 
        n_hiddens = 128
        num_rl_episodes = 100
        num_tg_episodes = 5
        # num_rl_episodes = 1
        # num_tg_episodes = 1

        #################################################################
        # Create RL Agent                                              #
        #################################################################
        RL_Agent = PolicyGradient(n_features = n_features, n_hiddens = n_hiddens, learning_rate = 0.001, gamma = 0.95)
        env = RL_Environment(G, node_to_rd_vecs, node_to_vecs)

        for i in range(len(train_workflows)):
            for j in range(len(train_workflows[i])):
                train_workflows[i][j], _, _ = get_dataset_info(train_workflows[i][j])
                train_workflows[i][j], _ = train_workflows[i][j].split("|", 1)
                train_workflows[i][j] = train_workflows[i][j].strip()
                # train_workflows[i][j] = train_workflows[i][j].replace("|", ",")
        for i in range(len(valid_workflows)):
            for j in range(len(valid_workflows[i])):
                valid_workflows[i][j], _, _ = get_dataset_info(valid_workflows[i][j])
                valid_workflows[i][j], _ = valid_workflows[i][j].split("|", 1)
                valid_workflows[i][j] = valid_workflows[i][j].strip()
                # valid_workflows[i][j] = valid_workflows[i][j].replace("|", ",")
        ##################################################################
        # Training                                      #
        ##################################################################
        result_dir = "ckpt/"

        print("Training_RL starts")
        train_start_time = time.time()
        best_score = -1
        for episode in range(num_rl_episodes):
            
            print(f"\n[TRAININGPG] Training episode = {episode+1}", file=f, flush=True)
            Training_RL(f, G, env, RL_Agent, train_ids, train_workflows, train_prompts, train_prompts_vecs, tid_to_path)
            score, time_ = Evaluation_RL(f, G, env, RL_Agent, valid_ids, valid_workflows, valid_prompts, valid_prompts_vecs, tid_to_path)
            
            # asyncio.run(Training_RL(f, G, env, RL_Agent, train_ids, train_workflows, train_prompts, train_prompts_vecs, 
            #             tid_to_path, benchmark_selected = benchmark_selected))
            # score, time_ = asyncio.run(Evaluation_RL(f, G, env, RL_Agent, valid_ids, valid_workflows, valid_prompts, valid_prompts_vecs, 
            #                              tid_to_path, benchmark_selected = benchmark_selected))
            if score > best_score or score==1.0:
                best_score = score
                PG_dir = result_dir + 'train_' + f"{best_score:.4f}_{time_:.4f}"
                os.makedirs(PG_dir, exist_ok=True)
                RL_Agent.save(PG_dir + '/test.pth')
        
        print("Training_RL_TG starts")
        
        if num_rl_episodes > 0:
            RL_Agent.load(PG_dir + '/test.pth')

        # Original System Prompt Accuracy
        best_score, time_ = asyncio.run(Evaluation_RL_TG(f, G, env, RL_Agent, concurrency, max_step, valid_problems,
                                             valid_ids, valid_gts, valid_prompts, valid_prompts_vecs, valid_files, valid_public_tests, 
                                             tid_to_path, benchmark_selected=benchmark_selected))
        print(f"original system prompt, score: {best_score}", file=f, flush=True)
        PG_dir = result_dir + 'original_RL_TG_' + f"{best_score:.4f}_{time_:.4f}"
        os.makedirs(PG_dir, exist_ok=True)
        RL_Agent.save(PG_dir + '/test.pth')
        save_system_prompt(G, PG_dir)
        
        for episode in range(num_tg_episodes):
            
            asyncio.run(Training_RL_TG(f, G, env, RL_Agent, episode, concurrency, max_step, valid_problems, 
                           train_ids, train_gts, train_prompts, train_prompts_vecs, train_files, train_public_tests, 
                           tid_to_path, benchmark_selected = benchmark_selected))
            
            score, time_ = asyncio.run(Evaluation_RL_TG(f, G, env, RL_Agent, concurrency, max_step, valid_problems, 
                                            valid_ids, valid_gts, valid_prompts, valid_prompts_vecs, valid_files, valid_public_tests, 
                                            tid_to_path, benchmark_selected = benchmark_selected))
            print(f"\n[TRAININGPG] episode_{episode+1}_score: {score}", file=f, flush=True)
            if score >= best_score or score==1.0:
                best_score = score
                PG_dir = result_dir + 'train_RL_TG_' + f"{best_score:.4f}_{time_:.4f}"
                os.makedirs(PG_dir, exist_ok=True)
                RL_Agent.save(PG_dir + '/test.pth')
                save_system_prompt(G, PG_dir)
                
        print(f"\n[TRAININGPG] train_rl_tg_score: {best_score} total_train_time: {time.time() - train_start_time}", file=f, flush=True)
        
        token_summary = token_usage.get_usage()
        train_input_tokens, train_output_tokens, train_cost = token_summary["total_input_tokens"], token_summary["total_output_tokens"], token_summary["total_cost"]
        print(f"\n[TRAININGPG] input_token: {train_input_tokens} output_token: {train_output_tokens} total_cost: {train_cost}", file=f, flush=True)
        
        print("Testing starts")
        # starting_nodes_vecs = []
        # for starting_node in starting_nodes:
        #     starting_nodes_vecs.append(node_to_vecs[starting_node])
        # tid_to_init_node_dict = build_init_node_dict(starting_nodes, starting_nodes_vecs, test_prompts_vecs, test_ids)
        
        starting_nodes_to_vecs = {}
        for starting_node in starting_nodes:
            starting_nodes_to_vecs[starting_node] = node_to_vecs[starting_node]
        # PG_dir = "C:/Users/l84405517/Desktop/Mango/Mango_async/ckpt/"
        RL_Agent.load(PG_dir + '/test.pth')
        load_system_prompt(G, PG_dir)
        test_score, test_time = asyncio.run(Evaluation_Test(f, test_dir, G, env, RL_Agent, concurrency, max_step, starting_nodes_to_vecs, test_problems, 
                                                test_ids, test_gts, test_prompts, test_prompts_vecs, test_files, test_public_tests, 
                                                benchmark_selected=benchmark_selected))

        print(f"\n[TEST] test_score: {test_score} test_time: {test_time}", file=f, flush=True)
        print(f"\n[TEST] test_score: {test_score} test_time: {test_time}")
        
        token_summary = token_usage.get_usage()
        total_input_tokens, total_output_tokens, total_cost = token_summary["total_input_tokens"], token_summary["total_output_tokens"], token_summary["total_cost"]
        
        print(f"\n[Test] input_token: {total_input_tokens-train_input_tokens} output_token: {total_output_tokens-train_output_tokens} total_cost: {total_cost-train_cost}", file=f, flush=True)
        print(f"\n[Test] input_token: {total_input_tokens-train_input_tokens} output_token: {total_output_tokens-train_output_tokens} total_cost: {total_cost-train_cost}")
        print(f"\n[TOTAL] input_token: {total_input_tokens} output_token: {total_output_tokens} total_cost: {total_cost}", file=f, flush=True)
        print(f"\n[TOTAL] input_token: {total_input_tokens} output_token: {total_output_tokens} total_cost: {total_cost}")
        
if __name__ == "__main__":
    main()