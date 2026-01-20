import json
from PIL import Image, ImageDraw, ImageFont

# ---------------------- 可配置参数----------------------
BASE_ROOT="test"
JSON_FILE_PATH = f"./{BASE_ROOT}/panel_plan.json"  # JSON文件路径
IMAGE_PREFIX = ""  # 图片前缀
IMAGE_FORMAT = "png"  # 图片格式
PER_IMAGE_BLANK_HEIGHT = 150  # 每张图片下方预留的空白高度
TEXT_SIZE = 40  # 文字大小
TEXT_COLOR = (0, 0, 0)  # 文字颜色（黑色，RGB格式）
TEXT_PADDING = 20  # 文字与图片边缘的内边距
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
ROW_IMG_COUNT = 2  # 每行排列图片数量（固定为2）
IMG_SPACING = 50  # 图片之间的间距（横向+纵向）
FINAL_IMAGE_BACKGROUND = (255, 255, 255)  # 最终大图背景色
OUTPUT_IMAGE_PATH = f"./{BASE_ROOT}/final_comic_collage.jpg"  # 最终合成图片保存路径


def load_comic_scenes(json_path):
    """读取JSON文件，返回场景内容字典（key=场景编号，value=场景描述）"""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            comic_data = json.load(f)
        scene_dict = {}
        for scene in comic_data["scene_list"]:
            scene_num = scene["scene_num"]
            scene_content = scene["scene_text"]
            scene_dict[scene_num] = scene_content
        return scene_dict
    except FileNotFoundError:
        raise Exception(f"JSON文件未找到：{json_path}")
    except KeyError as e:
        raise Exception(f"JSON文件格式错误，缺少关键字段：{e}")

def draw_wrapped_text(draw, text, font, max_width, start_y, image_width, text_color, blank_height):
    """
    优化版：中文自适应换行+文字在空白区域内水平/垂直居中（自适应位置）
    :param draw: ImageDraw对象
    :param text: 要绘制的文字内容
    :param font: 文字字体
    :param max_width: 文字最大绘制宽度（图片宽度-2*内边距）
    :param start_y: 空白区域起始y坐标（原图底部）
    :param image_width: 图片宽度
    :param text_color: 文字颜色
    :param blank_height: 空白区域总高度
    """
    # 1. 初始化变量
    current_line = ""  # 当前行文字
    current_y = 0  # 行绘制y坐标
    line_height = font.getbbox("测")[3] - font.getbbox("测")[1] + 10  # 行高
    all_lines = []  # 存储所有换行后的完整行

    # 2. 逐个字符遍历，实现中文精准换行
    for char in text:
        # 跳过空字符
        if char == "\n":
            if current_line:
                all_lines.append(current_line)
                current_line = ""
            continue
        
        # 测试当前字符加入后是否超出最大宽度
        test_line = current_line + char
        test_bbox = draw.textbbox((0, 0), test_line, font=font)
        test_width = test_bbox[2] - test_bbox[0]

        if test_width <= max_width:
            # 未超出宽度，保留当前行
            current_line = test_line
        else:
            # 超出宽度，保存当前行并换行
            all_lines.append(current_line)
            current_line = char

    # 3. 保存最后一行未完成的文字
    if current_line:
        all_lines.append(current_line)

    # 4. 计算文字整体垂直居中位置
    total_text_height = len(all_lines) * line_height  # 文字总高度
    # 垂直居中：空白区域中间位置 - 文字总高度的一半
    vertical_offset = start_y + (blank_height - total_text_height) // 2
    # 防止文字超出空白区域，限制最小起始位置
    current_y = max(vertical_offset, start_y + TEXT_PADDING)

    # 5. 绘制所有行文字
    for line in all_lines:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]
        # 水平居中计算
        draw_x = (image_width - line_width) // 2
        # 绘制当前行
        draw.text((draw_x, current_y), line, fill=text_color, font=font)
        # 更新下一行y坐标
        current_y += line_height

    # 6. 警告：若文字总高度超出空白区域
    if total_text_height > (blank_height - 2 * TEXT_PADDING):
        print(f"警告：文字内容过长，超出空白区域高度！建议增大 PER_IMAGE_BLANK_HEIGHT 或减小 TEXT_SIZE")

def process_single_image(image_path, scene_text, blank_height):
    """
    处理单张图片：添加下方空白区域，并绘制对应场景文字
    :param image_path: 原始图片路径
    :param scene_text: 场景描述文字
    :param blank_height: 下方空白高度
    :return: 处理后的Image对象
    """
    try:
        # 打开原始图片，转为RGBA格式
        orig_img = Image.open(image_path).convert("RGBA")
        orig_width, orig_height = orig_img.size
    except FileNotFoundError:
        raise Exception(f"图片文件未找到：{image_path}")

    # 1. 创建新图片
    new_height = orig_height + blank_height
    new_img = Image.new("RGBA", (orig_width, new_height), FINAL_IMAGE_BACKGROUND)
    # 2. 粘贴原始图片到新图片顶部
    new_img.paste(orig_img, (0, 0), orig_img if orig_img.mode == "RGBA" else None)

    # 3. 绘制场景文字到空白区域
    draw = ImageDraw.Draw(new_img)
    try:
        # 加载中文字体
        font = ImageFont.truetype(FONT_PATH, TEXT_SIZE)
    except IOError:
        # 若指定字体不存在，使用默认字体
        print(f"警告：未找到指定字体 {FONT_PATH}，使用默认字体，可能出现中文乱码")
        font = ImageFont.load_default(size=TEXT_SIZE)
    
    # 文字绘制参数
    max_text_width = orig_width - 2 * TEXT_PADDING  # 文字最大宽度
    blank_area_start_y = orig_height  # 空白区域的起始y坐标
    
    # 调用优化版自动换行函数
    draw_wrapped_text(
        draw=draw,
        text=scene_text,
        font=font,
        max_width=max_text_width,
        start_y=blank_area_start_y,
        image_width=orig_width,
        text_color=TEXT_COLOR,
        blank_height=blank_height
    )

    return new_img.convert("RGB")  # 转为RGB格式，方便后续合成

def collage_final_image(processed_images, row_count, img_spacing):
    """
    排版合成最终图片：一行2张，共4行
    :param processed_images: 处理后的图片列表（按场景编号排序）
    :param row_count: 每行图片数量
    :param img_spacing: 图片间距
    :return: 最终合成的Image对象
    """
    if not processed_images:
        raise Exception("无处理后的图片可供合成")
    
    # 获取单张处理后图片的尺寸（假设所有图片尺寸一致）
    single_width, single_height = processed_images[0].size
    total_images = len(processed_images)
    total_rows = (total_images + row_count - 1) // row_count  # 计算总行数（这里固定为4行）

    # 计算最终大图的尺寸
    final_width = row_count * single_width + (row_count + 1) * img_spacing
    final_height = total_rows * single_height + (total_rows + 1) * img_spacing

    # 创建最终大图画布
    final_img = Image.new("RGB", (final_width, final_height), FINAL_IMAGE_BACKGROUND)

    # 依次粘贴每张处理后的图片
    for idx, img in enumerate(processed_images):
        # 计算当前图片的行列索引
        row_idx = idx // row_count
        col_idx = idx % row_count

        # 计算当前图片的粘贴坐标
        paste_x = img_spacing + col_idx * (single_width + img_spacing)
        paste_y = img_spacing + row_idx * (single_height + img_spacing)

        # 粘贴图片到最终画布
        final_img.paste(img, (paste_x, paste_y))

    return final_img

def main():
    try:
        # 1. 读取JSON场景数据
        scene_dict = load_comic_scenes(JSON_FILE_PATH)
        #print("✅ JSON文件读取成功，获取到{}个场景".format(len(scene_dict)))

        # 2. 处理每张图片（按场景编号1-8排序）
        processed_images = []
        for scene_num in range(1, 9):  # 遍历1-8场景
            image_path = f"./{BASE_ROOT}/{IMAGE_PREFIX}{scene_num}.{IMAGE_FORMAT}"
            scene_text = scene_dict.get(scene_num, f"场景{scene_num}：无描述内容")
            
            #print(f"🔧 正在处理图片：{image_path}")
            processed_img = process_single_image(
                image_path=image_path,
                scene_text=scene_text,
                blank_height=PER_IMAGE_BLANK_HEIGHT
            )
            processed_images.append(processed_img)

        # 3. 排版合成最终图片
        print("🎨 正在合成最终大图...")
        final_image = collage_final_image(
            processed_images=processed_images,
            row_count=ROW_IMG_COUNT,
            img_spacing=IMG_SPACING
        )

        # 4. 保存最终图片
        final_image.save(OUTPUT_IMAGE_PATH, quality=95)
        print(f"[IMAGE] 漫画生成成功|{OUTPUT_IMAGE_PATH}")

        print(f"🎉 任务完成！最终图片已保存至：{OUTPUT_IMAGE_PATH}")

    except Exception as e:
        print(f"❌ 程序运行出错：{e}")

if __name__ == "__main__":
    main()