import json
from aigc_image_generator import call_aigc_draws,parse_stream_data,save_image_from_url,local_image_to_base64,call_ark_seedream_draws
from flask_web_agent import print_to_queue
import urllib3  

# 屏蔽 SSL 不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_comic_style(comic_style: str = None) -> str:
    """
    获取漫画风格，无输入时触发用户交互询问
    :param comic_style: 用户预先传入的漫画风格（可为None）
    :return: 确认后的有效漫画风格
    """
    if not comic_style or comic_style.strip() == "":
        while True:
            print("请指定漫画画风（如热血风、Q版卡通、宫崎骏风格、暗黑悬疑风等）：",flush=True)
            user_input = input("").strip()

            if user_input:
                return user_input
            print("风格不能为空，请重新输入！")
    else:
        return comic_style.strip()

API_KEY = "8888"


def read_comic_json_files(overview_file_path, detail_file_path):
    """
    读取漫画场景概述和详述的JSON文件
    :param overview_file_path: 场景概述JSON文件路径
    :param detail_file_path: 场景详述JSON文件路径
    :return: 场景概述列表、场景详述列表
    """

    try:
        with open(overview_file_path, 'r', encoding='utf-8') as f_overview:
            overview_data = json.load(f_overview)
            # 提取scene_list，默认返回空列表防止键不存在
            scene_overview_list = overview_data.get("scene_list", [])
    except FileNotFoundError:
        raise FileNotFoundError(f"场景概述文件 {overview_file_path} 未找到，请检查文件路径")
    except json.JSONDecodeError:
        raise ValueError(f"场景概述文件 {overview_file_path} 格式错误，不是合法的JSON")
    except Exception as e:
        raise Exception(f"读取场景概述文件失败：{str(e)}")
    
    # 读取场景详述JSON
    try:
        with open(detail_file_path, 'r', encoding='utf-8') as f_detail:
            # 场景详述本身是一个JSON数组
            scene_detail_list = json.load(f_detail)
    except FileNotFoundError:
        raise FileNotFoundError(f"场景详述文件 {detail_file_path} 未找到，请检查文件路径")
    except json.JSONDecodeError:
        raise ValueError(f"场景详述文件 {detail_file_path} 格式错误，不是合法的JSON")
    except Exception as e:
        raise Exception(f"读取场景详述文件失败：{str(e)}")
    
    return scene_overview_list, scene_detail_list

def loop_comic_scenes_test(overview_file, detail_file,comic_style):
    """
    循环遍历每个场景的概述和详述
    :param overview_file: 场景概述JSON文件路径
    :param detail_file: 场景详述JSON文件路径
    """
    # 先读取两个JSON文件，获取对应的列表
    scene_overviews, scene_details = read_comic_json_files(overview_file, detail_file)
    
    # 校验两个列表长度是否一致
    if len(scene_overviews) != len(scene_details):
        print(f"警告：场景概述数量（{len(scene_overviews)}）与场景详述数量（{len(scene_details)}）不一致，将以较短列表为准进行遍历")
    
    # 核心：单个for循环同时获取场景概述和详述
    last_content = "无"
    last_pic = None

    for index, (scene_overview, scene_detail) in enumerate(zip(scene_overviews, scene_details), start=1):
        
        # print("="*50)
        # print(scene_overview['scene_num'])
        # print("-"*50)
        # print(scene_overview['scene_content'])
        # print("-"*50)
        # print(scene_detail)
        

        scene_detail_str = json.dumps(
            scene_detail,
            ensure_ascii=False,  
            indent=2  
        )
        prompt = f"""
        参考传入的上一张漫画图片【绘画风格：{comic_style}】【画面内容：{last_content}】，保持画面的角色形象、线条风格、色彩调性完全一致；创作下一张漫画内容：{scene_overview['scene_content']}。要求：1. 分镜衔接自然，镜头视角与前作匹配（可标注：同视角/近景切换/全景拉远）；2. 角色表情、动作符合剧情逻辑，细节刻画清晰；3. 漫画线条干净利落，无多余噪点，符合印刷级画质标准
        """
        last_content = scene_overview['scene_content'] 
        
        print_to_queue("[LOADING]") 
        urls_param = []
        if last_pic and isinstance(last_pic, str):  
            urls_param = [last_pic]  
        
        '''responce = call_ark_seedream_draws(
            prompt = prompt,
            api_key = API_KEY,
            image=last_pic
        )'''
        responce = call_aigc_draws(
            prompt = prompt,
            api_key = API_KEY,
            urls=urls_param,
            aspect_ratio="1:1"
        )

        result = parse_stream_data(responce)

        
        image_url = "未知"
        images_list = result.get("images", [])
        if images_list:
            first_image = images_list[0]
            image_url = first_image.get("image_url", "未知").strip()
            if not image_url.startswith(("http://", "https://")):
                image_url = "未知"

        save_path = f"./test/{scene_overview['scene_num']}.png"
        if image_url != "未知":
            result2 = save_image_from_url(image_url, save_path=save_path)
        else:
            result2 = {"success": False, "save_path": None, "error_msg": "未获取到有效图片URL"}
        

        img_base64, convert_error = local_image_to_base64(f"{save_path}")
        

        if convert_error:
            print(f"图片转换Base64失败：{convert_error}")
            last_pic = None 
        else:
            last_pic = img_base64  
        

def loop_comic_scenes(overview_file, detail_file,comic_style,modify_requirement):
    """
    循环遍历每个场景的概述和详述
    :param overview_file: 场景概述JSON文件路径
    :param detail_file: 场景详述JSON文件路径
    """
    # 先读取两个JSON文件，获取对应的列表
    scene_overviews, scene_details = read_comic_json_files(overview_file, detail_file)
    
    # 校验两个列表长度是否一致
    if len(scene_overviews) != len(scene_details):
        print(f"警告：场景概述数量（{len(scene_overviews)}）与场景详述数量（{len(scene_details)}）不一致，将以较短列表为准进行遍历")
    
    # 核心：单个for循环同时获取场景概述和详述
    last_content = "无"
    last_pic = None
    last_pic_url = None
    for index, (scene_overview, scene_detail) in enumerate(zip(scene_overviews, scene_details), start=1):
        
        
        # 将scene_detail字典转换为带缩进的规整字符串，避免格式错乱
        scene_detail_str = json.dumps(
            scene_detail,
            ensure_ascii=False,  
            indent=2 
        )
        prompt = f"""
        参考传入的上一张漫画图片【绘画风格：{comic_style}】【画面内容：{last_content}】，保持画面的角色形象、线条风格、色彩调性完全一致；创作下一张漫画内容：{scene_overview['scene_content']}。{modify_requirement}要求：1. 分镜衔接自然，镜头视角与前作匹配（可标注：同视角/近景切换/全景拉远）；2. 角色表情、动作符合剧情逻辑，细节刻画清晰；3. 漫画线条干净利落，无多余噪点，符合印刷级画质标准
        """
        last_content = scene_overview['scene_content'] 
        
        print_to_queue("[LOADING]") 

        urls_param = []
        if last_pic and isinstance(last_pic, str):  
            urls_param = [last_pic]  
        
        responce = call_ark_seedream_draws(
            prompt = prompt,
            api_key = API_KEY,
            image=last_pic_url
        )

        
        result = responce

        image_url = "未知"
        images_list = result.get("images", [])
        if images_list:
            first_image = images_list[0]
            image_url = first_image.get("image_url", "未知").strip()
            if not image_url.startswith(("http://", "https://")):
                image_url = "未知"
        last_pic_url = image_url
        save_path = f"./test/{scene_overview['scene_num']}.png"
        if image_url != "未知":
            result2 = save_image_from_url(image_url, save_path=save_path)

            if result2["success"]:

                print(f"[IMAGE] 第{index}张生成成功|{result2['save_path']}")
            else:
                print(f"图片保存失败：{result2['error_msg']}") 
        else:
            result2 = {"success": False, "save_path": None, "error_msg": "未获取到有效图片URL"}
        #print(result2)
        print("[LOADING_END]") 
        img_base64, convert_error = local_image_to_base64(f"{save_path}")

 
        if convert_error:
            print(f"图片转换Base64失败：{convert_error}")
            last_pic = None  
        else:
            last_pic = img_base64 

if __name__ == "__main__":
    # 定义两个JSON文件的路径
    COMIC_OVERVIEW_FILE = "./test/panel_plan.json"  
    COMIC_DETAIL_FILE = "./test/manga_panel_json_list.json"     
    

    try:
        global comic_style
        comic_style = get_comic_style()
        modify_requirement = ""
        while True:
            loop_comic_scenes(COMIC_OVERVIEW_FILE, COMIC_DETAIL_FILE,comic_style,modify_requirement)
            print("\n请确认漫画是否满意？(输入 确认/修改:修改内容)：",flush=True)
            user_input = input()
            if user_input.startswith("确认"):
                break
            else:
                modify_requirement = user_input.replace("修改:", "【修改意见】").strip()

    except Exception as e:
        print(f"程序运行失败：{str(e)}")