from flask import Flask, render_template, request, jsonify, send_from_directory  # 新增 send_from_directory
import subprocess
import threading
import queue
import os
import sys


app = Flask(__name__)
app.secret_key = "comic_maker_combined_123456"

# 全局变量：输出队列、输入缓存、输入锁
output_queue = queue.Queue()
user_input_cache = queue.Queue()
input_lock = threading.Lock()


SYSTEM_ENCODING = "utf-8"


SCRIPT_LIST = [
    "comic_script_creator.py",
    "comic_pics_creator.py",      
    "comic_layout_formatter.py"             
]


TEST_DIR = "./test"


def print_to_queue(content):
    """
    替代原有print()，将所有输出存入队列，供SSE实时推送到网页终端
    新增：给后端普通输出添加 [OUTPUT] 前缀
    """
    if content:  
        try:

            content_safe = content.encode(SYSTEM_ENCODING, errors="ignore").decode(SYSTEM_ENCODING)
           
            output_queue.put(f"[OUTPUT] {content_safe.strip()}")
            print(content_safe.strip())
        except:
           
            output_queue.put(f"[OUTPUT] {content.strip()}")
            print(content.strip())

def run_python_script(script_path):
    """
    执行单个子脚本：utf-8 编码传输，支持 emoji，解除 input() 阻塞
    """
    try:
        #print_to_queue(f"\n========== 开始执行脚本：{script_path} ==========")
        

        env = os.environ.copy()  
        env["PYTHONIOENCODING"] = "utf-8"  
        env["PYTHONUTF8"] = "1"  
        env["LC_ALL"] = "en_US.UTF-8" 
        
        # 启动子脚本：-u 禁用缓冲，utf-8 编码，传入修改后的环境变量
        process = subprocess.Popen(
            [sys.executable, "-u", script_path],  
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=SYSTEM_ENCODING, 
            bufsize=0,  
            text=True,
            env=env  
        )
        
        # 实时读取子脚本 stdout
        def read_stdout():
            char_buffer = ""  # 字符缓冲区：累积要推送的内容
            while process.poll() is None:
                # 按字符读取
                char = process.stdout.read(1)
                if not char:
                    continue
                

                if char == "\r":
                    char_buffer += "\n"  # \r 转成 \n，实现换行
                    continue
                
    
                if char == "\n":
                    if char_buffer:  
                        print_to_queue(char_buffer.strip("\n")) 
                        char_buffer = ""  
                    continue
                
                char_buffer += char
        
        # 实时读取子脚本 stderr
        def read_stderr():
            while process.poll() is None:
                stderr_line = process.stderr.readline()
                if stderr_line:
                    output_queue.put(f"[ERROR] {stderr_line.strip()}")
        
        # 启动读取线程
        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()
        
        # 实时写入网页输入到子脚本 stdin
        while process.poll() is None:
            try:
                if not user_input_cache.empty():
                    user_input = user_input_cache.get_nowait().strip()
                    if user_input and process.stdin:
                        process.stdin.write(user_input + "\n")
                        process.stdin.flush()
                        #print_to_queue(f"=== 已将输入传递给子脚本：{user_input} ===")
                import time
                time.sleep(0.1)
            except queue.Empty:
                continue
            except Exception as e:
                
                output_queue.put(f"[ERROR] 写入子脚本输入失败：{str(e)}")
                break
        
        # 等待子脚本执行完成
        process.wait()
        try:
            if 'char_buffer' in locals() and char_buffer:
                print_to_queue(char_buffer.strip())  # 推送剩余内容
        except:
            pass
        # 读取剩余输出（防止 emoji 遗漏）
        remaining_stdout = process.stdout.read()
        remaining_stderr = process.stderr.read()
        if remaining_stdout:
            print_to_queue(remaining_stdout.strip())
        if remaining_stderr:
            # 【已存在】[ERROR] 前缀，标记子脚本剩余错误输出
            output_queue.put(f"[ERROR] {remaining_stderr.strip()}")
        
        # 判断执行结果
        if process.returncode == 0:
            #print_to_queue(f"========== 脚本 {script_path} 执行成功 ==========\n")
            return True
        else:
            print_to_queue(f"========== 脚本 {script_path} 执行失败，返回码：{process.returncode} ==========\n")
            return False
    
    except FileNotFoundError:
        error_msg = f"错误：未找到脚本文件 {script_path}"
        # 【修改点2】确保 [ERROR] 前缀统一，标记文件未找到错误
        output_queue.put(f"[ERROR] {error_msg}")
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"错误：执行脚本 {script_path} 时发生异常：{str(e)}"
        # 【修改点2】确保 [ERROR] 前缀统一，标记执行脚本异常
        output_queue.put(f"[ERROR] {error_msg}")
        print(error_msg)
        return False

def comic_create_main():
    """
    对应你的comic_create.py main函数，顺序执行所有子脚本
    """
    #print_to_queue("=== 漫画创作流程启动，开始顺序执行子脚本 ===")
    #print_to_queue(f"待执行脚本列表：{', '.join(SCRIPT_LIST)}")
    print_to_queue(f"您好，我是漫画创作agent。")
    # 顺序执行子脚本，失败则终止
    for script in SCRIPT_LIST:
        success = run_python_script(script)
        if not success:
            fail_msg = "前一个脚本执行失败，终止所有后续任务！"
            # 【已存在】[ERROR] 前缀，标记任务终止错误
            output_queue.put(f"[ERROR] {fail_msg}")
            print_to_queue(fail_msg)
            break
    
    #print_to_queue("\n========== 所有任务执行流程结束 ==========")

def run_comic_create_in_background():
    """
    后台线程执行漫画创作逻辑，避免阻塞Flask主线程
    """
    try:
        comic_create_main()
    except Exception as e:
        error_msg = f"漫画创作流程整体执行异常：{str(e)}"
        # 【修改点3】确保 [ERROR] 前缀统一，标记整体流程异常
        output_queue.put(f"[ERROR] {error_msg}")
        print(error_msg)

@app.route("/")
def index():
    """
    网页首页：加载index.html，启动漫画创作流程
    """
    # 自动创建 test 目录（若不存在），保留原有逻辑
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)
        print_to_queue(f"=== 自动创建 test 目录（用于存储JSON/图片文件）===")
    
    # 检查子脚本是否存在
    missing_scripts = [script for script in SCRIPT_LIST if not os.path.exists(script)]
    if missing_scripts:
        error_msg = f"缺少必要子脚本：{', '.join(missing_scripts)}，请检查文件路径"
        # 【已存在】[ERROR] 前缀，标记缺少子脚本错误
        output_queue.put(f"[ERROR] {error_msg}")
        print(error_msg)
    
    # 启动后台线程执行漫画创作逻辑
    threading.Thread(
        target=run_comic_create_in_background,
        daemon=True
    ).start()
    
    return render_template("index.html")

@app.route("/test/<path:filename>")
def serve_test_files(filename):
    """
    路由：通过 http://127.0.0.1:5000/test/xxx.jpg 访问 ./test/xxx.jpg
    """
    try:
        return send_from_directory(TEST_DIR, filename)
    except Exception as e:
        error_msg = f"访问文件失败：{str(e)}"
        # 【已存在】[ERROR] 前缀，标记文件访问失败错误
        output_queue.put(f"[ERROR] {error_msg}")
        return error_msg, 404

@app.route("/stream")
def stream():
    """
    SSE接口：实时推送输出队列中的内容到网页终端
    """
    def generate():
        while True:
            try:
                # 阻塞等待队列中的新内容，确保实时性
                line = output_queue.get(timeout=1)
                yield f"data: {line}\n\n"  # 符合SSE标准格式
            except queue.Empty:
                continue
    
    return app.response_class(generate(), mimetype="text/event-stream")

@app.route("/send_input", methods=["POST"])
def send_input():
    """
    接收网页输入，存入缓存
    新增：给用户输入添加 [YOU] 前缀
    """
    data = request.get_json()
    user_input = data.get("input", "").strip()
    
    if user_input:
        with input_lock:
            user_input_cache.put(user_input)
        
        # 【修改点4】添加 [YOU] 前缀，标记用户输入（核心）
        output_queue.put(f"[YOU] {user_input}")
        return jsonify({"success": True, "msg": "输入已保存"})
    else:
        return jsonify({"success": False, "msg": "输入内容不能为空"})

# ===================== 4. 启动入口 =====================
if __name__ == "__main__":
    print("=== 整合版漫画创作网页终端启动中 ===")
    print(f"系统编码适配：{SYSTEM_ENCODING}")
    print(f"子脚本列表：{', '.join(SCRIPT_LIST)}")
    print("请打开浏览器访问：http://127.0.0.1:5000")
    print(f"test 目录访问地址：http://127.0.0.1:5000/test/[文件名]")
    print("="*50)
    
    # 启动Flask服务（threaded=True开启多线程，支持同时处理SSE和POST请求）
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)