![1400f2b1-bcfb-46e8-89e4-364e8661ea5b.png](https://raw.gitcode.com/user-images/assets/8923380/a8994cb5-c67f-4699-a29f-155fd044fa83/1400f2b1-bcfb-46e8-89e4-364e8661ea5b.png '1400f2b1-bcfb-46e8-89e4-364e8661ea5b.png')
# 我们的Agent独立完成了一次头部颅脑MRI扫描

进行一次核磁共振(MRI)扫描对放射技师和受检人员都不是什么轻松的事。

一般而言，对于一个特定的检查区域，放射技师需要进行若干个扫描序列。在每个扫描序列中技师需要启动MRI扫描，等待MRI扫描结果，然后基于结果去进行图片的对齐、裁切和其他参数调整，最后再决定是否开始或者调整下一个扫描序列。在完成对应扫描序列后，拼接成一个3D的MRI建模，供放射科医生进行下一步诊断。

尽管这些操作相对重复、枯燥，一名出色的放射科技师同样需要以年记的时间来培养。单是MRI就有三十到四十个不同检查区域和项目。一位放射技师可能还要同时掌握CT/MRI/超声等多种检测手段，每个检测方法对应还有不同软硬件医用设备供应商的操作方法。

现有一些新的工作把需要的相关调参知识用AI模型/多模态大模型凝练出来[1]，但要完全自动化相关的操作还面临一个关键问题：**模型无法直接操作为人类放射技师设计的仪器**。

我们的项目便是针对这个问题，通过openjiuwen框架，赋能已有的医学多模态MRI模型，使得通MRI的检测能够完全一键执行。**其中Computer Use能力由我们在Tool赛道开发的AutoCursor工具支撑。医学多模态模型由复旦医学院青年研究员王烁博士团队提供。**

目前，**我们的Agent已经能够完整完成一次往往要放射技师耗时10多分钟的头部颅脑MRI检测**，未来我们计划与复旦医学院AIMMM团队共建更强大的医用检测设备自动化Agent，为患者解忧，为医者纾困。

[Demo请点击此处查看](https://gitcode.com/Oliver_Qiang/AutoCursor/blob/main/demo/CT_scan_demo.mp4)

[1]The state-of-the-art in cardiac MRI reconstruction: Results of the CMRxRecon challenge in MICCAI 2023

-------------------

### AutoCursor可用工具集

|工具名称|描述|关键参数|
|--|--|--|
|`screenshot`|获取屏幕图像|x, y, w, h, full|
|`getPosition`|获取当前鼠标位置|无|
|`moveTo`|移动鼠标到指定位置|x, y|
|`click`|单击鼠标|x, y, button|
|`doubleClick`|双击鼠标|x, y, button|
|`dragTo`|鼠标拖拽|x, y|
|`write`|键入文本|text|
|`scroll`|滚轮操作|len|
|`pressEnter`|按下回车键|无|

## 📦 安装指导
### 环境要求
- **Python版本**：Python 3.11.4
- **屏幕分辨率**：1920×1080（支持自适应，但以该分辨率为基准）

### 依赖安装
1. 克隆项目仓库
```
git clone https://gitcode.com/Oliver_Qiang/AutoCursor.git
cd AutoCursor
```
2. 创建虚拟环境（推荐）
```
conda create -n AutoCursor python==3.11.4
conda activate AutoCursor
```
3. 安装核心依赖
```
pip install -r requirements.txt
```

### 配置设置
1. **环境变量配置**  
	创建 .env 文件并配置以下变量：
    ```
    API_KEY= "your-api-key"
    DATABASE_URL= "https://your-database-url"
    # 此文件已加入.gitignore 不会随git提交
    ```
2. **模型配置**  
    确保已配置支持视觉理解的LLM模型（如Qwen-VL系列）

### 快速开始
1. **启动程序**  
`python ./core/autoCursorCT.py`
2. **切换到目标应用**  
    程序启动后将有5秒时间切换到目标应用窗口
3. **执行自动化操作**   

