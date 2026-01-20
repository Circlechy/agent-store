"""
图片存储服务模块
管理本地图片文件的存储、索引和读取
"""

import os
import uuid
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, BinaryIO, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class StorageService:
    """
    图片存储服务类
    负责图片文件的存储、索引和管理
    """

    _instance: Optional["StorageService"] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._initialized = getattr(self, '_initialized', False)
        self._storage_path: Optional[Path] = None
        self._allowed_extensions: set = {
            "jpg", "jpeg", "png", "gif", "webp", "bmp"}
        self._max_file_size: int = 50 * 1024 * 1024  # 50MB

    def initialize(
        self,
        storage_path: str,
        allowed_extensions: Optional[set] = None,
        max_file_size: Optional[int] = None
    ) -> None:
        """
        初始化存储服务

        Args:
            storage_path: 存储根目录路径
            allowed_extensions: 允许的文件扩展名
            max_file_size: 最大文件大小（字节）
        """
        if self._initialized:
            logger.info("存储服务已初始化，跳过重复初始化")
            return

        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)

        if allowed_extensions:
            self._allowed_extensions = allowed_extensions
        if max_file_size:
            self._max_file_size = max_file_size

        self._initialized = True
        logger.info(f"存储服务初始化完成，存储路径: {self._storage_path}")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self._storage_path is not None

    @property
    def storage_path(self) -> Path:
        """获取存储路径"""
        if not self.is_initialized:
            raise RuntimeError("存储服务未初始化")
        return self._storage_path

    def _generate_id(self) -> str:
        """生成标准UUID"""
        return str(uuid.uuid4())

    def _get_extension(self, filename: str) -> str:
        """获取文件扩展名"""
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def _validate_extension(self, filename: str) -> bool:
        """验证文件扩展名"""
        ext = self._get_extension(filename)
        return ext in self._allowed_extensions

    def _get_storage_subdir(self, image_id: str) -> Path:
        """
        根据ID获取存储子目录（按日期分层存储）
        """
        today = datetime.now().strftime("%Y/%m/%d")
        subdir = self._storage_path / today
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir

    def _get_image_path(self, image_id: str, extension: str) -> Path:
        """获取图片完整存储路径"""
        subdir = self._get_storage_subdir(image_id)
        return subdir / f"{image_id}.{extension}"

    def save_image(
        self,
        file_content: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        保存图片文件

        安全性设计：
        - UUID由系统自动生成，禁止外部指定
        - 文件重命名为 UUID.扩展名 格式
        - 确保标识唯一性和存储安全性

        Args:
            file_content: 文件二进制内容
            filename: 原始文件名（仅用于提取扩展名）

        Returns:
            图片信息字典
        """
        if not self.is_initialized:
            raise RuntimeError("存储服务未初始化")

        # 验证扩展名
        if not self._validate_extension(filename):
            raise ValueError(f"不支持的文件格式: {filename}")

        # 验证文件大小
        if len(file_content) > self._max_file_size:
            raise ValueError(
                f"文件大小超过限制: {len(file_content)} > {self._max_file_size}")

        # 系统生成UUID（安全性设计：禁止外部指定）
        image_id = self._generate_id()
        extension = self._get_extension(filename)

        # 文件重命名为: UUID.扩展名
        file_path = self._get_image_path(image_id, extension)

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)

        # 获取图片信息（保留原始文件名用于展示）
        image_info = self._get_image_info(file_path, image_id, filename)

        logger.info(f"图片保存成功: {image_id} (原名: {filename}) -> {file_path}")
        return image_info

    def save_image_from_path(
        self,
        source_path: str
    ) -> Dict[str, Any]:
        """
        从本地路径保存图片

        安全性设计：UUID由系统自动生成

        Args:
            source_path: 源文件路径

        Returns:
            图片信息字典
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")

        with open(source, "rb") as f:
            content = f.read()

        # 移除 image_id 参数，强制使用系统生成的UUID
        return self.save_image(content, source.name)

    def _get_image_info(
        self,
        file_path: Path,
        image_id: str,
        original_filename: str
    ) -> Dict[str, Any]:
        """获取图片详细信息"""
        try:
            stat = file_path.stat()
        except FileNotFoundError:
            # 文件可能已被删除
            return None

        # 获取图片尺寸
        width, height, img_format = 0, 0, ""
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                img_format = img.format or ""
        except Exception as e:
            logger.warning(f"无法读取图片信息: {file_path}, 错误: {e}")
            # 图片可能损坏，但我们仍然返回基本文件信息，以便用户可以看到并删除它
            img_format = "unknown"

        # 计算相对路径
        relative_path = str(file_path.relative_to(self._storage_path))

        return {
            "id": image_id,
            "filename": original_filename,
            "file_path": relative_path,
            "full_path": str(file_path),
            "file_size": stat.st_size,
            "width": width,
            "height": height,
            "format": img_format,
            "created_at": datetime.fromtimestamp(stat.st_ctime),
            "url": f"/api/v1/storage/images/{image_id}"
        }

    def get_image_path(self, image_id: str) -> Optional[Path]:
        """
        根据ID查找图片路径

        Args:
            image_id: 图片ID

        Returns:
            图片路径或None
        """
        if not self.is_initialized:
            raise RuntimeError("存储服务未初始化")

        # 遍历查找图片
        for ext in self._allowed_extensions:
            for path in self._storage_path.rglob(f"{image_id}.{ext}"):
                if path.exists():
                    return path

        return None

    def get_image(self, image_id: str) -> Optional[Tuple[bytes, str]]:
        """
        读取图片内容

        Args:
            image_id: 图片ID

        Returns:
            (文件内容, 媒体类型) 或 None
        """
        path = self.get_image_path(image_id)
        if not path:
            return None

        ext = self._get_extension(path.name)
        media_type = self._get_media_type(ext)

        with open(path, "rb") as f:
            content = f.read()

        return content, media_type

    def _get_media_type(self, extension: str) -> str:
        """获取媒体类型"""
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp"
        }
        return media_types.get(extension, "application/octet-stream")

    def get_image_info(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        获取图片信息

        Args:
            image_id: 图片ID

        Returns:
            图片信息或None
        """
        path = self.get_image_path(image_id)
        if not path:
            return None

        return self._get_image_info(path, image_id, path.name)

    def delete_image(self, image_id: str) -> bool:
        """
        删除图片

        Args:
            image_id: 图片ID

        Returns:
            是否删除成功
        """
        path = self.get_image_path(image_id)
        if not path:
            return False

        path.unlink()
        logger.info(f"图片删除成功: {image_id}")
        return True

    def list_images(
        self,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        列出所有图片

        Args:
            page: 页码
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (图片列表, 总数)
        """
        if not self.is_initialized:
            raise RuntimeError("存储服务未初始化")

        # 收集所有图片
        all_images = []
        for ext in self._allowed_extensions:
            for path in self._storage_path.rglob(f"*.{ext}"):
                # 提取ID
                image_id = path.stem
                # 兼容旧格式(img_前缀)和新格式(标准UUID)
                if image_id.startswith("img_") or self._is_valid_uuid(image_id):
                    info = self._get_image_info(path, image_id, path.name)
                    all_images.append(info)

        # 排序
        reverse = sort_order == "desc"
        all_images.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

        # 分页
        total = len(all_images)
        start = (page - 1) * page_size
        end = start + page_size

        return all_images[start:end], total

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        if not self.is_initialized:
            raise RuntimeError("存储服务未初始化")

        total_size = 0
        total_count = 0

        for ext in self._allowed_extensions:
            for path in self._storage_path.rglob(f"*.{ext}"):
                total_size += path.stat().st_size
                total_count += 1

        return {
            "total_images": total_count,
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "storage_path": str(self._storage_path)
        }

    def _is_valid_uuid(self, value: str) -> bool:
        """验证是否为有效UUID"""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    def image_exists(self, image_id: str) -> bool:
        """检查图片是否存在"""
        return self.get_image_path(image_id) is not None


# 全局服务实例
storage_service = StorageService()


def get_storage_service() -> StorageService:
    """获取存储服务实例"""
    return storage_service
