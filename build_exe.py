# -*- coding: utf-8 -*-
"""把托盘版后台服务打包成一个独立 exe。

用法：
    .venv\\Scripts\\python.exe build_exe.py

产物：
    dist-exe\\WXSX-Helper.exe        构建原名（中间产物）
    <项目根>\\微信小店售后助手.exe   最终交付，双击即用

要点：
  * --onefile + --noconsole：单文件、无黑框，只在右下角托盘留图标
  * 数据库 / 日志 / 图标都在 exe 同级的 data\\ 下（tray_app.py 已按 frozen 修正）
    因此 exe 放在项目根目录时会直接沿用现有的 data\\wxsx_helper.db
  * 自检（不建托盘、不干扰正式服务）：
        set WXSX_PORT=5099
        微信小店售后助手.exe --selftest
    结果写在 data\\tray.log 的 SELFTEST_OK / SELFTEST_FAIL 行
"""

import os
import shutil

from PyInstaller.__main__ import run

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASCII_NAME = 'WXSX-Helper'
CN_NAME = '微信小店售后助手.exe'
DIST_DIR = os.path.join(BASE_DIR, 'dist-exe')
WORK_DIR = os.path.join(BASE_DIR, 'build-exe')
ICON = os.path.join(BASE_DIR, 'data', 'tray_icon.ico')
ENTRY = os.path.join(BASE_DIR, 'tray_app.py')

opts = [
    '--name=%s' % ASCII_NAME,
    '--onefile',
    '--noconsole',              # 无控制台黑框
    '--clean',
    '--noconfirm',
    '--distpath=%s' % DIST_DIR,
    '--workpath=%s' % WORK_DIR,
    '--specpath=%s' % WORK_DIR,
    # 项目内模块（部分在函数内动态 import，静态分析可能漏掉）
    '--hidden-import=config',
    '--hidden-import=db',
    '--hidden-import=app',
    '--hidden-import=flask_cors',
    '--hidden-import=tkinter',
    # pystray 的平台后端 / PIL 的图像插件都是动态加载，必须整包收进来
    '--collect-submodules=pystray',
    '--collect-submodules=PIL',
    '--collect-submodules=jinja2',
    # Flask 3 / Werkzeug 运行时会用 importlib.metadata 读版本号
    '--copy-metadata=flask',
    '--copy-metadata=flask-cors',
    '--copy-metadata=jinja2',
    '--copy-metadata=werkzeug',
    '--copy-metadata=pystray',
    '--copy-metadata=pillow',
]

if os.path.isfile(ICON):
    opts.append('--icon=%s' % ICON)

opts.append(ENTRY)

print('=' * 60)
print('  打包托盘版后台服务 -> 单个 exe')
print('  入口: tray_app.py')
print('  模式: onefile / noconsole (无黑框)')
print('=' * 60)

run(opts)

built = os.path.join(DIST_DIR, ASCII_NAME + '.exe')
if not os.path.isfile(built):
    raise SystemExit('构建失败：没找到 %s' % built)

final = os.path.join(BASE_DIR, CN_NAME)
shutil.copy2(built, final)

print()
print('=' * 60)
print('  完成：%s' % final)
print('  大小：%.1f MB' % (os.path.getsize(final) / 1024 / 1024))
print('=' * 60)
print('  双击即可运行；右键托盘图标 ->「退出」才是真正停止服务。')
print('  数据沿用：%s' % os.path.join(BASE_DIR, 'data', 'wxsx_helper.db'))
print()
