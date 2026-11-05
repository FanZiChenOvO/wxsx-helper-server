# ================================================================
# 配置文件
#
# 修改下面的值为你自己的配置
# ================================================================

import os
import sys

# Flask 服务端口
PORT = 5000

# 监听地址：
#   '127.0.0.1' → 仅本机访问
#   '0.0.0.0'   → 允许局域网内其他设备访问（推荐）
# 单台电脑使用不受影响，127.0.0.1 的请求照常能访问
HOST = '0.0.0.0'

# 数据库文件路径 — 始终放在 exe/script 所在目录的 data/ 下
# PyInstaller 打包后 sys.frozen == 'exe'，此时用 exe 所在目录
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(_BASE_DIR, 'data', 'wxsx_helper.db')

# 调试模式（生产环境设为 False）
# debug=True 会导致 Flask 自动重启进程，后台运行时可能退出
DEBUG = False
