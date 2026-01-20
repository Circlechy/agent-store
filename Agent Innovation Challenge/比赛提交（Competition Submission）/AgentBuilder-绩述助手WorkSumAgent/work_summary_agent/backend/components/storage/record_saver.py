# -*- coding: utf-8 -*-
"""
记录保存组件

保存分析结果到JSON文件，支持相似记录合并
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
from openjiuwen.core.component.base import ComponentExecutable, WorkflowComponent
from openjiuwen.core.runtime.runtime import Runtime
from openjiuwen.core.context_engine.base import Context
from openjiuwen.core.common.logging import logger

# 工作记录存储目录
_current_file = Path(__file__).resolve()
WORK_RECORDS_DIR = _current_file.parent.parent.parent.parent / "work_records"
WORK_RECORDS_DIR.mkdir(exist_ok=True)


class RecordSaverComponent(ComponentExecutable, WorkflowComponent):
    """记录保存组件 - 保存分析结果到JSON文件"""
    
    # 时间窗口（秒）：在此时间内的记录会自动合并
    TIME_WINDOW_SECONDS = 30  # 30秒（缩短时间窗口，减少过度合并）
    
    def __init__(self, work_records_dir: Optional[Path] = None, time_window_seconds: int = 30):
        """
        初始化记录保存组件
        
        Args:
            work_records_dir: 工作记录目录，如果为None则使用默认目录
            time_window_seconds: 时间窗口（秒），在此时间内的记录会自动合并（默认60秒）
        """
        self.work_records_dir = work_records_dir or WORK_RECORDS_DIR
        self.work_records_dir.mkdir(exist_ok=True)
        self.time_window_seconds = time_window_seconds
    
    async def invoke(self, inputs: Dict[str, Any], runtime: Runtime, context: Context) -> Dict[str, Any]:
        """
        保存工作记录
        
        Args:
            inputs: 输入数据，包含：
                - content: 分析结果（来自ContentAnalyzer组件）
                - date: 日期（格式: YYYY-MM-DD，可选，默认今天）
                - timestamp: 时间戳（ISO格式字符串，可选，默认当前时间）
                - merge_similar: 是否合并相似记录（默认True）
                - metadata: 元数据（来自提取器组件，可选）
            runtime: 运行时上下文
            context: 上下文引擎
            
        Returns:
            保存结果字典：
                - saved: 是否成功保存
                - record_file: 记录文件路径
                - date: 日期
                - timestamp: 时间戳
        """
        # 获取分析结果（来自ContentAnalyzer）
        # content可能是字典，也可能直接是分析结果
        content = inputs.get("content", {})
        
        # 如果content是空字典或None，尝试从inputs中直接获取分析结果字段
        if not content or (isinstance(content, dict) and not content.get("tasks") and not content.get("work_content")):
            # 尝试从inputs中直接获取分析结果
            if "tasks" in inputs or "work_content" in inputs:
                content = {
                    "tasks": inputs.get("tasks", []),
                    "work_content": inputs.get("work_content", ""),
                    "achievements": inputs.get("achievements", []),
                    "issues": inputs.get("issues", []),
                    "next_steps": inputs.get("next_steps", []),
                }
        
        if not content or (isinstance(content, dict) and not content.get("tasks") and not content.get("work_content")):
            logger.warning("记录保存组件：分析结果为空")
            return {
                "saved": False,
                "error": "分析结果为空"
            }
        
        # 获取日期和时间戳
        date = inputs.get("date") or datetime.now().strftime("%Y-%m-%d")
        # 统一使用带 'Z' 的 UTC 时间戳格式（与前端保持一致）
        if inputs.get("timestamp"):
            timestamp = inputs.get("timestamp")
        else:
            # 生成带 'Z' 的 UTC 时间戳（与前端 toISOString() 格式一致）
            timestamp = datetime.utcnow().isoformat() + 'Z'
        merge_similar = inputs.get("merge_similar", True)
        
        record_file = self.work_records_dir / f"{date}.json"
        
        try:
            # 读取现有记录
            records: List[Dict[str, Any]] = []
            if record_file.exists():
                try:
                    with open(record_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                except Exception as e:
                    logger.warning(f"读取现有记录失败: {e}，将创建新文件")
                    records = []
            
            # 如果启用合并，尝试合并
            if merge_similar and records:
                # 优先检查时间窗口：1分钟内的记录直接合并
                merged = self._try_merge_by_time_window(records, content, timestamp)
                if merged:
                    logger.info(f"检测到时间窗口内的记录（{self.time_window_seconds}秒内），已合并到现有记录中（日期: {date}）")
                    records = merged
                else:
                    # 时间窗口内没有记录，再检查内容相似度
                    merged = self._try_merge_similar_record(records, content, timestamp)
                    if merged:
                        logger.info(f"检测到相似内容，已合并到现有记录中（日期: {date}）")
                        records = merged
                    else:
                        # 无法合并，添加新记录
                        logger.debug(f"未检测到可合并记录，添加新记录（日期: {date}）")
                        new_record = {
                            "timestamp": timestamp,
                            "content": content
                        }
                        records.append(new_record)
            else:
                # 不合并，直接添加新记录
                new_record = {
                    "timestamp": timestamp,
                    "content": content
                }
                records.append(new_record)
            
            # 保存到文件
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            
            logger.info(f"记录保存成功: {record_file.name}，共 {len(records)} 条记录")
            
            return {
                "saved": True,
                "record_file": str(record_file),
                "date": date,
                "timestamp": timestamp,
                "record_count": len(records)
            }
        except Exception as e:
            logger.error(f"记录保存失败: {e}", exc_info=True)
            return {
                "saved": False,
                "error": str(e),
                "date": date
            }
    
    def _try_merge_by_time_window(
        self, 
        existing_records: List[Dict[str, Any]], 
        new_content: Dict[str, Any], 
        new_timestamp: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        尝试将新内容合并到时间窗口内的记录中
        
        Args:
            existing_records: 现有记录列表
            new_content: 新内容
            new_timestamp: 新记录的时间戳（ISO格式字符串）
            
        Returns:
            如果成功合并，返回更新后的记录列表；否则返回None
        """
        if not existing_records or not new_content:
            return None
        
        try:
            # 解析新记录的时间戳
            # 处理带 'Z' 的 UTC 时间戳
            timestamp_str = new_timestamp.replace('Z', '+00:00') if new_timestamp.endswith('Z') else new_timestamp
            new_time = datetime.fromisoformat(timestamp_str)
            # 如果有时区信息，转换为本地时间进行比较
            if new_time.tzinfo is not None:
                # 转换为本地时间（无时区）以便比较
                new_time = new_time.replace(tzinfo=None)
        except Exception:
            try:
                # 尝试直接解析（无时区）
                new_time = datetime.fromisoformat(new_timestamp)
            except Exception as e:
                logger.warning(f"解析新时间戳失败: {new_timestamp}, 错误: {e}，跳过时间窗口检查")
                return None
        
        # 检查最近的记录（最多检查最近10条）
        check_count = min(10, len(existing_records))
        recent_records = existing_records[-check_count:] if len(existing_records) >= check_count else existing_records
        
        # 从最新到最旧查找时间窗口内的记录
        for record in reversed(recent_records):
            record_timestamp = record.get("timestamp")
            if not record_timestamp:
                continue
            
            try:
                # 解析记录的时间戳
                # 处理带 'Z' 的 UTC 时间戳
                timestamp_str = record_timestamp.replace('Z', '+00:00') if record_timestamp.endswith('Z') else record_timestamp
                record_time = datetime.fromisoformat(timestamp_str)
                # 如果有时区信息，转换为本地时间进行比较
                if record_time.tzinfo is not None:
                    record_time = record_time.replace(tzinfo=None)
                
                # 计算时间差（秒）
                time_diff = abs((new_time - record_time).total_seconds())
                
                # 如果在时间窗口内，检查内容类型和任务主题
                if time_diff <= self.time_window_seconds:
                    existing_content = record.get("content", {})
                    
                    # 检查内容类型：如果类型不同，不合并
                    existing_type = existing_content.get("content_type", "own_work")
                    new_type = new_content.get("content_type", "own_work")
                    
                    # 如果内容类型不同，不合并（即使在一分钟内）
                    if existing_type != new_type and existing_type != "mixed" and new_type != "mixed":
                        logger.debug(
                            f"时间窗口内的记录但内容类型不同（时间差: {time_diff:.1f}秒，"
                            f"现有类型: {existing_type}，新类型: {new_type}），不合并"
                        )
                        continue  # 继续检查下一条记录
                    
                    # 检查任务主题相似度：如果任务完全不同，不合并
                    task_similarity = self._calculate_task_similarity(
                        existing_content.get("tasks", []),
                        new_content.get("tasks", [])
                    )
                    
                    # 如果任务相似度太低（没有共同任务），不合并
                    TASK_SIMILARITY_THRESHOLD = 0.5  # 至少要有50%的任务相似度（提高阈值，避免不同事情混在一起）
                    if task_similarity < TASK_SIMILARITY_THRESHOLD:
                        logger.debug(
                            f"时间窗口内的记录但任务主题不同（时间差: {time_diff:.1f}秒，"
                            f"任务相似度: {task_similarity:.2%}），不合并"
                        )
                        continue  # 继续检查下一条记录
                    
                    # 内容类型相同且任务主题相似，可以合并
                    merged_content = self._merge_content(existing_content, new_content)
                    record["content"] = merged_content
                    # 更新时间戳为最新的
                    record["timestamp"] = new_timestamp
                    logger.info(
                        f"检测到时间窗口内的记录（时间差: {time_diff:.1f}秒，"
                        f"内容类型: {existing_type}，任务相似度: {task_similarity:.2%}），已合并"
                    )
                    return existing_records
            except Exception as e:
                logger.warning(f"解析记录时间戳失败: {record_timestamp}, 错误: {e}，跳过此记录")
                continue
        
        return None
    
    def _try_merge_similar_record(
        self, 
        existing_records: List[Dict[str, Any]], 
        new_content: Dict[str, Any],
        new_timestamp: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        尝试将新内容合并到相似记录中（基于内容相似度）
        
        Args:
            existing_records: 现有记录列表
            new_content: 新内容
            new_timestamp: 新记录的时间戳（ISO格式字符串）
            
        Returns:
            如果成功合并，返回更新后的记录列表；否则返回None
        """
        if not existing_records or not new_content:
            return None
        
        # 检查新内容是否与最近的记录相似（检查最近10条记录）
        check_count = min(10, len(existing_records))
        recent_records = existing_records[-check_count:] if len(existing_records) >= check_count else existing_records
        
        # 计算相似度分数，找到最相似的记录
        best_match = None
        best_score = 0.0
        
        for record in reversed(recent_records):  # 从最新到最旧
            existing_content = record.get("content", {})
            similarity_score = self._calculate_similarity_score(existing_content, new_content)
            
            if similarity_score > best_score:
                best_score = similarity_score
                best_match = record
        
        # 如果相似度超过阈值，进行合并
        SIMILARITY_THRESHOLD = 0.15
        
        if best_score >= SIMILARITY_THRESHOLD and best_match is not None:
            existing_content = best_match.get("content", {})
            # 合并内容
            merged_content = self._merge_content(existing_content, new_content)
            best_match["content"] = merged_content
            # 更新时间戳为最新的
            best_match["timestamp"] = new_timestamp
            logger.info(f"检测到相似内容（相似度: {best_score:.2%}），已合并到现有记录中")
            return existing_records
        
        return None
    
    def _calculate_task_similarity(self, tasks1: List[str], tasks2: List[str]) -> float:
        """
        计算任务列表的相似度
        
        Args:
            tasks1: 第一个任务列表
            tasks2: 第二个任务列表
            
        Returns:
            相似度分数（0-1之间），0表示完全不同，1表示完全相同
        """
        if not tasks1 and not tasks2:
            # 都没有任务，认为相似
            return 1.0
        
        if not tasks1 or not tasks2:
            # 一个有空任务，另一个有任务，认为不相似
            return 0.0
        
        # 将任务转换为小写并去除空白，用于比较
        tasks1_normalized = [t.lower().strip() for t in tasks1 if t and t.strip()]
        tasks2_normalized = [t.lower().strip() for t in tasks2 if t and t.strip()]
        
        if not tasks1_normalized or not tasks2_normalized:
            return 0.0
        
        # 计算集合相似度（Jaccard相似度）
        set1 = set(tasks1_normalized)
        set2 = set(tasks2_normalized)
        
        # 交集大小
        intersection = len(set1 & set2)
        # 并集大小
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        # Jaccard相似度 = 交集 / 并集
        similarity = intersection / union
        
        return similarity
    
    def _calculate_similarity_score(self, content1: Dict[str, Any], content2: Dict[str, Any]) -> float:
        """计算两个内容的相似度分数（0-1之间）"""
        scores = []
        
        # 1. 任务相似度（权重：0.3）
        tasks1 = set([t.lower().strip() for t in content1.get("tasks", []) if t])
        tasks2 = set([t.lower().strip() for t in content2.get("tasks", []) if t])
        if tasks1 or tasks2:
            if tasks1 & tasks2:
                task_score = len(tasks1 & tasks2) / max(len(tasks1 | tasks2), 1)
                scores.append(("tasks", task_score, 0.3))
            else:
                scores.append(("tasks", 0.0, 0.3))
        
        # 2. 工作内容相似度（权重：0.4）
        work_content1 = content1.get("work_content", "").lower().strip()
        work_content2 = content2.get("work_content", "").lower().strip()
        if work_content1 and work_content2:
            words1 = [w for w in work_content1.split() if len(w) >= 2]
            words2 = [w for w in work_content2.split() if len(w) >= 2]
            
            if words1 and words2:
                keywords1 = set(words1[:20])
                keywords2 = set(words2[:20])
                
                if keywords1 & keywords2:
                    overlap_ratio = len(keywords1 & keywords2) / max(len(keywords1 | keywords2), 1)
                    scores.append(("work_content_keywords", overlap_ratio, 0.4))
        
        # 计算加权平均
        if scores:
            total_weight = sum(weight for _, _, weight in scores)
            weighted_sum = sum(score * weight for _, score, weight in scores)
            return weighted_sum / total_weight if total_weight > 0 else 0.0
        
        return 0.0
    
    def _merge_content(self, existing_content: Dict[str, Any], new_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并两个内容记录
        
        Args:
            existing_content: 现有内容
            new_content: 新内容
            
        Returns:
            合并后的内容
        """
        # 合并 tasks（去重）
        existing_tasks = set([t.lower().strip() for t in existing_content.get("tasks", []) if t])
        new_tasks = set([t.lower().strip() for t in new_content.get("tasks", []) if t])
        merged_tasks = list(existing_tasks | new_tasks)
        
        # 合并 work_content（用换行分隔，如果内容差异大则用分隔符区分）
        existing_work = existing_content.get("work_content", "").strip()
        new_work = new_content.get("work_content", "").strip()
        if existing_work and new_work:
            # 如果两个工作内容差异很大，用分隔符明确区分，避免不同事情混在一起
            # 简单检查：如果内容长度差异很大，可能是不同的事情
            len_diff_ratio = abs(len(existing_work) - len(new_work)) / max(len(existing_work), len(new_work)) if max(len(existing_work), len(new_work)) > 0 else 0
            if len_diff_ratio > 0.5:
                # 内容长度差异大（>50%），可能是不同的事情，用分隔符区分
                merged_work_content = f"{existing_work}\n\n---\n\n{new_work}"
            else:
                merged_work_content = f"{existing_work}\n{new_work}"
        elif existing_work:
            merged_work_content = existing_work
        else:
            merged_work_content = new_work
        
        # 合并 achievements（去重，基于 title）
        existing_achievements = existing_content.get("achievements", [])
        new_achievements = new_content.get("achievements", [])
        achievement_titles = set()
        merged_achievements = []
        
        # 先添加现有的
        for ach in existing_achievements:
            if isinstance(ach, dict):
                title = ach.get("title", "").strip()
                if title and title not in achievement_titles:
                    achievement_titles.add(title)
                    merged_achievements.append(ach)
            elif ach:
                merged_achievements.append(ach)
        
        # 再添加新的
        for ach in new_achievements:
            if isinstance(ach, dict):
                title = ach.get("title", "").strip()
                if title and title not in achievement_titles:
                    achievement_titles.add(title)
                    merged_achievements.append(ach)
            elif ach:
                merged_achievements.append(ach)
        
        # 合并 issues（去重）
        existing_issues = [i.strip() for i in existing_content.get("issues", []) if i and i.strip()]
        new_issues = [i.strip() for i in new_content.get("issues", []) if i and i.strip()]
        merged_issues = list(set(existing_issues + new_issues))
        
        # 合并 next_steps（去重）
        existing_steps = [s.strip() for s in existing_content.get("next_steps", []) if s and s.strip()]
        new_steps = [s.strip() for s in new_content.get("next_steps", []) if s and s.strip()]
        merged_steps = list(set(existing_steps + new_steps))
        
        # 保留 content_type（优先使用新内容的类型，如果是 mixed 则保持）
        existing_type = existing_content.get("content_type", "own_work")
        new_type = new_content.get("content_type", "own_work")
        if existing_type == "mixed" or new_type == "mixed":
            merged_type = "mixed"
        elif existing_type != new_type:
            merged_type = "mixed"  # 类型不同时设为 mixed
        else:
            merged_type = existing_type
        
        merged = {
            "content_type": merged_type,
            "tasks": merged_tasks,
            "work_content": merged_work_content,
            "achievements": merged_achievements,
            "issues": merged_issues,
            "next_steps": merged_steps,
        }
        
        # 保留 metadata（使用新内容的 metadata）
        if "metadata" in new_content:
            merged["metadata"] = new_content["metadata"]
        elif "metadata" in existing_content:
            merged["metadata"] = existing_content["metadata"]
        
        return merged
