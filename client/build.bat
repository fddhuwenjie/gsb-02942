@echo off
chcp 65001 >nul
echo ================================================
echo 远程关机客户端打包工具
echo ================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install -r requirements.txt -q

REM 执行打包
echo [2/3] 开始打包...
python build.py

echo.
echo [3/3] 完成!
echo.
pause
