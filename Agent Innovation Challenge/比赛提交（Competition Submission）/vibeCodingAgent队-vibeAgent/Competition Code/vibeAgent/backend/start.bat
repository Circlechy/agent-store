@echo off
chcp 65001 >nul 2>&1
REM Backend V3 Windows 启动脚本

echo ========================================
echo Backend V3 启动脚本
echo ========================================

REM 检查虚拟环境是否存在（优先 conda，其次 venv）
if not "%CONDA_DEFAULT_ENV%"=="" (
    echo 使用 Conda 环境: %CONDA_DEFAULT_ENV%
) else if exist "venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
) else (
    echo 警告: 未找到虚拟环境（venv 或 conda），使用系统 Python
)

REM 加载 .env 文件（如果存在）
if exist ".env" (
    echo 发现 .env 文件，将加载环境变量
) else (
    echo 警告: 未找到 .env 文件，请复制 .env.example 为 .env 并配置
    pause
    exit /b 1
)

REM 设置默认端口
if "%PORT%"=="" set PORT=8000

REM 启动服务
echo.
echo 正在启动服务...
echo 端口: %PORT%
echo API 文档: http://localhost:%PORT%/docs
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --reload

pause
