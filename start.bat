@echo off
cd /d "%~dp0"
echo ========================================
echo   微信小店售后增强 - 本地服务
echo ========================================
echo.

:: ---- 自动添加防火墙规则（需要管理员权限）----
echo [检查] 防火墙规则...
netsh advfirewall firewall show rule name="wxsx-helper-port-5000" >nul 2>&1
if %errorlevel% neq 0 (
    echo [添加] 正在添加防火墙规则（允许 5000 端口入站）...
    netsh advfirewall firewall add rule name="wxsx-helper-port-5000" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [警告] 自动添加防火墙规则失败！
        echo   可能原因：未以管理员身份运行此脚本
        echo   解决方法：右键此文件 →「以管理员身份运行」
        echo   或手动操作：见下方说明
        echo.
    ) else (
        echo [完成] 防火墙规则已添加
    )
) else (
    echo [已有] 防火墙规则已存在
)
echo.

:: ---- 显示本机局域网 IP ----
echo [本机局域网 IP 地址]：
ipconfig | findstr /C:"IPv4"
echo.

echo ========================================
echo   服务地址：
echo   本机访问:   http://127.0.0.1:5000
echo   局域网访问: http://上面的IPv4地址:5000
echo   数据查看:   http://127.0.0.1:5000/admin
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

:: ---- 启动服务 ----
:: 优先用 exe，没有则用 Python
if exist "dist-exe\wxsx-helper-server.exe" (
    echo [启动] 使用 exe 模式
    dist-exe\wxsx-helper-server.exe
) else (
    echo [启动] 使用 Python 模式
    python app.py
)
pause
