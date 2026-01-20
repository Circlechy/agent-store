import base64
import os
import json
from doc_process.utils import logging

logger = logging.get_logger()

def file_2_base64(file_path):
    with open(file_path, "rb") as f_in:
        file_ = f_in.read()
        base64_str = bytes.decode(base64.b64encode(file_))
    return base64_str


def base64_2_file(base64_str, save_path):
    with open(save_path, "wb") as f_out:
        file_ = base64.b64decode(str.encode(base64_str))
        f_out.write(file_)



def detect_dir(local_data_dir):
    # 判断目录是否存在
    if not os.path.exists(local_data_dir):
        # 如果目录不存在，则创建目录
        os.makedirs(local_data_dir, exist_ok=True)
        logger.info(f"目录 {local_data_dir} 已创建")
    else:
        logger.info(f"目录 {local_data_dir} 已经存在")

    # 修改目录权限为 770
    os.chmod(local_data_dir, 0o770)

def extract_generated_text(response, is_stream=False):
    """
    Extract model generated text from html POST response in utf-8 format.
    """
    response.encoding = 'utf-8'
    if is_stream:
        generated_text = ""

        for line in response.iter_lines(decode_unicode=True):
            if line:
                line_text = line.replace("data: ", "").strip()
                
                if line_text == "[DONE]":
                    break
                    
                try:
                    # Parse the JSON chunk
                    chunk_json = json.loads(line_text)
                    
                    # Extract the content delta
                    # Note: Structure might vary slightly, usually choices[0]['delta']['content']
                    delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    
                    generated_text += content
                    
                except json.JSONDecodeError:
                    pass # Skip invalid JSON lines
        
        return generated_text
    else:
        try:
            data = response.json()
        except Exception as e:
            return f"Error parsing JSON: {e}"

        try:
            return data['choices'][0]['message']['content']
        except (KeyError, IndexError):
            return "Error: Unexpected JSON structure"