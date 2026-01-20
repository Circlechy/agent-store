import subprocess
import sys

def run_python_script(script_path):
    """
    执行单个Python脚本，实时显示输出，等待执行完成后返回结果
    :param script_path: 脚本文件路径（相对路径或绝对路径）
    """
    try:
        print(f"\n========== 开始执行脚本：{script_path} ==========")
        # 调用Python脚本，阻塞式执行，实时输出打印内容
        result = subprocess.run(
            [sys.executable, script_path], 
            # 移除PIPE，让输出直接实时显示在终端
            stdout=sys.stdout, 
            stderr=sys.stderr,  
            encoding="utf-8"    # 编码格式，避免中文乱码
        )
        
        # 判断脚本是否执行成功
        if result.returncode == 0:
            print(f"========== 脚本 {script_path} 执行成功 ==========\n")
            return True
        else:
            print(f"========== 脚本 {script_path} 执行失败，返回码：{result.returncode} ==========\n")
            return False
    
    except FileNotFoundError:
        print(f"错误：未找到脚本文件 {script_path}")
        return False
    except Exception as e:
        print(f"错误：执行脚本 {script_path} 时发生异常：{str(e)}")
        return False

def main():
    # 定义三个要执行的Python脚本路径（
    script_list = [
        "create_outline.py",   
        "create_pic.py",       
        "final.py"             
    ]
    
    # 顺序执行所有脚本
    for script in script_list:
        success = run_python_script(script)
        # 可选：若前一个脚本执行失败，终止后续脚本执行
        if not success:
            print("前一个脚本执行失败，终止所有后续任务！")
            break
    
    print("\n========== 所有任务执行流程结束 ==========")

if __name__ == "__main__":
    main()

 