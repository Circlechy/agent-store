import asyncio
import os
from typing import Dict, List, Union
from openjiuwen.core.utils.llm.model_utils.model_factory import ModelFactory
from openjiuwen.core.utils.prompt.template.template import Template
from openjiuwen.core.utils.llm.messages import SystemMessage, HumanMessage
import json
import re
from flask_web_agent import print_to_queue
# ===================== 1. 全局配置=====================
os.environ["LLM_SSL_VERIFY"] = "false"
API_BASE = "https://api-inference.modelscope.cn/v1"
API_KEY  = "sk-1234"
#MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"
MODEL_NAME = "openai/gpt-oss-20b"
MODEL_PROVIDER = "openai"
MAX_PANEL_NUM = 8  # 分镜数上限，可调整
# ===================== 2. 核心提示词模板定义 =====================
def get_curl_headers():
    return {
        "User-Agent": "curl/7.88.1",
        "Content-Type": "application/json",
        "Accept": "*/*"
    }


def format_to_natural_text(theme_elements):
    """
    将 theme_elements（JSON字符串/字典）转为大模型风格的自然段落，无JSON格式符号
    """

    if isinstance(theme_elements, str):
        try:
            theme_elements = json.loads(theme_elements)
        except json.JSONDecodeError as e:
            return f"格式解析失败：{str(e)}"
    if not isinstance(theme_elements, dict):
        return "输入数据格式错误，不是有效字典或JSON字符串"
    # 1. 定义英文键到中文描述的映射
    key_mapping = {
        "subject": "漫画主题",
        "tone": "整体基调",
        "core_conflict": "核心冲突",
        "target_audience": "目标受众",
        "core_prototype": "核心人物原型",
        "core_spirit": "核心创作精神"
    }

    # 2. 拼接基础信息段落
    basic_info = []
    for key, desc in key_mapping.items():
        if key in theme_elements:
            basic_info.append(f"{desc}：{theme_elements[key]}")
    
    # 3. 处理关键场景
    key_scenes = theme_elements.get("key_scenes", [])
    scenes_text = "\n".join([f"  {idx+1}. {scene}" for idx, scene in enumerate(key_scenes)])
    
    # 4. 处理漫画风格
    manga_style = theme_elements.get("manga_style", "无指定风格")

    # 5. 拼接最终自然文本
    natural_text = f"""本次漫画创作的主题核心要素如下：
{'、'.join(basic_info)}

关键创作场景（按剧情逻辑排序）：
{scenes_text}

漫画风格要求：{manga_style}"""
    return natural_text


def get_comic_style(comic_style: str = None) -> str:
    """
    获取漫画风格，无输入时触发用户交互询问
    :param comic_style: 用户预先传入的漫画风格（可为None）
    :return: 确认后的有效漫画风格
    """
    # 若用户无传入/传入为空，触发交互
    if not comic_style or comic_style.strip() == "":
        while True:

            user_input = input("请指定漫画剧情风格（如热血风、Q版卡通、宫崎骏风格、暗黑悬疑风等）：").strip()
            # 简单校验，避免用户输入空值
            if user_input:
                return user_input
            print("风格不能为空，请重新输入！")
    # 若用户已有传入，直接返回处理后的结果
    else:
        return comic_style.strip()




THEME_PROCESS_TEMPLATE = Template(
    content=[
        {"role": "system", "content": """
你是专业的漫画分镜主题分析师，擅长根据指定风格提取适配分镜表现的核心要素。
输出要求：
1.  格式：标准JSON，无额外冗余解释；
2.  核心字段（必选）：subject、tone、core_conflict、target_audience、core_prototype、core_spirit、key_scenes(≤{{max_scene_num}})、manga_style；
3.  风格强绑定要求：
    - manga_style字段需详细描述{{comic_style}}的视觉特征（如热血风=粗犷线条+高对比度+速度线；Q版卡通=圆润线条+夸张比例+明亮色调；宫崎骏风格=细腻笔触+自然光影+治愈氛围）；
    - key_scenes需优先选择适合{{comic_style}}视觉表现的场景（如Q版卡通优先选萌趣互动场景，宫崎骏风格优先选自然场景）；
    - core_conflict的视觉化方案需贴合{{comic_style}}的叙事特点（如暗黑悬疑风用阴影/特写表现冲突，治愈风用细节互动表现冲突）。
"""},
        {"role": "user", "content": "请分析以下漫画主题，提取上述核心要素。主题：{{theme}}；核心场景上限：{{max_scene_num}}；漫画风格：{{comic_style}}。"}
    ]
)


OUTLINE_GENERATE_TEMPLATE = Template(
    content=[
        {"role": "system", "content": """
你是资深漫画编剧，擅长根据指定风格生成适配分镜的剧本大纲。
要求：
1.  分幕方式：推荐3幕结构，全剧分镜总数≤{{max_panel_num}}，标注每幕分镜数；
2.  场景适配性要求：每个场景标注「分镜适配性」，且必须贴合{{comic_style}}的视觉语言：
    - 例1（热血风）：战斗场面/低角度特写/速度线全景；
    - 例2（Q版卡通）：萌趣互动特写/夸张表情大面板/群像小格子；
    - 例3（宫崎骏风格）：自然远景/角色手部细节特写/光影渐变中景；
3.  调性约束：突出{{comic_style}}对应的核心亮点（热血风=燃点/反转；Q版=萌点/笑点；宫崎骏风格=治愈点/细节共鸣）；
4.  严格围绕主题核心要素，场景视觉冲击力需匹配风格特征。
"""},
        {"role": "user", "content": "基于以下核心要素生成分镜适配漫画大纲。核心要素：{{theme_elements}}；分镜上限：{{max_panel_num}}；漫画风格：{{comic_style}}。"}
    ]
)


SCRIPT_WRITE_TEMPLATE = Template(
    content=[
        {"role": "system", "content": """
你是专业漫画分镜脚本撰写师，擅长根据指定风格撰写适配分镜绘制的脚本。
格式：【分镜序号】+【场景（镜头类型）】+【角色动作（视觉化描述）】+【台词/音效（风格匹配）】
风格强约束：
1.  镜头类型：必须符合{{comic_style}}的常用镜头；
2.  台词风格：贴合{{comic_style}}的叙事语气、；
3.  音效拟声词：匹配{{comic_style}}的呈现习惯、；
4.  分镜总数≤{{max_panel_num}}，每个分镜内容独立且有核心看点。
"""},
        {"role": "user", "content": "基于以下大纲撰写分镜脚本。大纲：{{confirmed_outline}}；分镜上限：{{max_panel_num}}；漫画风格：{{comic_style}}。"}
    ]
)


PANEL_PLAN_TEMPLATE = Template(
    content=[
        {"role": "system", "content": """
你是专业漫画场景信息提取与格式转换助手，仅负责从文本中提取已有场景内容进行结构化处理，不新增任何原文未提及内容、不修改原文语义、不进行任何提炼拆分或扩写。
要求：
1.  从输入的漫画大纲中提取所有场景，场景总数≤{{max_panel_num}}，编号按原文"Scene X"顺序排列（1-{{max_panel_num}}），无遗漏、不跳号、不重复；
2.  每张场景仅需完整复制原文对应场景的全部内容，不拆分任何细节、不提炼任何字段，原样保留原文的表述、标点、特殊符号（如"咚咚咚""BOOM！"）；
3.  优先级规则：严格完整保留原文场景的所有内容，优先满足{{comic_style}}对应的场景原文完整提取需求，不做任何加工处理；
4.  JSON固定结构（严格遵循语法合法，括号匹配、引号正确，分镜列表按编号升序排列，仅输出JSON数据，无其他解释性文字）：
{
    "comic_style": "{{comic_style}}",
    "total_scenes": 实际场景数量（整数，≤{{max_panel_num}}）,
    "scene_list": [
        {
            "scene_num": 1,
            "scene_content": "完整复制原文中第1场景的全部内容，不做任何修改",
            "scene_text": 用一简洁的一句话讲述原文中第1场景的故事，用于漫画旁白
        },
        {
            "scene_num": 2,
            "scene_content": "完整复制原文中第2场景的全部内容，不做任何修改",
            "scene_text": 用一简洁的一句话讲述原文中第2场景的故事，用于漫画旁白
        }
        ...  // 以此类推，继续生成第3场景、第4场景……直至第N场景（N=total_scenes，≤{{max_panel_num}}）
    ]
}
"""},
        {"role": "user", "content": "基于以下漫画大纲提取场景信息并转换为标准JSON格式。漫画大纲：{{manga_script}}；场景上限：{{max_panel_num}}；漫画风格：{{comic_style}}。"}
    ]
)


PANEL_GENERATE_TEMPLATE = Template(
    content=[
        {"role": "system", "content": """

你是专业文生图漫画分镜细化助手，核心职责是将输入的单条分镜描述，丰富故事、配上必要的对话，精准拆解、填充至指定JSON格式，全程紧扣{{comic_style}}风格基调，严格遵循“输入内容为唯一依据、字段无模糊表述、细节可落地、不新增原文无提及元素”原则，确保输出适配文生图模型需求。
一、核心要求

1. 字段完整性：所有JSON字段必须填充，无空值、无“此处填写”等占位表述，内容完全源于输入分镜描述，贴合{{comic_style}}专属特征。

2. 表述精准性：每个字段描述具体可落地（如构图、道具、字体、光影需明确），杜绝笼统词汇，严格匹配当前分镜剧情，不偏离输入核心信息。

3. 风格统一性：全程围绕{{comic_style}}展开，所有视觉元素、色调、排版、造型均需适配该风格，负面指令严格执行，杜绝风格混搭或偏离。

二、JSON字段填充规则（逐字段对应输入内容）

画面内容： 
         
对话和文本：提取输入中的音效、台词类元素，标注具体排版位置（如太阳头顶、画面角落）、字体样式以及谁说的，仅保留输入提及内容，无冗余文本。


三、输出要求

- 仅输出符合规则的JSON数据，无任何解释性文字、备注、格式说明，确保语法合法（括号匹配、引号正确）。

- 所有内容不超出输入分镜描述范围，不新增原文无提及的角色、道具、特效、文本等元素。
         
"""
},
        {"role": "user", "content": "{{panel_content}}"}
    ]
)


def get_comic_style(comic_style: str = None) -> str:
    """
    获取漫画风格，无输入时触发用户交互询问
    :param comic_style: 用户预先传入的漫画风格（可为None）
    :return: 确认后的有效漫画风格
    """
    # 若用户无传入/传入为空，触发交互
    if not comic_style or comic_style.strip() == "":
        while True:
            print("请指定漫画剧情风格（如热血风、Q版卡通、宫崎骏风格、暗黑悬疑风等）：",flush=True)
            user_input = input().strip()
            if user_input:
                return user_input
            print("风格不能为空，请重新输入！")
    else:
        return comic_style.strip()
    
# ===================== 3. 改造后的ScriptCreationAgent =====================
class ScriptCreationAgent:
    def __init__(self):
        self.model = self._init_model()
        self.comic_style = None
        self.user_theme = None
        self.theme_elements = None
        self.confirmed_outline = None
        self.manga_script = None
        self.panel_plan = None
        self.panel_json_list = []
    def _init_model(self):
        factory = ModelFactory()
        model = factory.get_model(
            model_provider=MODEL_PROVIDER,
            api_base=API_BASE,
            api_key=API_KEY
        )
        return model

    def _format_messages(self, template: Template, fill_data: Dict) -> List[Dict]:
        return template.format(fill_data).to_messages()

    def process_theme(self, theme: str) -> str:
        # 完善 fill_data，传入模板所需的所有参数
        fill_data = {
            "theme": theme,
            "comic_style": self.comic_style,  # 传入漫画风格（已通过 get_comic_style 获取）
            "max_scene_num": MAX_PANEL_NUM  # 传入核心场景上限
        }
        messages = self._format_messages(THEME_PROCESS_TEMPLATE, fill_data)

        headers = get_curl_headers()
        response = self.model.invoke(
            model_name=MODEL_NAME, messages=messages, temperature=0.7, top_p=0.95
        )
        return response.content

    def generate_outline(self, theme_elements: str) -> str:
        # 完善 fill_data，传入模板所需的所有参数
        fill_data = {
            "theme_elements": theme_elements,
            "comic_style": self.comic_style,
            "max_panel_num": MAX_PANEL_NUM
        }
        messages = self._format_messages(OUTLINE_GENERATE_TEMPLATE, fill_data)
        response = self.model.invoke(
            model_name=MODEL_NAME, messages=messages, temperature=0.8, top_p=0.95
        )
        return response.content

    def confirm_outline(self, outline: str) -> str:
        print("\n===== AI生成的分镜适配大纲 =====")
        print(outline)
        while True:
            time.sleep(0.02)
            print("\n请确认大纲是否满意？(输入 确认/修改:修改内容)：",flush=True)
            user_input = input()
            if user_input.startswith("确认"):
                return outline
            elif user_input.startswith("修改"):
                modify_requirement = user_input.replace("修改:", "").strip()
                prompt = f"原大纲：{outline}\n修改需求：{modify_requirement}\n修改后分镜总数仍≤{MAX_PANEL_NUM}。"
                # 改为字典格式，与模板一致，避免依赖 SystemMessage/HumanMessage
                messages = [
                    {"role": "system", "content": "漫画大纲修改助手，确保分镜总数≤12。"},
                    {"role": "user", "content": prompt}
                ]
                new_outline = self.model.invoke(model_name=MODEL_NAME, messages=messages).content
                print("\n===== 修改后的大纲 =====")
                print(new_outline)
                return new_outline
            else:
                print("输入格式错误，请重新输入！")

    def write_script(self, confirmed_outline: str) -> str:
        # 完善 fill_data，传入模板所需的所有参数
        fill_data = {
            "confirmed_outline": confirmed_outline,
            "comic_style": self.comic_style,
            "max_panel_num": MAX_PANEL_NUM
        }
        messages = self._format_messages(SCRIPT_WRITE_TEMPLATE, fill_data)
        response = self.model.invoke(
            model_name=MODEL_NAME, messages=messages, temperature=0.6, top_p=0.95
        )
        return response.content

    # 分镜规划方法
    def plan_manga_panels(self, manga_script: str) -> str:
        
        # 完善 fill_data，传入模板所需的所有参数
        fill_data = {
            "manga_script": manga_script,
            "comic_style": self.comic_style,
            "max_panel_num": MAX_PANEL_NUM
        }
        messages = self._format_messages(PANEL_PLAN_TEMPLATE, fill_data)
        response = self.model.invoke(
            model_name=MODEL_NAME, messages=messages, temperature=0.7, top_p=0.95
        )

        return response.content

    # 改造：详细分镜生成方法
    def generate_manga_panels(self, panel_plan_dict: dict) -> List[str]:
        
        panel_str_list =[]
        
        for i,panel_plan in enumerate(panel_plan_dict['scene_list'] ):
            time.sleep(0.03)
            print(f"正在生成第{i+1}张分镜...")
            # 完善 fill_data，传入模板所需的所有参数
            panel_content = panel_plan['scene_content']

            messages = self._format_messages(
                PANEL_GENERATE_TEMPLATE,
                fill_data = {
                "panel_content": panel_content,
                "comic_style": self.comic_style,
                "max_panel_num": MAX_PANEL_NUM
                }
            )
            
            panel_detail = self.model.invoke(
                model_name=MODEL_NAME, messages=messages, temperature=0.7, top_p=0.95
            ).content
   

            panel_dict = None
            # 第一步：尝试修复非标准JSON
            cleaned_detail = re.sub(r'\n\s*', ' ', panel_detail.strip())  # 去除多余换行和空格
            cleaned_detail = re.sub(r'([{,:\[])\s*([^:\]}]+?)\s*([},:\]])', r'\1"\2"\3', cleaned_detail)  # 补全缺失的引号

            try:
                # 尝试解析修复后的内容为字典
                panel_dict = json.loads(cleaned_detail)
            except (json.JSONDecodeError, TypeError) as e:
                # 解析失败，再尝试直接解析原始内容
                try:
                    panel_dict = json.loads(panel_detail)
                except (json.JSONDecodeError, TypeError):
                    # 确认无法解析，保留原始字符串
                    panel_dict = panel_detail

            # 第二步：根据类型针对性格式化输出
            if isinstance(panel_dict, (dict, list)):
                # 是字典/列表，正常格式化
                print(json.dumps(panel_dict, indent=2, ensure_ascii=False, sort_keys=False))
            else:
                # 仍是字符串，直接打印
                print(panel_dict)


            try:
                panel_json = json.loads(panel_detail)
                self.panel_json_list.append(panel_json)
            except json.JSONDecodeError as e:
                print(f"警告：第{i}张分镜JSON格式解析失败，错误信息：{e}")
                # 填充空JSON，保证列表长度完整
                self.panel_json_list.append({"分镜序号": i, "解析失败": True, "原始内容": panel_detail})
            
            panel_str_list.append(panel_detail)
        
        return panel_str_list

    def save_panel_json_list_to_json(self, file_name: str = "./test/manga_panel_json_list.json"):
        """
        将分镜JSON列表格式化写入txt文件
        :param file_name: 输出文件名
        """
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(
                    self.panel_json_list,
                    f,  # 传入文件对象
                    ensure_ascii=False,
                    indent=4,
                    sort_keys=False
                )
            print(f"\n分镜JSON列表已成功写入 {file_name} 文件！")
            print(f"JSON列表长度：{len(self.panel_json_list)} 张分镜（符合8张要求）")
        except Exception as e:
            print(f"错误：分镜JSON列表写入失败，错误信息：{e}")

    def integrate_data(self, theme: str, outline: str, panel_plan: str, panel_list: List[str]) -> str:
        final_work = f"""
# 漫画分镜创作最终作品（分镜总数：{len(panel_list)}张）
## 一、核心主题
{theme}

## 二、分镜适配大纲
{outline}

## 三、分镜规划清单
{panel_plan}

## 四、详细分镜描述（共{len(panel_list)}张）
"""
        for i, panel in enumerate(panel_list, 1):
            final_work += f"\n### 第{i}张分镜\n{panel}\n"

        final_work += f"""
---
生成时间：漫画分镜创作Agent自动生成
分镜总数：{len(panel_list)}张（≤{MAX_PANEL_NUM}张）
"""
        return final_work

    # 完整工作流
    def run_workflow(self, user_theme: str):
        
        self.comic_style = get_comic_style()
        self.user_theme = user_theme.strip()
       
        print("===== 漫画剧本创作启动 =====")
        # 1. 主题处理
        print_to_queue("[LOADING]") 
        print(f"\n[1/5] 正在分析主题：{user_theme}")
        theme_elements = self.process_theme(user_theme)
        beautiful_theme = format_to_natural_text(theme_elements)
        print_to_queue("[LOADING_END]") 

        print(f"主题核心要素：{beautiful_theme}")

        # 2. 大纲生成
        print_to_queue("[LOADING]") 
        print("\n[2/5] 正在生成分镜适配大纲...")
        outline = self.generate_outline(theme_elements)
        print_to_queue("[LOADING_END]") 
        # 3. 大纲确认
        print_to_queue("[LOADING]") 
        print("\n[3/5] 等待用户确认大纲...")
        confirmed_outline = self.confirm_outline(outline)
        print_to_queue("[LOADING_END]") 

        print_to_queue("[LOADING]") 
        print(f"\n[4/5] 正在规划分镜清单（总数≤{MAX_PANEL_NUM}）...")
        panel_plan = self.plan_manga_panels(confirmed_outline)
        panel_plan_dict = json.loads(panel_plan)
        # 核心步骤：将 Python 字典写入 JSON 文件
        with open("./test/panel_plan.json", "w", encoding="utf-8") as f:
        
            json.dump(
                panel_plan_dict, 
                f,  
                ensure_ascii=False,  
                indent=4  
            )
        
        print(f"分镜规划完成：")
        for id in panel_plan_dict["scene_list"]:
            print(f"{id['scene_num']}.:{id['scene_content']}")
        print_to_queue("[LOADING_END]") 
        
        # 6. 详细分镜生成
        print_to_queue("[LOADING]") 
        print(f"\n[5/5] 正在生成详细分镜描述（共{MAX_PANEL_NUM}张）...")
        panel_list = self.generate_manga_panels(panel_plan_dict)
        print_to_queue("[LOADING_END]") 
        #7. 数据整合
        print("\n 正在整合最终分镜作品...")
        print_to_queue("[LOADING_END]") 

        final_work = self.integrate_data(
            user_theme, confirmed_outline, panel_plan, panel_list
        )
        
        # 输出+保存
        print("\n===== 漫画分镜创作完成！最终作品如下 =====")
        print(final_work)
        with open("manga_panel_creation_result.txt", "w", encoding="utf-8") as f:
            f.write(final_work)
        print(f"\n作品已保存到 manga_panel_creation_result.txt 文件！分镜总数：{len(panel_list)}张")
        print_to_queue("[LOADING_END]") 
        self.save_panel_json_list_to_json()
import time
# ===================== 4. 主函数入口 =====================
if __name__ == "__main__":
    print("请输入漫画创作主题（如：愚公移山改编漫画）：", flush=True)
    time.sleep(0.02)
    user_theme = input()  
    agent = ScriptCreationAgent()
    agent.run_workflow(user_theme)