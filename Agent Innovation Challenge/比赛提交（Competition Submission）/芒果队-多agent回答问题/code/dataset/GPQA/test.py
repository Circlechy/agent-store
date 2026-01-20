from human_eval.data import HUMAN_EVAL, read_problems, stream_jsonl, write_jsonl

a = list(stream_jsonl("dataset/GPQA/test/2025-12-01-15-51-36/Test_Ans.jsonl"))
for i in a:
    if i["answer"] != i["gt"]:
        print(i["answer"], i["gt"])