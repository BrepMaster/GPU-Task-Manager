@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   GPU 任务管理器 - 打包脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/3] 开始打包 (onedir 模式)...
python -m PyInstaller build.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请检查上方日志。
    pause
    exit /b 1
)

echo [3/3] 打包完成！
echo.
echo 输出目录: dist\GPU任务管理器\
echo 双击 dist\GPU任务管理器\GPU任务管理器.exe 即可运行
echo.
pause
