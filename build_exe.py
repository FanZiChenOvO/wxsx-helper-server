# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置

使用方式：
  cd server
  python build_exe.py

生成的 exe 在 dist/wxsx-helper-server/ 目录下
"""

import os
import sys
from PyInstaller.__main__ import run

# 确保在 server 目录下执行
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 打包参数
opts = [
    '--name=wxsx-helper-server',
    '--onefile',                         # 打包成单个 exe
    '--console',                         # 控制台程序（需要看到启动日志）
    '--noconfirm',                       # 覆盖已有输出
    f'--distpath={os.path.join(BASE_DIR, "dist-exe")}',
    f'--workpath={os.path.join(BASE_DIR, "build-exe")}',
    f'--specpath={os.path.join(BASE_DIR, "build-exe")}',
    # 隐藏导入（Flask 相关）
    '--hidden-import=flask_cors',
    '--hidden-import=config',
    '--hidden-import=db',
    # 数据文件（不需要打包数据库，运行时自动创建）
    # 图标（如果有）
    # '--icon=icon.ico',
    # 入口文件
    os.path.join(BASE_DIR, 'app.py'),
]

print('=' * 50)
print('  开始打包 wxsx-helper-server.exe')
print('=' * 50)
print(f'  入口: app.py')
print(f'  输出: {os.path.join(BASE_DIR, "dist-exe")}')
print(f'  模式: 单文件 exe')
print('=' * 50)

run(opts)

print()
print('=' * 50)
print('  打包完成！')
print(f'  exe 路径: {os.path.join(BASE_DIR, "dist-exe", "wxsx-helper-server.exe")}')
print('=' * 50)
print()
print('  使用方式：')
print('    1. 将 wxsx-helper-server.exe 复制到任意目录')
print('    2. 双击运行（或命令行运行）')
print('    3. 首次运行会自动在 exe 同级目录创建 data/wxsx_helper.db')
print('    4. 服务地址: http://127.0.0.1:5000')
print()
