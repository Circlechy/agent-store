import logging
import os
import re

logger = logging.getLogger(__name__)


class ShowImage:
    def __init__(self):
        self.search_image_dir = "search_image"  # 项目根目录下的 search_image 目录

    async def get_images(self, inputs: dict) -> list[dict]:
        answer = inputs.get("answer", "")

        # 获取答案内容
        content = ""
        if isinstance(answer, dict):
            content = answer.get("content", "") or answer.get("answer", "") or str(answer)
        else:
            content = str(answer)

        # 使用正则表达式匹配 [来源:来源名称](group_id)
        # 匹配规则：[来源: (捕获组1:来源名称)](捕获组2:group_id)
        matches = re.findall(r'\[来源:([^\]]+)\]\(([^)]+)\)', content)

        # 去重并保留来源信息
        # 使用字典来去重 group_id，同时保留对应的 source
        # 修复 Bug: 如果 group_ids_str 是多个 ID 的组合（如 "id1, id2" 或 "(id1, id2)"）
        # 需要将其拆分为独立的 key，以便后续分别查找对应的图片文件
        unique_images_map = {}
        for source, group_ids_str in matches:
            # 1. 预处理：去掉可能存在的包裹括号和前后空格
            clean_ids_str = group_ids_str.strip('() ')
            # 2. 拆分：支持中英文逗号、空格、分号等多种分隔符
            group_ids = [gid.strip() for gid in re.split(r'[,，\s;；]+', clean_ids_str)]

            for group_id in group_ids:
                if group_id and group_id not in unique_images_map:
                    unique_images_map[group_id] = source.strip()

        # 日志打印：包含 ID 和 来源的映射关系，方便排查哪些图片来源匹配失败
        logger.info(f'[ShowImage] Found unique images mapping (ID -> Source): {unique_images_map}')

        image_list = []

        if os.path.exists(self.search_image_dir) and unique_images_map:
            # 获取目录下所有文件，避免多次 IO
            all_files = os.listdir(self.search_image_dir)
            for group_id, source in unique_images_map.items():
                # 忽略大小写查找同名文件
                for filename in all_files:
                    name, ext = os.path.splitext(filename)
                    if name.lower() == group_id.lower():
                        # 构造访问路径
                        # 注意：这里假设 backend/api/main.py 已经挂载了 /api/v1/search_images 路由
                        # 前端 getApiUrl 会自动添加 /api/v1 前缀，所以这里只需要返回 /search_images/{filename}
                        image_list.append({
                            "url": f"/search_images/{filename}",
                            "source": source
                        })
                        break

        logger.info(f'[ShowImage] Found images: {image_list}')
        return image_list
