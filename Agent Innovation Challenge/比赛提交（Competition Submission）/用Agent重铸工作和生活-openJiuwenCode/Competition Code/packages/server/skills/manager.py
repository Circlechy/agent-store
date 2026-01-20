"""
Skill 管理器

整合 loader、matcher、executor、installer，提供统一的 skill 管理接口。
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Skill
from .loader import SkillLoader
from .matcher import SkillMatcher
from .executor import SkillExecutor, SkillExecutionContext
from .installer import SkillInstaller, InstalledPlugin, MarketplaceInfo


class SkillManager:
    """Skill 管理器

    提供统一的 skill 管理接口，整合加载、匹配、执行、安装功能。

    使用示例：
    >>> manager = SkillManager(project_root=Path.cwd())
    >>> manager.load_skills()
    >>> skills = manager.list_skills()
    >>> skill = manager.get_skill("my-skill")
    >>> manager.activate_skill(skill)
    >>> manager.deactivate_skill()
    >>> manager.install_plugin("example-skills@anthropics")
    >>> manager.uninstall_plugin("example-skills@anthropics")
    """

    def __init__(self, project_root: Optional[Path] = None):
        """初始化管理器

        Args:
            project_root: 项目根目录
        """
        # 初始化子组件
        self.loader = SkillLoader(project_root)
        self.matcher = SkillMatcher(self.loader)
        self.executor = SkillExecutor()
        self.installer = SkillInstaller()

    def load_skills(self, force_reload: bool = False) -> Dict[str, Skill]:
        """加载所有 skills

        Args:
            force_reload: 是否强制重新加载

        Returns:
            skill_name -> Skill 的映射
        """
        return self.loader.load_all(force_reload)

    def list_skills(self) -> List[Skill]:
        """列出所有可用的 skills

        Returns:
            Skill 列表
        """
        return self.loader.list_skills()

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定名称的 skill

        Args:
            name: Skill 名称

        Returns:
            Skill 对象
        """
        return self.loader.get_skill(name)

    def match_skill(self, user_input: str) -> Optional[Tuple[Skill, str]]:
        """匹配 skill

        Args:
            user_input: 用户输入

        Returns:
            (Skill, 参数) 或 None
        """
        return self.matcher.match(user_input)

    def match_explicit(self, user_input: str) -> Optional[Tuple[Skill, str]]:
        """显式匹配 skill

        Args:
            user_input: 用户输入

        Returns:
            (Skill, 参数) 或 None
        """
        return self.matcher.match_explicit(user_input)

    def activate_skill(self, skill: Skill) -> SkillExecutionContext:
        """激活 skill

        Args:
            skill: 要激活的 Skill

        Returns:
            执行上下文
        """
        return self.executor.activate_skill(skill)

    def deactivate_skill(self):
        """停用当前 skill"""
        self.executor.deactivate_skill()

    @property
    def is_skill_active(self) -> bool:
        """是否有 skill 正在执行"""
        return self.executor.is_skill_active

    @property
    def current_skill(self) -> Optional[Skill]:
        """当前执行的 skill"""
        return self.executor.current_skill

    def is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否被当前 skill 允许

        Args:
            tool_name: 工具名称

        Returns:
            如果允许返回 True，否则返回 False
        """
        return self.executor.is_tool_allowed(tool_name)

    def filter_tools(self, tools: List) -> List:
        """根据当前 skill 的 allowed-tools 过滤工具

        Args:
            tools: 所有可用工具列表

        Returns:
            过滤后的工具列表
        """
        return self.executor.filter_tools(tools)

    def get_prompt_suffix(self) -> str:
        """获取 skill 的提示词后缀

        Returns:
            提示词后缀
        """
        return self.executor.get_prompt_suffix()

    def ensure_dirs(self):
        """确保 skills 目录存在"""
        self.loader.ensure_dirs()

    def reload(self) -> Dict[str, Skill]:
        """重新加载所有 skills

        Returns:
            skill_name -> Skill 的映射
        """
        return self.loader.reload()

    # ==================== 插件安装管理 ====================

    def install_plugin(self, spec: str, force: bool = False) -> InstalledPlugin:
        """安装插件

        Args:
            spec: 插件规格，如 example-skills@anthropics
            force: 是否强制重新安装

        Returns:
            已安装的插件信息

        Raises:
            ValueError: 格式无效或插件不存在
            RuntimeError: 安装失败
        """
        plugin = self.installer.install(spec, force)
        # 重新加载 skills 以包含新安装的
        self.loader.reload()
        return plugin

    def uninstall_plugin(self, spec: str) -> bool:
        """卸载插件

        Args:
            spec: 插件规格，如 example-skills@anthropics

        Returns:
            是否成功

        Raises:
            ValueError: 插件未安装
        """
        result = self.installer.uninstall(spec)
        # 重新加载 skills 以移除已卸载的
        self.loader.reload()
        return result

    def update_plugin(self, spec: str) -> InstalledPlugin:
        """更新插件

        Args:
            spec: 插件规格，如 example-skills@anthropics

        Returns:
            更新后的插件信息

        Raises:
            ValueError: 插件未安装
        """
        plugin = self.installer.update(spec)
        # 重新加载 skills
        self.loader.reload()
        return plugin

    def list_installed_plugins(self) -> List[InstalledPlugin]:
        """列出已安装的插件

        Returns:
            已安装插件列表
        """
        return self.installer.list_installed()

    def add_marketplace(self, name: str, url: str) -> MarketplaceInfo:
        """添加自定义 marketplace

        Args:
            name: Marketplace 名称
            url: Git 仓库 URL

        Returns:
            Marketplace 信息
        """
        return self.installer.add_marketplace(name, url)

    def list_marketplaces(self) -> List[MarketplaceInfo]:
        """列出所有已知的 marketplace

        Returns:
            Marketplace 列表
        """
        return self.installer.list_marketplaces()
