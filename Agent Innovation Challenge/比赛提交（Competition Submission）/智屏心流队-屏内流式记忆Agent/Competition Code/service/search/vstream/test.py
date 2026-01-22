import requests
import json
import os
import base64

with open("data_out copy.json", "r") as f:
  json_data = json.load(f)

print("json loaded")
print(json_data['model'])
print(len(json_data['messages'][1]['content']))

# os.environ["http_proxy"] = "http://y84416470:YCB8*86*6@10.155.96.165:8080"
# os.environ["https_proxy"] = os.environ["http_proxy"]
# os.environ["http_proxy"] = "http://10.155.97.225:3128"
# os.environ['https_proxy'] = os.environ['http_proxy']
# os.environ["no_proxy"] = "localhost,127.0.0.1,.huawei.com"
print(os.environ['https_proxy'])


headers={
  "Authorization": "Bearer sk-eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkZXBhcnRtZW50TmFtZSI6InVua25vd24iLCJhY2NvdW50SWQiOiJkNTk5MDA0NTQiLCJrZXlWZXJzaW9uIjoiMi4wIiwiYWNjb3VudE5hbWUiOiJkb25neXVrdW4iLCJ0ZW5hbnRJZCI6IjM3ZmI2OTU5NWVlMjYxOGM2ZTI5ODY2NzAyMWQyNmExIn0.cqH9PEeAza20JbyXGxlkTd6aoSPBXXjGtVkuw56YCsI",
  "Content-Type": "application/json",
}

url = 'http://mlops.huawei.com/mlops-service/api/v2/agentService/v1/chat/completions'

# with open("test_image.jpg", "rb") as image_file:
#        image_data = base64.b64encode(image_file.read()).decode('utf-8')

# json_data = {
#        "model": "qwen3-vl-32b-instruct-npu", # "MiniCPM-v2.6-ModelArts"
#        "messages": [
#            {
#                "role": "user",
#                "content": [
#                    {
#                        "type": "text",
#                        "text": "图片里的内容是什么？"
#                    },
#                    {
#                        "type": "image_url",
#                        "image_url": {
#                            "url": f"data:image/jpeg;base64,{image_data}"
#                        }
#                    }
#                ]
#            }
#        ],
#        "max_tokens": 2048
#    }

response = requests.post(url, headers=headers, json=json_data)
response.raise_for_status()
response.encoding = 'utf-8'

print("--- Streaming Response ---")

# 3. Iterate over lines (handles the stream chunks)
for line in response.iter_lines(decode_unicode=True):
    if line:
        # Remove the "data: " prefix common in SSE streams
        line_text = line.replace("data: ", "").strip()
        
        # specific check to handle the [DONE] signal often sent at the end
        if line_text == "[DONE]":
            break
            
        try:
            # Parse the JSON chunk
            chunk_json = json.loads(line_text)
            
            # Extract the content delta
            # Note: Structure might vary slightly, usually choices[0]['delta']['content']
            delta = chunk_json.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            
            # Print without newlines to form a coherent sentence
            print(content, end='', flush=True)
            
        except json.JSONDecodeError:
            pass # Skip invalid JSON lines

print("\n--- End of Stream ---")


def get_document_count(host_url, index_name):
    """
    Get the total number of documents in an Elasticsearch index.
    
    Args:
        host_url: Elasticsearch service address
        index_name: Name of the index to check
        username: (Optional)
        password: (Optional)
    """
    # Endpoint for counting documents
    url = f"{host_url.rstrip('/')}/{index_name}/_count"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        # We generally use GET for a simple count, but POST with match_all works too
        response = requests.get(
            url, 
            headers=headers, 
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        # The API returns simple JSON: {"count": 123, "_shards": ...}
        count = result.get("count", 0)
        print(f"✅ Success: Index '{index_name}' contains {count} documents.")
        return count

    except requests.exceptions.RequestException as e:
        print(f"❌ API Request Error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Error Details: {e.response.text}")
        return None
    