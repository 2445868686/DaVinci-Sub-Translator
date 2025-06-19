@echo off
rem 设置代码页为 UTF-8，确保后续输出的字符正确显示
chcp 65001 >nul
setlocal

:: ============ 可根据需要修改 =============
set "PYTHON=python" :: 若 python 不在 PATH，请改绝对路径，例如 C:\Python311\python.exe
set "WHEEL_DIR=C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\HB\Translator\wheel"
set "TARGET_DIR=C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\HB\Translator\Lib"

:: 将所有需要安装的包放在一个变量里
:: 新增了 setuptools 和 wheel，它们是安装源代码包所必需的构建工具
set "PACKAGES=googletrans==4.0.0-rc1 requests setuptools wheel"

:: 指定使用的镜像源
set "PIP_MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple"
:: =========================================

echo [START] download & offline install : %PACKAGES%
echo ------------------------------------------------------------

:: 1. 创建目录（如果不存在）
echo [1/4] Checking and creating directories...
if not exist "%WHEEL_DIR%" mkdir "%WHEEL_DIR%"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

:: 2. 清理 pip 缓存（可选）
echo [2/4] Purging pip cache...
"%PYTHON%" -m pip cache purge --disable-pip-version-check >nul 2>&1

:: 3. 从镜像下载所有包及其依赖项
echo [3/4] Downloading all packages from mirror: %PACKAGES%
"%PYTHON%" -m pip download %PACKAGES% ^
--dest "%WHEEL_DIR%" ^
--no-cache-dir %PIP_MIRROR%
if errorlevel 1 (
echo [ERROR] Failed to download packages. Please check your network or the mirror.
pause & exit /b 1
)
echo Download complete. Wheels are in "%WHEEL_DIR%"

:: 4. 离线安装到目标目录
echo [4/4] Offline installing to "%TARGET_DIR%"...
"%PYTHON%" -m pip install %PACKAGES% ^
--no-index ^
--find-links "%WHEEL_DIR%" ^
--target "%TARGET_DIR%" ^
--upgrade ^
--disable-pip-version-check
if errorlevel 1 (
echo [ERROR] Offline install failed. Please check the logs above.
pause & exit /b 1
)

echo ------------------------------------------------------------
echo [SUCCESS] All packages installed successfully to "%TARGET_DIR%"
pause
endlocal