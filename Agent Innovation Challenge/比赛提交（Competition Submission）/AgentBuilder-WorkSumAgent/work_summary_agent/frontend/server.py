# -*- coding: utf-8 -*-
"""
工作总结管理系统 - Web服务器

提供前端页面的API接口和静态文件服务
"""

import os
import sys
import json
import asyncio
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 添加项目根目录到Python路径
# server.py 位于 work_summary_agent/frontend/server.py
# 需要向上1级到达项目根目录: frontend -> work_summary_agent
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
sys.path.insert(0, str(project_root))
# 添加backend目录到路径
sys.path.insert(0, str(project_root / "backend"))

# 加载.env文件中的环境变量
# .env文件统一放在work_summary_agent目录下（项目根目录）
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        print(f"✓ 已加载环境变量文件: {env_file}")
    else:
        print(f"⚠ 未找到.env文件: {env_file}")
        print("  请确保.env文件位于work_summary_agent目录下")
        print("  将使用系统环境变量")
except ImportError:
    print("⚠ python-dotenv未安装，无法加载.env文件")
    print("  请安装: pip install python-dotenv")

# 导入工作总结Agent（使用适配器保持向后兼容）
from backend.work_summary_agent_adapter import WorkSummaryAgentAdapter as WorkSummaryAgent
from backend.screen_capture import get_screen_capture

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # 允许跨域请求

# 工作记录目录（与 work_summary_agent.py 保持一致）
# work_records 目录位于项目根目录下
WORK_RECORDS_DIR = project_root / "work_records"
WORK_RECORDS_DIR.mkdir(exist_ok=True)

# 上传文件临时目录
UPLOAD_DIR = project_root / "frontend" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 支持的文件格式
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md', '.json'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

# 初始化Agent（延迟初始化）
# 注意：对于截图功能，需要使用单例模式保持状态一致性
# 但对于异步操作，仍然需要创建新实例以避免事件循环冲突
_agent = None
_screenshot_agent = None  # 专门用于截图功能的单例Agent

def get_agent():
    """
    获取Agent实例（用于异步操作）
    
    注意：为了确保事件循环隔离，每次调用都创建新实例
    这样可以避免openjiuwen框架内部的事件循环状态污染
    """
    # 每次都创建新实例，确保事件循环隔离
    return WorkSummaryAgent(image_processing_mode="multimodal")

def get_screenshot_agent():
    """
    获取用于截图功能的Agent实例（单例模式）
    
    截图功能的启动/停止需要保持状态，所以使用单例模式
    """
    global _screenshot_agent
    if _screenshot_agent is None:
        _screenshot_agent = WorkSummaryAgent(image_processing_mode="multimodal")
    return _screenshot_agent


def run_async(coro_factory):
    """
    在Flask的同步环境中运行异步协程
    
    使用asyncio.run()在独立线程中运行，确保事件循环完全隔离
    这与测试脚本的方式一致，确保httpx.AsyncClient能正确工作
    
    Args:
        coro_factory: 一个函数，返回异步协程对象。这样可以确保Agent和协程都在正确的线程中创建
        
    Returns:
        协程的执行结果
    """
    import concurrent.futures
    import threading
    
    def run_in_thread():
        """在独立线程中使用asyncio.run()运行协程"""
        # 使用asyncio.run()创建新的事件循环并运行协程
        # 这与测试脚本的方式完全一致
        # asyncio.run()会自动创建、设置、运行和关闭事件循环
        try:
            # 在事件循环创建后，再创建协程对象
            # 这样确保Agent和协程都在正确的事件循环上下文中
            coro = coro_factory()
            return asyncio.run(coro)
        except Exception as e:
            # 记录详细错误信息以便调试
            import traceback
            print(f"异步执行错误: {e}")
            print(traceback.format_exc())
            raise
    
    # 在独立线程中运行，避免阻塞Flask主线程
    # 使用max_workers=1确保串行执行，避免并发问题
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        try:
            return future.result(timeout=300)  # 5分钟超时
        except concurrent.futures.TimeoutError:
            raise Exception("异步操作超时")
        except Exception as e:
            import traceback
            print(f"线程执行错误: {e}")
            print(traceback.format_exc())
            raise


def allowed_file(filename, file_type):
    """检查文件扩展名是否允许"""
    if not '.' in filename:
        return False
    ext = '.' + filename.rsplit('.', 1)[1].lower()
    if file_type == 'document':
        return ext in ALLOWED_DOCUMENT_EXTENSIONS
    elif file_type == 'image':
        return ext in ALLOWED_IMAGE_EXTENSIONS
    return False


def save_uploaded_file(file, file_type):
    """保存上传的文件到临时目录"""
    if not allowed_file(file.filename, file_type):
        raise ValueError(f"不支持的文件格式: {file.filename}")
    
    # 生成安全的文件名
    filename = secure_filename(file.filename)
    # 添加唯一ID防止文件名冲突
    unique_id = str(uuid.uuid4())[:8]
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{unique_id}{ext}"
    filepath = UPLOAD_DIR / unique_filename
    
    # 保存文件
    file.save(str(filepath))
    return filepath


@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('.', 'index.html')


@app.route('/api/work-records/dates', methods=['GET'])
def get_work_record_dates():
    """
    获取所有有记录的日期列表
    
    Returns:
        包含所有有记录的日期的JSON数组
    """
    try:
        record_files = list(WORK_RECORDS_DIR.glob("*.json"))
        dates = []
        for record_file in record_files:
            # 从文件名提取日期（格式：YYYY-MM-DD.json）
            date_str = record_file.stem
            try:
                # 验证日期格式
                datetime.strptime(date_str, "%Y-%m-%d")
                dates.append(date_str)
            except ValueError:
                # 忽略格式不正确的文件名
                continue
        
        # 排序日期
        dates.sort()
        return jsonify(dates)
    except Exception as e:
        print(f"获取日期列表错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/work-records', methods=['GET'])
def get_work_records():
    """
    获取工作记录
    
    Query参数:
        date: 日期 (格式: YYYY-MM-DD，默认今天)
    """
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    record_file = WORK_RECORDS_DIR / f"{date_str}.json"
    
    if not record_file.exists():
        return jsonify([])
    
    try:
        with open(record_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/work-records', methods=['POST'])
def add_work_record():
    """
    添加工作记录
    
    JSON Body:
        content: 工作内容（必填）
        timestamp: 时间戳 (ISO格式，可选)
    """
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': '工作内容不能为空'}), 400
        
        # 统一使用带 'Z' 的 UTC 时间戳格式（与前端 JavaScript toISOString() 保持一致）
        timestamp = data.get('timestamp') or (datetime.utcnow().isoformat() + 'Z')
        
        # 使用辅助函数运行异步代码
        # 注意：Agent和协程都在run_async内部创建，确保在正确的事件循环中
        def create_coro():
            agent = get_agent()
            return agent.add_text_record(
                content,
                timestamp=timestamp,
                incremental=True
            )
        
        result = run_async(create_coro)
        
        try:
            return jsonify({
                'success': True,
                'message': '记录添加成功',
                'result': result
            })
        except Exception as e:
            import traceback
            print(f"处理错误: {e}")
            print(traceback.format_exc())
            return jsonify({'error': f'处理失败: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/work-records/<date>/<timestamp>', methods=['DELETE'])
def delete_work_record(date, timestamp):
    """
    删除工作记录
    
    URL参数:
        date: 日期 (格式: YYYY-MM-DD)
        timestamp: 时间戳 (ISO格式字符串，需要URL编码)
    """
    try:
        # URL解码时间戳
        import urllib.parse
        timestamp = urllib.parse.unquote(timestamp)
        
        agent = get_agent()
        success = agent.delete_work_record(date, timestamp)
        
        if success:
            return jsonify({
                'success': True,
                'message': '记录删除成功'
            })
        else:
            return jsonify({'error': '记录不存在或删除失败'}), 404
            
    except Exception as e:
        import traceback
        print(f"删除记录错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/work-records/<date>/<timestamp>', methods=['PUT'])
def update_work_record(date, timestamp):
    """
    更新工作记录
    
    URL参数:
        date: 日期 (格式: YYYY-MM-DD)
        timestamp: 时间戳 (ISO格式字符串，需要URL编码)
    
    JSON Body:
        content: 更新后的记录内容（字典格式）
    """
    try:
        # URL解码时间戳
        import urllib.parse
        timestamp = urllib.parse.unquote(timestamp)
        
        data = request.get_json()
        content = data.get('content')
        
        if not content:
            return jsonify({'error': '记录内容不能为空'}), 400
        
        agent = get_agent()
        success = agent.update_work_record(date, timestamp, content)
        
        if success:
            return jsonify({
                'success': True,
                'message': '记录更新成功'
            })
        else:
            return jsonify({'error': '记录不存在或更新失败'}), 404
            
    except Exception as e:
        import traceback
        print(f"更新记录错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/work-records/<date>/clear', methods=['DELETE'])
def clear_all_records(date):
    """
    清空指定日期的所有工作记录
    
    URL参数:
        date: 日期 (格式: YYYY-MM-DD)
    """
    try:
        print(f"[清空] 收到清空请求，日期: {date}")
        agent = get_agent()
        success = agent.clear_day_records(date)
        
        if success:
            print(f"[清空] 成功清空日期 {date} 的所有记录")
            return jsonify({
                'success': True,
                'message': f'已清空 {date} 的所有记录'
            })
        else:
            print(f"[清空] 日期 {date} 没有记录可清空")
            return jsonify({
                'success': True,
                'message': f'{date} 没有记录可清空'
            })
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[清空] 清空记录错误: {error_msg}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': error_msg,
            'message': f'清空失败: {error_msg}'
        }), 500


@app.route('/api/work-records/<date>/consolidate', methods=['POST'])
def consolidate_records(date):
    """
    整合指定日期的相似记录（使用LLM分析）
    
    URL参数:
        date: 日期 (格式: YYYY-MM-DD)
    
    JSON Body (可选):
        similarity_threshold: 相似度阈值 (0-1之间，默认0.2，保留兼容性)
    """
    print(f"[整合] 收到整合请求，日期: {date}")
    try:
        data = request.get_json() or {}
        threshold = data.get('similarity_threshold', 0.2)
        print(f"[整合] 相似度阈值: {threshold}")
        
        # 使用辅助函数运行异步代码
        def create_coro():
            print(f"[整合] 创建协程，日期: {date}")
            agent = get_agent()
            # 确保返回协程对象
            return agent.consolidate_day_records(date, similarity_threshold=threshold)
        
        try:
            print(f"[整合] 开始执行异步整合...")
            reduced_count = run_async(create_coro)
            print(f"[整合] 整合完成，减少记录数: {reduced_count}")
        except Exception as e:
            import traceback
            print(f"[整合] 整合记录执行错误: {e}")
            print(traceback.format_exc())
            raise
        
        if reduced_count > 0:
            message = f'已整合记录，减少 {reduced_count} 条'
        else:
            message = '没有需要合并的记录'
        
        print(f"[整合] 返回结果: {message}")
        return jsonify({
            'success': True,
            'message': message,
            'reduced_count': reduced_count
        })
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[整合] 整合记录错误: {error_msg}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': error_msg,
            'message': f'整合失败: {error_msg}'
        }), 500


@app.route('/api/work-records/summary', methods=['GET'])
def get_summary():
    """
    获取工作总结（支持日期范围）
    
    Query参数:
        start_date: 开始日期 (格式: YYYY-MM-DD，必需)
        end_date: 结束日期 (格式: YYYY-MM-DD，必需)
        如果只提供date参数，则视为单日汇总（向后兼容）
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # 向后兼容：如果只提供了date参数，视为单日
        if not start_date and not end_date:
            date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            start_date = date_str
            end_date = date_str

        if not start_date or not end_date:
            return jsonify({'error': '请提供start_date和end_date参数'}), 400

        # 验证日期格式
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': '日期格式错误，请使用YYYY-MM-DD格式'}), 400

        # 验证日期范围
        if start_date > end_date:
            return jsonify({'error': '开始日期不能晚于结束日期'}), 400

        agent = get_agent()

        # 使用辅助函数运行异步代码
        if start_date == end_date:
            # 单日汇总，使用原有方法
            summary = run_async(
                lambda: agent.summarize_day_records(start_date, use_llm=True)
            )
        else:
            # 日期范围汇总
            summary = run_async(
                lambda: agent.summarize_date_range(start_date, end_date, use_llm=True)
            )
        try:
            return jsonify(summary)
        except Exception as e:
            import traceback
            print(f"处理错误: {e}")
            print(traceback.format_exc())
            return jsonify({'error': f'生成总结失败: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/work_records/<path:filename>')
def serve_work_record(filename):
    """提供工作记录文件的访问"""
    return send_from_directory(WORK_RECORDS_DIR, filename)


@app.route('/api/screenshot/capture', methods=['POST'])
def capture_screenshot():
    """
    手动截取屏幕并自动分析记录
    
    JSON Body (可选):
        timestamp: 时间戳 (ISO格式，可选)
    """
    try:
        data = request.get_json() or {}
        # 统一使用带 'Z' 的 UTC 时间戳格式（与前端 JavaScript toISOString() 保持一致）
        timestamp = data.get('timestamp') or (datetime.utcnow().isoformat() + 'Z')
        
        # 使用辅助函数运行异步代码
        def create_coro():
            agent = get_agent()
            return agent.capture_and_analyze(
                timestamp=timestamp,
                incremental=True
            )
        
        result = run_async(create_coro)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': '截图并分析成功',
                'result': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '截图失败')
            }), 500
            
    except Exception as e:
        import traceback
        print(f"截图错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/screenshot/auto/start', methods=['POST'])
def start_auto_screenshot():
    """
    启动自动截图功能
    
    JSON Body:
        interval: 截图间隔（秒，默认5）
    """
    try:
        data = request.get_json() or {}
        interval = data.get('interval', 5)
        
        if interval <= 0:
            return jsonify({'error': '截图间隔必须大于0'}), 400
        
        # 使用单例Agent，保持状态一致性
        agent = get_screenshot_agent()
        agent.start_auto_screenshot(interval)
        return jsonify({
            'success': True,
            'interval': interval,
            'running': agent.is_auto_screenshot_running()
        })
        
    except Exception as e:
        import traceback
        print(f"启动自动截图错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/screenshot/auto/stop', methods=['POST'])
def stop_auto_screenshot():
    """停止自动截图功能"""
    try:
        # 使用单例Agent，保持状态一致性
        agent = get_screenshot_agent()
        print(f"停止截图前状态: running={agent.is_auto_screenshot_running()}")
        
        # 获取停止前的统计信息
        stats = agent.get_screenshot_stats()
        
        # stop_auto_screenshot 现在会以 ScreenCapture 的实际状态为准
        agent.stop_auto_screenshot()
        
        running = agent.is_auto_screenshot_running()
        print(f"停止截图后状态: running={running}")
        
        return jsonify({
            'success': True,
            'running': running,
            'stats': stats  # 返回统计信息
        })
        
    except Exception as e:
        import traceback
        print(f"停止自动截图错误: {e}")
        print(traceback.format_exc())
        # 即使出错，也尝试直接停止 ScreenCapture（作为最后的保险）
        try:
            from backend.screen_capture import get_screen_capture
            screen_capture = get_screen_capture()
            if screen_capture.is_auto_capture_running():
                screen_capture.stop_auto_capture()
                print("已通过直接调用 ScreenCapture 停止截图")
        except Exception as e2:
            print(f"直接停止ScreenCapture也失败: {e2}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/screenshot/auto/status', methods=['GET'])
def get_auto_screenshot_status():
    """获取自动截图状态"""
    try:
        # 使用单例Agent，is_auto_screenshot_running 现在以 ScreenCapture 的实际状态为准
        agent = get_screenshot_agent()
        
        stats = agent.get_screenshot_stats()
        
        return jsonify({
            'running': agent.is_auto_screenshot_running(),
            'interval': agent.get_screenshot_interval(),
            'stats': stats  # 返回统计信息
        })
        
    except Exception as e:
        import traceback
        print(f"获取自动截图状态错误: {e}")
        print(traceback.format_exc())
        # 如果Agent出错，至少返回ScreenCapture的状态
        try:
            from backend.screen_capture import get_screen_capture
            screen_capture = get_screen_capture()
            return jsonify({
                'running': screen_capture.is_auto_capture_running(),
                'interval': screen_capture.get_auto_capture_interval()
            })
        except:
            return jsonify({'error': str(e)}), 500


@app.route('/api/work-records/upload', methods=['POST'])
def upload_work_record():
    """
    上传文件（文档或图片）作为工作记录
    
    Form Data:
        file: 文件（必填）
        type: 文件类型 (document/image，必填)
        timestamp: 时间戳 (ISO格式，可选)
        text_content: 用户输入的文本内容（可选，用于与文件内容整合）
    """
    try:
        # 检查文件是否存在
        if 'file' not in request.files:
            return jsonify({'error': '未找到文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
        
        file_type = request.form.get('type', '').lower()
        if file_type not in ['document', 'image']:
            return jsonify({'error': '文件类型必须是 document 或 image'}), 400
        
        # 统一使用带 'Z' 的 UTC 时间戳格式（与前端 JavaScript toISOString() 保持一致）
        timestamp = request.form.get('timestamp') or (datetime.utcnow().isoformat() + 'Z')
        text_content = request.form.get('text_content', '').strip()  # 获取用户输入的文本内容
        
        # 保存上传的文件
        try:
            filepath = save_uploaded_file(file, file_type)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        try:
            # 使用辅助函数运行异步代码
            # 注意：Agent和协程都在run_async内部创建，确保在正确的事件循环中
            def create_coro():
                agent = get_agent()
                if file_type == 'document':
                    return agent.add_document_record(
                        str(filepath),
                        timestamp=timestamp,
                        incremental=True,
                        additional_text=text_content  # 传递用户输入的文本
                    )
                elif file_type == 'image':
                    return agent.add_image_record(
                        str(filepath),
                        timestamp=timestamp,
                        incremental=True,
                        additional_text=text_content  # 传递用户输入的文本
                    )
            
            result = run_async(create_coro)
            
            return jsonify({
                'success': True,
                'message': '文件上传并处理成功',
                'result': result
            })
        except Exception as e:
            import traceback
            print(f"处理错误: {e}")
            print(traceback.format_exc())
            return jsonify({'error': f'处理失败: {str(e)}'}), 500
        finally:
            # 处理完成后删除临时文件
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception as e:
                print(f"删除临时文件失败: {e}")
                
    except Exception as e:
        import traceback
        print(f"错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("工作总结管理系统 - Web服务器")
    print("=" * 60)
    print(f"访问地址: http://localhost:5000")
    print(f"工作记录目录: {WORK_RECORDS_DIR}")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("\n⚠ 警告: 未设置 API_KEY 环境变量")
        print("内容分析功能可能无法正常工作")
        print("请设置环境变量: export API_KEY=your_api_key\n")
    
    # 检查工作记录目录
    if not WORK_RECORDS_DIR.exists():
        print(f"\n⚠ 警告: 工作记录目录不存在: {WORK_RECORDS_DIR}")
        print("将自动创建该目录\n")
    else:
        # 列出已有的记录文件
        record_files = list(WORK_RECORDS_DIR.glob("*.json"))
        if record_files:
            print(f"\n✓ 找到 {len(record_files)} 个工作记录文件")
            for f in sorted(record_files)[:5]:  # 只显示前5个
                print(f"  - {f.name}")
            if len(record_files) > 5:
                print(f"  ... 还有 {len(record_files) - 5} 个文件")
        else:
            print("\nℹ 工作记录目录为空，等待添加记录...")
        print()
    
    app.run(host='0.0.0.0', port=5000, debug=True)