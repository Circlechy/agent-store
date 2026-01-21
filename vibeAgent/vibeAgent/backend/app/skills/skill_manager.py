"""
技能管理器

负责加载技能并构建可注入的提示词内容
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
import yaml
import re
import os
from loguru import logger

from app.config.settings import get_settings


class SkillManager:
    """技能管理器"""
    
    def __init__(self, skills_dir: Optional[Path] = None):
        """
        初始化技能管理器
        
        Args:
            skills_dir: 技能目录路径
        """
        settings = get_settings()
        if skills_dir is None:
            # 默认使用 backend_v3 目录下的 skills 目录
            # __file__ = backend_v3/app/skills/skill_manager.py
            # .parent.parent.parent = backend_v3/
            backend_v3_root = Path(__file__).parent.parent.parent
            skills_dir = backend_v3_root / settings.skills_dir
        
        self.skills_dir = Path(skills_dir)
        self._skill_cache: Dict[str, Dict[str, Any]] = {}
        self._file_mtimes: Dict[str, float] = {}  # 记录文件修改时间
    
    def load_skill(self, skill_name: str, force_reload: bool = False) -> Optional[Dict[str, Any]]:
        """
        加载技能
        
        Args:
            skill_name: 技能名称
            force_reload: 强制重新加载（忽略缓存）
        
        Returns:
            技能数据（包含 frontmatter 和 body），如果不存在则返回 None
        """
        skill_dir = self.skills_dir / skill_name
        skill_file = skill_dir / "SKILL.md"
        
        if not skill_file.exists():
            logger.warning(f"技能文件不存在: {skill_file}")
            return None
        
        # 检查文件是否更新（基于修改时间）
        cache_key = f"{skill_name}"
        current_mtime = os.path.getmtime(skill_file)
        
        # 检查 references 目录的修改时间
        ref_dir = skill_dir / "references"
        if ref_dir.exists():
            for ref_file in ref_dir.glob("*.md"):
                ref_mtime = os.path.getmtime(ref_file)
                if ref_mtime > current_mtime:
                    current_mtime = ref_mtime
        
        # 如果文件已更新或强制重新加载，清除缓存
        if force_reload or cache_key not in self._file_mtimes or current_mtime > self._file_mtimes[cache_key]:
            if cache_key in self._skill_cache:
                logger.info(f"检测到技能文件更新，清除缓存: {skill_name}")
                del self._skill_cache[cache_key]
        
        # 检查缓存
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]
        
        try:
            # 读取文件内容
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 解析 YAML frontmatter
            frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
            match = re.match(frontmatter_pattern, content, re.DOTALL)
            
            if match:
                frontmatter_str = match.group(1)
                body = match.group(2)
                frontmatter = yaml.safe_load(frontmatter_str) or {}
            else:
                # 没有 frontmatter，只有 body
                frontmatter = {}
                body = content
            
            # 加载 references
            references = self._load_references(skill_dir)
            
            skill_data = {
                "name": skill_name,
                "frontmatter": frontmatter,
                "body": body,
                "references": references,
                "skill_dir": skill_dir
            }
            
            # 缓存
            self._skill_cache[skill_name] = skill_data
            self._file_mtimes[cache_key] = current_mtime
            
            return skill_data
        
        except Exception as e:
            logger.error(f"加载技能失败: {skill_name}, 错误: {e}")
            return None
    
    def _load_references(self, skill_dir: Path) -> Dict[str, str]:
        """
        加载技能目录下的 references
        
        Args:
            skill_dir: 技能目录
        
        Returns:
            references 字典 {文件名: 内容}
        """
        references = {}
        ref_dir = skill_dir / "references"
        
        if not ref_dir.exists():
            return references
        
        for ref_file in ref_dir.glob("*.md"):
            try:
                with open(ref_file, "r", encoding="utf-8") as f:
                    references[ref_file.name] = f.read()
            except Exception as e:
                logger.warning(f"加载 reference 失败: {ref_file}, 错误: {e}")
        
        return references
    
    def clear_cache(self, skill_name: Optional[str] = None):
        """
        清除技能缓存
        
        Args:
            skill_name: 技能名称，如果为 None 则清除所有缓存
        """
        if skill_name:
            if skill_name in self._skill_cache:
                del self._skill_cache[skill_name]
                logger.info(f"已清除技能缓存: {skill_name}")
        else:
            self._skill_cache.clear()
            logger.info("已清除所有技能缓存")
    
    def get_skill_content(
        self,
        skill_name: str,
        context: Optional[Dict[str, Any]] = None,
        include_references: Optional[List[str]] = None,
        token_budget: Optional[int] = None
    ) -> str:
        """
        获取技能内容（用于注入到 system prompt）
        
        Args:
            skill_name: 技能名称
            context: 上下文信息（用于构建 prompt）
            include_references: 需要包含的 references 列表（如果为 None，则包含所有）
            token_budget: token 预算（超预算时裁剪 references）
        
        Returns:
            技能内容字符串
        """
        skill_data = self.load_skill(skill_name)
        if not skill_data:
            return ""
        
        parts = []
        
        # 1. 添加 SKILL.md 的 body
        parts.append(f"## {skill_name}\n\n{skill_data['body']}")
        
        # 2. 添加 references
        if include_references is None:
            # 包含所有 references
            include_references = list(skill_data["references"].keys())
        
        ref_contents = []
        for ref_name in include_references:
            if ref_name in skill_data["references"]:
                ref_contents.append(f"### {ref_name}\n\n{skill_data['references'][ref_name]}")
        
        if ref_contents:
            parts.append("\n\n".join(ref_contents))
        
        # 3. 如果设置了 token_budget，进行裁剪
        if token_budget:
            content = "\n\n".join(parts)
            # 简单估算：1 token ≈ 4 字符（中文更少，这里保守估计）
            estimated_tokens = len(content) // 3
            
            if estimated_tokens > token_budget:
                # 裁剪：优先保留 SKILL.md body，裁剪 references
                logger.warning(f"技能内容超过 token 预算 ({estimated_tokens} > {token_budget})，进行裁剪")
                # 简单实现：只保留 SKILL.md body
                parts = [parts[0]]  # 只保留第一个部分（SKILL.md body）
        
        return "\n\n".join(parts)
    
    def get_multiple_skills_content(
        self,
        skill_names: List[str],
        context: Optional[Dict[str, Any]] = None,
        include_references: Optional[Dict[str, List[str]]] = None,
        token_budget: Optional[int] = None
    ) -> str:
        """
        获取多个技能的内容
        
        Args:
            skill_names: 技能名称列表
            context: 上下文信息
            include_references: 每个技能需要包含的 references（{skill_name: [ref_names]})
            token_budget: token 预算
        
        Returns:
            合并后的技能内容
        """
        contents = []
        
        for skill_name in skill_names:
            skill_refs = include_references.get(skill_name) if include_references else None
            content = self.get_skill_content(
                skill_name=skill_name,
                context=context,
                include_references=skill_refs,
                token_budget=token_budget // len(skill_names) if token_budget else None
            )
            if content:
                contents.append(content)
        
        return "\n\n---\n\n".join(contents)

    def load_references_code(self, skill_name: str, file_name: str|list[str]) -> str:
        """
        加载技能目录下的 assets 中的指定文件内容
        
        Args:
            skill_name: 技能名称
            file_name: 文件名或文件名列表
        
        Returns:
            文件内容字符串，如果传入多个文件则合并返回
        """
        skill_dir = self.skills_dir / skill_name
        assets_dir = skill_dir / "assets"
        
        if not assets_dir.exists():
            logger.warning(f"技能 assets 目录不存在: {assets_dir}")
            return ""
        
        # 统一处理为列表
        file_names = [file_name] if isinstance(file_name, str) else file_name
        
        contents = []
        for name in file_names:
            file_path = assets_dir / name
            if not file_path.exists():
                logger.warning(f"文件不存在: {file_path}")
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # 如果多个文件，添加文件名作为注释分隔
                    if len(file_names) > 1:
                        contents.append(f"# === {name} ===\n{content}")
                    else:
                        contents.append(content)
            except Exception as e:
                logger.error(f"加载文件失败: {file_path}, 错误: {e}")
        
        return "\n\n".join(contents) if contents else ""
