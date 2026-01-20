"""
定时任务工具 - 自动化执行
使用 APScheduler 实现定时自动 Dreaming
"""

import sys
from pathlib import Path

# 当作为脚本直接运行时，添加父目录到 Python 路径
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import asyncio
import json
from datetime import datetime, time
from typing import Optional, Callable, Dict, Any, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# 根据运行方式选择导入方式
try:
    from .inbox_tools import count_pending_fragments
    from .backup_tools import auto_backup
    from ..config import DATA_DIR
except ImportError:
    from deep_digest.src.tools.inbox_tools import count_pending_fragments
    from deep_digest.src.tools.backup_tools import auto_backup
    from deep_digest.src.config import DATA_DIR

# 通知文件路径
NOTIFICATIONS_FILE = Path(DATA_DIR) / "notifications.json"


# 全局调度器
_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """
    获取全局调度器（单例模式）
    
    Returns:
        BackgroundScheduler 实例
    """
    global _scheduler
    
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            timezone='Asia/Shanghai',
            job_defaults={
                'coalesce': True,  # 合并错过的任务
                'max_instances': 1  # 同一任务最多1个实例
            }
        )
        _scheduler.start()
        print("✅ 调度器已启动")
    
    return _scheduler


def stop_scheduler():
    """停止调度器"""
    global _scheduler
    
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        print("✅ 调度器已停止")


def add_daily_job(
    job_id: str,
    func: Callable,
    hour: int,
    minute: int = 0,
    **kwargs
) -> bool:
    """
    添加每日定时任务
    
    Args:
        job_id: 任务 ID（唯一标识）
        func: 要执行的函数
        hour: 小时 (0-23)
        minute: 分钟 (0-59)
        **kwargs: 传递给函数的参数
    
    Returns:
        是否添加成功
    
    Example:
        >>> add_daily_job("backup", auto_backup, hour=2, minute=0)
        True
    """
    scheduler = get_scheduler()
    
    try:
        # 检查任务是否已存在
        if scheduler.get_job(job_id):
            print(f"⚠️  任务已存在: {job_id}")
            return False
        
        # 添加任务
        scheduler.add_job(
            func=func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            name=f"每日任务 {hour:02d}:{minute:02d}",
            kwargs=kwargs,
            replace_existing=True
        )
        
        print(f"✅ 已添加每日任务: {job_id} (每天 {hour:02d}:{minute:02d})")
        return True
    
    except Exception as e:
        print(f"❌ 添加任务失败: {e}")
        return False


def add_interval_job(
    job_id: str,
    func: Callable,
    minutes: int = None,
    hours: int = None,
    **kwargs
) -> bool:
    """
    添加间隔执行任务
    
    Args:
        job_id: 任务 ID
        func: 要执行的函数
        minutes: 间隔分钟数
        hours: 间隔小时数
        **kwargs: 传递给函数的参数
    
    Returns:
        是否添加成功
    
    Example:
        >>> add_interval_job("check", check_inbox, minutes=30)
        True
    """
    scheduler = get_scheduler()
    
    try:
        # 检查任务是否已存在
        if scheduler.get_job(job_id):
            print(f"⚠️  任务已存在: {job_id}")
            return False
        
        # 添加任务
        scheduler.add_job(
            func=func,
            trigger=IntervalTrigger(minutes=minutes, hours=hours),
            id=job_id,
            name=f"间隔任务 ({minutes}分钟)" if minutes else f"间隔任务 ({hours}小时)",
            kwargs=kwargs,
            replace_existing=True
        )
        
        interval_str = f"{minutes}分钟" if minutes else f"{hours}小时"
        print(f"✅ 已添加间隔任务: {job_id} (每 {interval_str})")
        return True
    
    except Exception as e:
        print(f"❌ 添加任务失败: {e}")
        return False


def remove_job(job_id: str) -> bool:
    """
    移除定时任务
    
    Args:
        job_id: 任务 ID
    
    Returns:
        是否移除成功
    """
    scheduler = get_scheduler()
    
    try:
        scheduler.remove_job(job_id)
        print(f"✅ 已移除任务: {job_id}")
        return True
    except Exception as e:
        print(f"❌ 移除任务失败: {e}")
        return False


def list_jobs() -> list:
    """
    列出所有定时任务
    
    Returns:
        任务列表
    """
    scheduler = get_scheduler()
    
    jobs = []
    
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A",
            "trigger": str(job.trigger)
        })
    
    return jobs


def add_notification(message: str, type: str = "info"):
    """
    添加通知消息
    
    Args:
        message: 通知内容
        type: 通知类型 (info/success/warning/error)
    """
    try:
        # 读取现有通知
        if NOTIFICATIONS_FILE.exists():
            with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
                notifications = json.load(f)
        else:
            notifications = []
        
        # 添加新通知
        notifications.append({
            "message": message,
            "type": type,
            "timestamp": datetime.now().isoformat(),
            "read": False
        })
        
        # 只保留最近 50 条通知
        notifications = notifications[-50:]
        
        # 保存
        NOTIFICATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(notifications, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 添加通知失败: {e}")


def get_notifications(unread_only: bool = False) -> List[Dict]:
    """
    获取通知列表
    
    Args:
        unread_only: 是否只返回未读通知
    
    Returns:
        通知列表
    """
    try:
        if not NOTIFICATIONS_FILE.exists():
            return []
        
        with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
            notifications = json.load(f)
        
        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]
        
        return notifications
    except Exception as e:
        print(f"⚠️ 读取通知失败: {e}")
        return []


def mark_notifications_read():
    """
    标记所有通知为已读
    """
    try:
        if not NOTIFICATIONS_FILE.exists():
            return
        
        with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
            notifications = json.load(f)
        
        for n in notifications:
            n["read"] = True
        
        with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(notifications, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 标记通知已读失败: {e}")


def _run_async_in_thread(coro):
    """
    在后台线程中安全地运行异步协程
    
    Args:
        coro: 异步协程对象
    
    Returns:
        协程的返回值
    """
    # 创建新的事件循环（线程安全）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 运行协程直到完成
        result = loop.run_until_complete(coro)
        return result
    except Exception as e:
        print(f"❌ 异步任务执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理所有待处理的任务
        try:
            # 取消所有待处理的任务
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # 等待所有任务完成取消
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass  # 忽略清理过程中的错误
        finally:
            # 关闭事件循环
            loop.close()


def auto_dreaming_job(
    agent_factory: Callable = None,
    threshold: int = 10
):
    """
    自动 Dreaming 任务
    
    Args:
        agent_factory: Agent 工厂函数（返回 Night Agent）
        threshold: 触发阈值（待处理碎片数量）
    """
    try:
        # 检查待处理碎片数量
        pending_count = count_pending_fragments()
        
        print(f"[Auto Dreaming] 检测到 {pending_count} 条待处理碎片")
        
        if pending_count < threshold:
            print(f"[Auto Dreaming] 未达到阈值 ({threshold})，跳过执行")
            return
        
        print(f"[Auto Dreaming] 开始自动整理...")
        
        # 如果提供了 agent_factory，执行 Night Agent
        if agent_factory:
            # 创建事件循环（必须在创建 agent 之前）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 在事件循环中创建 agent 和执行任务
                agent = agent_factory()
                result = loop.run_until_complete(agent.invoke(inputs={}))
                print(f"[Auto Dreaming] 整理完成: {result}")
                
                # 添加成功通知
                add_notification(
                    f"🌙 自动整理完成！已处理 {pending_count} 条碎片",
                    type="success"
                )
            finally:
                # 清理事件循环
                try:
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as cleanup_error:
                    print(f"⚠️ 清理事件循环时出错: {cleanup_error}")
                finally:
                    loop.close()
        else:
            print("[Auto Dreaming] 未提供 agent_factory，跳过执行")
    
    except Exception as e:
        import traceback
        print(f"❌ [Auto Dreaming] 执行失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        
        # 添加错误通知
        add_notification(
            f"❌ 自动整理失败: {str(e)[:100]}",
            type="error"
        )


def setup_auto_dreaming(
    enabled: bool = True,
    hour: int = 23,
    minute: int = 0,
    threshold: int = 10,
    agent_factory: Callable = None
) -> bool:
    """
    配置自动 Dreaming
    
    Args:
        enabled: 是否启用
        hour: 执行时间（小时）
        minute: 执行时间（分钟）
        threshold: 触发阈值
        agent_factory: Agent 工厂函数
    
    Returns:
        是否配置成功
    """
    job_id = "auto_dreaming"
    
    # 如果禁用，移除任务
    if not enabled:
        return remove_job(job_id)
    
    # 添加任务
    return add_daily_job(
        job_id=job_id,
        func=auto_dreaming_job,
        hour=hour,
        minute=minute,
        agent_factory=agent_factory,
        threshold=threshold
    )


def setup_auto_backup(
    enabled: bool = True,
    hour: int = 2,
    minute: int = 0,
    max_backups: int = 7
) -> bool:
    """
    配置自动备份
    
    Args:
        enabled: 是否启用
        hour: 执行时间（小时）
        minute: 执行时间（分钟）
        max_backups: 最大备份数量
    
    Returns:
        是否配置成功
    """
    job_id = "auto_backup"
    
    # 如果禁用，移除任务
    if not enabled:
        return remove_job(job_id)
    
    # 添加任务
    return add_daily_job(
        job_id=job_id,
        func=auto_backup,
        hour=hour,
        minute=minute,
        max_backups=max_backups
    )


if __name__ == "__main__":
    print("=" * 70)
    print("定时任务工具测试")
    print("=" * 70)
    
    # 测试 1: 添加每日备份任务
    print("\n[测试 1] 添加每日备份任务...")
    setup_auto_backup(enabled=True, hour=2, minute=0)
    
    # 测试 2: 添加自动 Dreaming 任务
    print("\n[测试 2] 添加自动 Dreaming 任务...")
    setup_auto_dreaming(enabled=True, hour=23, minute=0, threshold=10)
    
    # 测试 3: 列出所有任务
    print("\n[测试 3] 列出所有任务...")
    jobs = list_jobs()
    
    print(f"\n当前有 {len(jobs)} 个定时任务:")
    for job in jobs:
        print(f"  • {job['name']:<30} 下次执行: {job['next_run']}")
    
    # 测试 4: 立即执行一次备份（测试）
    print("\n[测试 4] 立即执行备份...")
    auto_backup(max_backups=5)
    
    print("\n✅ 测试完成")
    print("⚠️  调度器将继续运行，按 Ctrl+C 停止")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n停止调度器...")
        stop_scheduler()
