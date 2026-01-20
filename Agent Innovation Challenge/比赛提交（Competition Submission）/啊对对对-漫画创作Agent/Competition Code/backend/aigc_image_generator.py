import requests
import json
import os
import traceback
# 导入 Ark SDK 相关模块（需先安装：pip install 'volcengine-python-sdk[ark]'）
from volcenginesdkarkruntime import Ark
import base64
def call_aigc_draws(
    prompt,                 
    api_key,                 
    model="nano-banana-fast",
    aspect_ratio="auto",     
    image_size="1K",         
    urls=None,              
    web_hook="",             
    shut_progress=False,    
    api_url="https://grsai.dakka.com.cn/v1/draw/nano-banana",  
    stream=False             
):
    """
    封装nano banana绘图接口的调用函数，返回绘图接口响应结果
    :param prompt: 绘图提示词（必填）
    :param api_key: 平台申请的API Key（必填）
    :param model: 模型名称，默认nano-banana-fast
    :param aspect_ratio: 图像比例，默认auto
    :param image_size: 图像大小，默认1K
    :param urls: 参考图URL/Base64列表，默认空列表
    :param web_hook: 回调地址，默认空字符串
    :param shut_progress: 是否关闭进度回复，默认False
    :param api_url: API接口地址，默认国内直连地址
    :param stream: 是否启用流式响应，默认False
    :return: 包含响应结果的字典（含成功状态、数据、错误信息）
    """
    # 初始化返回结果
    result_dict = {
        "success": False,
        "status_code": None,
        "task_info": {},
        "images": [],
        "error_msg": ""
    }
    

    if urls is None:
        urls = []
    
    # 1. 构建请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"  # 格式：Bearer + 空格 + API Key
    }
    
    # 2. 构建请求体
    request_body = {
        "model": model,
        "prompt": prompt,
        "aspectRatio": aspect_ratio,
        "imageSize": image_size,
        "urls": urls,
        "webHook": web_hook,
        "shutProgress": shut_progress
    }
    
    try:
        # 3. 发送POST请求
        response = requests.post(
            url=api_url,
            headers=headers,
            json=request_body,
            stream=stream
        )
        
        # 记录响应状态码
        result_dict["status_code"] = response.status_code
        
        # 4. 处理正常响应（状态码200）
        if response.status_code == 200:
            try:
                # 解析JSON格式响应（非流式响应）
                response_data = response.json()
                
                # 更新返回结果的成功状态和核心数据
                result_dict["success"] = True
                result_dict["task_info"] = {
                    "task_id": response_data.get("id", "未知"),
                    "task_status": response_data.get("status", "未知"),
                    "task_progress": f"{response_data.get('progress', '未知')}%"
                }
                
                # 提取生成的图片信息（
                image_results = response_data.get("results", [])
                for idx, img_data in enumerate(image_results):
                    result_dict["images"].append({
                        "index": idx + 1,
                        "image_url": img_data.get("url", "未知"),
                        "image_note": img_data.get("content", "未知")
                    })
                
            except json.JSONDecodeError:
                # 处理流式响应
                stream_data = []
                for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                    if chunk:
                        stream_data.append(chunk)
                
                result_dict["success"] = True  # 流式响应状态码200即视为成功
                result_dict["task_info"]["stream_data"] = "".join(stream_data)
                result_dict["error_msg"] = "响应为流式数据，已完成分段读取"
        
        # 5. 处理异常响应
        else:
            result_dict["error_msg"] = f"接口调用失败，状态码：{response.status_code}，错误信息：{response.text}"
    
    except Exception as e:
        # 捕获请求过程中的异常
        result_dict["error_msg"] = f"请求发生异常：{str(e)}"
    
    # 6. 返回整理后的结果
    return result_dict


def call_ark_seedream_draws(
    prompt,                 
    api_key=None,           
    model="doubao-seedream-4-5-251128", 
    size="2K",              
    response_format="url",  
    watermark=False,        
    image="",               
    base_url="https://ark.cn-beijing.volces.com/api/v3"  
):
    """
    封装火山引擎 Ark 平台 doubao-seedream 绘图模型的调用函数，返回结构化绘图结果
    :param prompt: 绘图提示词（必填）
    :param api_key: Ark API Key（可选，未传入则自动读取环境变量ARK_API_KEY）
    :param model: 模型ID，默认doubao-seedream-4-5-251128
    :param size: 图像大小，默认2K（支持SDK支持的其他尺寸如1K、4K等）
    :param response_format: 响应格式，默认url（返回图片URL），可选b64_json（返回Base64编码）
    :param watermark: 是否添加水印，默认False
    :param image: 可选参考图，支持有效的图片URL或Base64编码字符串，默认空字符串（不使用参考图）
    :param base_url: 接口基础地址，默认北京区域地址
    :return: 包含响应结果的字典（含成功状态、数据、错误信息，与原函数格式对齐）
    """
    # 初始化返回结果
    result_dict = {
        "success": False,
        "status_code": None,  # Ark SDK封装了状态码，此处预留兼容，成功时填充为200
        "task_info": {},
        "images": [],
        "error_msg": ""
    }

    try:
        # 1. 处理 API Key
        ark_api_key = api_key or os.getenv('ARK_API_KEY')
        if not ark_api_key:
            result_dict["error_msg"] = "API Key 缺失：请传入api_key参数或配置ARK_API_KEY环境变量"
            return result_dict

        # 2. 初始化 Ark 客户端
        client = Ark(
            base_url=base_url,
            api_key=ark_api_key
        )

        # 3. 调用绘图接口，传入参数
        images_response = client.images.generate(
            model=model,
            prompt=prompt,
            image=image, 
            size=size,
            response_format=response_format,
            watermark=watermark
        )

        # 4. 处理成功响应，填充返回结果
        result_dict["success"] = True
        result_dict["status_code"] = 200  # SDK 调用成功默认返回200级响应
        result_dict["task_info"] = {
            "model": model,
            "response_format": response_format,
            "watermark": watermark,
            "size": size,
            "reference_image": image  
        }

        # 5. 提取图片数据
        if hasattr(images_response, 'data') and images_response.data:
            for idx, img_data in enumerate(images_response.data):
                image_info = {
                    "index": idx + 1,
                    "image_url": "未知",
                    "image_note": f"doubao-seedream 生成图片（尺寸：{size}）"
                }
                # 根据响应格式提取对应数据
                if response_format == "url":
                    image_info["image_url"] = getattr(img_data, 'url', '未知')
                elif response_format == "b64_json":
                    image_info["image_url"] = getattr(img_data, 'b64_json', '未知')
                    image_info["image_note"] += "（格式：Base64编码）"
                
                # 若使用了参考图，补充标注
                if image:
                    image_info["image_note"] += "（基于参考图生成）"
                
                result_dict["images"].append(image_info)

    except Exception as e:
        # 6. 捕获所有异常（SDK异常、环境变量异常等）
        result_dict["error_msg"] = f"请求发生异常：{str(e)}\n异常详情：{traceback.format_exc()}"

    # 7. 返回整理后的结构化结果
    return result_dict

# 下载图片函数
def save_image_from_url(
    image_url,
    save_path=None,
    verify_ssl=False,
    proxies=None
    #proxies={"https": "http://127.0.0.1:7890", "http": "http://127.0.0.1:7890"}
):
    result = {"success": False, "save_path": None, "error_msg": ""}
    if not image_url or not isinstance(image_url, str) or image_url == "未知":
        result["error_msg"] = "无效 URL"
        return result
    try:
        response = requests.get(
            image_url,
            verify=verify_ssl,
            timeout=30,
            proxies=proxies  # 启用代理
        )
        response.raise_for_status()
        if save_path is None:
            file_name = image_url.split("/")[-1].split("?")[0]
            save_path = f"./{file_name}"
        with open(save_path, "wb") as f:
            f.write(response.content)
        result["success"] = True
        result["save_path"] = save_path
    except Exception as e:
        result["error_msg"] = f"未知异常：{str(e)}"
    return result



def parse_stream_data(draw_result):
    """
    解析nano banana流式响应数据，提取图片URL和完整任务信息
    :param draw_result: call_nano_banana_draw 函数的返回结果
    :return: 整理后的字典（含任务信息、图片列表）
    """
    # 初始化解析结果
    parse_result = {
        "task_id": "未知",
        "task_status": "未知",
        "finish_time": 0,
        "images": []
    }
    
    # 校验传入数据是否有效
    if not draw_result["success"] or "stream_data" not in draw_result["task_info"]:
        print("无效的流式数据或调用失败，无法解析")
        return parse_result
    
    stream_data = draw_result["task_info"]["stream_data"]
    
    # 1. 分割流式数据，提取所有有效JSON片段
    data_chunks = stream_data.split("\n\ndata: ")
    for chunk in data_chunks:
        chunk = chunk.strip()  # 去除首尾空白字符
        if not chunk:
            continue  # 跳过空片段
        
        # 2. 解析单个JSON片段
        try:
            chunk_json = json.loads(chunk)
        except json.JSONDecodeError:
            continue 
        
        # 3. 更新任务基础信息
        parse_result["task_id"] = chunk_json.get("id", "未知")
        parse_result["task_status"] = chunk_json.get("status", "未知")
        parse_result["finish_time"] = chunk_json.get("end_time", 0)
        
        # 4. 提取图片信息
        if chunk_json.get("progress") == 100 and chunk_json.get("results"):
            results = chunk_json["results"]
            for idx, img_data in enumerate(results):
                parse_result["images"].append({
                    "index": idx + 1,
                    "image_url": img_data.get("url", "未知"),
                    "image_note": img_data.get("content", "无图注")
                })
    
    return parse_result


def local_image_to_base64(image_path):
    """
    将本地图片转换为接口可识别的Base64编码字符串（带数据头）
    :param image_path: 本地图片路径（如./test.png、C:/images/photo.jpg）
    :return: 成功返回Base64字符串，失败返回None和错误信息
    """
    # 1. 校验文件是否存在
    if not os.path.exists(image_path):
        return None, f"本地图片不存在：{image_path}"
    
    # 2. 获取图片格式（后缀），用于拼接Base64数据头
    image_suffix = os.path.splitext(image_path)[-1].lower().lstrip(".")
    supported_formats = ["png", "jpg", "jpeg", "bmp", "webp"]
    if image_suffix not in supported_formats:
        return None, f"不支持的图片格式：{image_suffix}，仅支持{supported_formats}"
    
    # 3. 读取图片二进制数据并进行Base64编码
    try:
        with open(image_path, "rb") as f:
            # 读取二进制数据
            image_binary = f.read()
            # 进行Base64编码（bytes→str）
            image_base64 = base64.b64encode(image_binary).decode("utf-8")
        
        # 4. 拼接Base64数据头（接口必须识别该格式，否则无法解析）
        # 格式：data:image/[格式];base64,[编码字符串]
        base64_with_header = f"data:image/{image_suffix};base64,{image_base64}"
        return base64_with_header, None
    
    except Exception as e:
        return None, f"图片转换失败：{str(e)}"