# -*- coding: utf-8 -*-
"""
微信小店售后增强 —— 托盘版后台服务

与旧的 `start-backend.bat` 区别：

  旧版：cmd 黑框常驻，误点窗口 X 服务就没了。
  新版：没有控制台窗口，服务跑在后台线程，只在系统托盘留一个小图标。
        - 左键图标 / 菜单「显示状态窗口」：打开状态小窗
        - 状态小窗点 X 关闭：只是缩回托盘，服务继续运行
        - 右键托盘图标 →「退出」：才真正停止服务并结束进程

必须用 pythonw.exe 启动（无控制台），见 start-tray.vbs。
"""

import ctypes
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from ctypes import wintypes
from datetime import datetime

# PyInstaller --onefile 会把代码解压到临时目录 _MEIxxxxx，
# 此时 __file__ 指向临时目录；数据/日志/图标必须落在 exe 同级目录，
# 否则每次重启都会换一个临时目录，日志和数据库会「消失」。
FROZEN = getattr(sys, 'frozen', False)
BASE_DIR = (os.path.dirname(sys.executable) if FROZEN
            else os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import config
PORT = config.PORT

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
LOG_PATH = os.path.join(DATA_DIR, 'tray.log')
ICO_PATH = os.path.join(DATA_DIR, 'tray_icon.ico')
CREATE_NO_WINDOW = 0x08000000

_log_file = open(LOG_PATH, 'a', encoding='utf-8', buffering=1)


class _Stream:
    """pythonw 下 sys.stdout / sys.stderr 为 None，重定向到日志文件。"""

    def __init__(self, f):
        self.f = f

    def write(self, s):
        try:
            self.f.write(s)
            self.f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.f.flush()
        except Exception:
            pass

    def isatty(self):
        return False

    def fileno(self):
        return self.f.fileno()

    @property
    def encoding(self):
        return 'utf-8'


sys.stdout = _Stream(_log_file)
sys.stderr = _Stream(_log_file)


def log(msg):
    try:
        _log_file.write('[%s] %s\n' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg))
        _log_file.flush()
    except Exception:
        pass


def alert(msg, title='微信小店售后助手', style=0x10):
    """无控制台时也要能报错；MB_TOPMOST 保证看得见。"""
    try:
        ctypes.windll.user32.MessageBoxW(0, str(msg), title, style | 0x40000)
    except Exception:
        log('弹窗失败: ' + str(msg))


def confirm(msg, title='微信小店售后助手'):
    try:
        # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST（默认「是」，双击启动脚本就是想切过去）
        r = ctypes.windll.user32.MessageBoxW(0, str(msg), title, 0x4 | 0x20 | 0x40000)
        return r == 6  # IDYES
    except Exception:
        return False


# ================================================================
# 单实例：重复双击启动脚本时，不要出现两个托盘图标
# ================================================================

_mutex_handle = None


def acquire_single_instance():
    global _mutex_handle
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    # 按端口区分：同一端口只准有一个托盘，不同端口（如自检用的临时端口）可共存
    name = 'Local\\WXSX_HELPER_TRAY_MUTEX_%d' % PORT
    _mutex_handle = k32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


# ================================================================
# 旧的黑框服务接管：端口被占时，问一句再结束它
# ================================================================

def _run_hidden(args, timeout=8):
    try:
        return subprocess.check_output(
            args, creationflags=CREATE_NO_WINDOW, timeout=timeout,
            text=True, errors='ignore')
    except Exception as e:
        log('命令执行失败 %s: %s' % (args[0], e))
        return ''


def pid_on_port(port):
    out = _run_hidden(['netstat', '-ano', '-p', 'TCP'])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == 'TCP' and parts[3] == 'LISTENING':
            if parts[1].endswith(':' + str(port)):
                try:
                    return int(parts[4])
                except ValueError:
                    pass
    return None


def process_info(pid):
    out = _run_hidden([
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        'Get-CimInstance Win32_Process -Filter "ProcessId=%d" | '
        'Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | '
        'ConvertTo-Json -Compress' % pid,
    ])
    try:
        return json.loads(out.strip())
    except Exception:
        return None


def kill_pid(pid, tree=False):
    args = ['taskkill', '/PID', str(pid), '/F']
    if tree:
        args.append('/T')  # 连子进程一起结束
    _run_hidden(args, timeout=6)


def find_cmd_ancestor(pid, max_depth=5):
    """往上找那个 cmd 黑框。venv 的 python.exe 会多一层 launcher，不能只看一层父。"""
    seen = set()
    cur = pid
    for _ in range(max_depth):
        if not cur or cur in seen:
            return None
        seen.add(cur)
        info = process_info(cur)
        if not isinstance(info, dict):
            return None
        if (info.get('Name') or '').lower() == 'cmd.exe':
            return info
        cur = info.get('ParentProcessId')
    return None


def takeover_old_server(port):
    """返回 True 表示旧服务已被结束、可以重新 bind。"""
    pid = pid_on_port(port)
    if not pid:
        return False

    info = process_info(pid)
    if not isinstance(info, dict):
        alert('%d 端口被占用（PID %d），但读不到进程信息。\n请手动关闭占用程序后再启动。' % (port, pid))
        return False

    exe = (info.get('ExecutablePath') or '').lower()
    name = (info.get('Name') or '').lower()
    cmdline = info.get('CommandLine') or ''
    # 注意：venv 的 python.exe 是 launcher，Get-CimInstance 报的 ExecutablePath
    # 往往是系统 Python，路径里不一定带项目名；命令行则是相对路径的 app.py。
    # 所以「python + app.py」就算本项目旧服务，再配合下面的确认弹窗兜底。
    ours = (
        'wxsx-helper-server' in exe
        or (name.startswith('python') and 'app.py' in cmdline)
        or 'wxsx-helper-server' in cmdline.lower()
    )
    if not ours:
        alert('%d 端口被其他程序占用（PID %d，%s）。\n\n请手动关闭它，或改 config.py 里的 PORT。'
              % (port, pid, info.get('Name') or '未知进程'))
        return False

    if not confirm(
        '检测到旧的「黑框」控制台服务还在运行（PID %d）。\n\n'
        '是否结束它，并切换到托盘模式？\n\n'
        '选「是」会重启服务，插件可能有 1~2 秒连不上；\n'
        '选「否」则本次不启动托盘。' % pid
    ):
        return False

    # 连黑框 cmd 一起关掉，不然它会一直停在「请按任意键继续」。
    # /T 会把 cmd 底下的两层 python 一并结束，一步到位。
    cmd_info = find_cmd_ancestor(pid)
    if cmd_info:
        cmdline2 = (cmd_info.get('CommandLine') or '').lower()
        if any(k in cmdline2 for k in ('start.bat', 'start-backend', 'wxsx', 'app.py')):
            log('结束旧黑框窗口 %s（含子进程树）' % cmd_info['ProcessId'])
            kill_pid(cmd_info['ProcessId'], tree=True)
        else:
            log('结束旧服务进程 %s' % pid)
            kill_pid(pid)
    else:
        log('结束旧服务进程 %s' % pid)
        kill_pid(pid)

    time.sleep(1.2)
    return True


# ================================================================
# 图标
# ================================================================

def make_icon_image(ok=True):
    from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = (7, 193, 96, 255) if ok else (226, 75, 74, 255)
    d.rounded_rectangle([2, 2, 62, 62], radius=16, fill=fill)

    # 白色 "S"，在 16x16 托盘尺寸下比汉字清晰
    font = None
    for p in (r'C:\Windows\Fonts\arialbd.ttf', r'C:\Windows\Fonts\segoeuib.ttf',
              r'C:\Windows\Fonts\arial.ttf'):
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, 42)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    text = 'S'
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1] - 3),
           text, fill='white', font=font)
    return img


def save_ico():
    try:
        make_icon_image(True).save(
            ICO_PATH, format='ICO', sizes=[(16, 16), (32, 32), (48, 48)])
    except Exception as e:
        log('图标文件生成失败（不影响托盘）: %s' % e)


# ================================================================
# 全局状态
# ================================================================

STATUS = {
    'ok': True,
    'text': '● 服务运行中  ·  127.0.0.1:%d' % PORT,
    'started': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
}
ui_queue = queue.Queue()
srv = None
icon = None
root = None
lbl_status = None
lbl_detail = None
STARTUP_VBS = os.path.join(
    os.environ.get('APPDATA', ''),
    r'Microsoft\Windows\Start Menu\Programs\Startup\WXSX-Helper-Tray.vbs')


def post(fn):
    """托盘消息循环线程 → tkinter 主线程的唯一通道（tkinter 不是线程安全的）。"""
    ui_queue.put(fn)


def pump():
    try:
        while True:
            fn = ui_queue.get_nowait()
            fn()
    except queue.Empty:
        pass
    except Exception:
        log('UI 命令异常:\n' + traceback.format_exc())
    try:
        root.after(120, pump)
    except Exception:
        pass


def apply_state():
    """服务健康状态变化时：换图标颜色 / 刷新菜单文字 / 刷新窗口。"""
    ok = STATUS['ok']
    try:
        icon.icon = make_icon_image(ok)
        icon.title = ('售后助手 · 运行中 (127.0.0.1:%d)' % PORT if ok
                      else '售后助手 · 服务未响应！')
        icon.update_menu()
    except Exception:
        pass
    try:
        lbl_status.config(
            text='● 服务运行中' if ok else '● 服务未响应',
            fg='#07c160' if ok else '#e24b4a')
        lbl_detail.config(
            text=STATUS['text'] + '\n启动时间：' + STATUS['started'])
    except Exception:
        pass


def health_loop():
    while True:
        time.sleep(8)
        ok = False
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=1):
                ok = True
        except Exception:
            pass
        if ok != STATUS['ok']:
            STATUS['ok'] = ok
            STATUS['text'] = ('● 服务运行中  ·  127.0.0.1:%d' % PORT if ok
                              else '● 服务未响应！请右键托盘 → 退出后重新启动')
            log('服务状态变为: %s' % ('正常' if ok else '未响应'))
            post(apply_state)


# ================================================================
# 菜单动作
# ================================================================

def show_window():
    post(lambda: _show_window_impl())


def _show_window_impl():
    try:
        root.deiconify()
        root.lift()
        root.focus_force()
        apply_state()
    except Exception:
        pass


def hide_window():
    """点窗口 X：只缩回托盘，不停服务。"""
    try:
        root.withdraw()
    except Exception:
        pass
    try:
        icon.notify('服务继续在后台运行，右键托盘图标可退出。', '微信小店售后助手')
    except Exception:
        pass


def open_admin():
    post(lambda: webbrowser.open('http://127.0.0.1:%d/admin' % PORT))


def copy_addr():
    def _do():
        try:
            root.clipboard_clear()
            root.clipboard_append('http://127.0.0.1:%d' % PORT)
            root.update()
        except Exception:
            pass
    post(_do)
    try:
        icon.notify('已复制 http://127.0.0.1:%d' % PORT, '微信小店售后助手')
    except Exception:
        pass


def open_log():
    post(lambda: os.startfile(LOG_PATH))


def is_autostart():
    return os.path.isfile(STARTUP_VBS)


def toggle_autostart():
    post(lambda: _toggle_autostart_impl())


def _toggle_autostart_impl():
    try:
        if is_autostart():
            os.remove(STARTUP_VBS)
            msg = '已取消开机自动启动。'
        else:
            if FROZEN:
                # exe 版直接启动自己，不再依赖 .venv / start-tray.vbs / pythonw.exe
                # 用 Chr(34) 拼引号，兼容路径中的空格；中文路径交给 mbcs 编码
                run_line = 'sh.Run q & "%s" & q, 0, False\n' % sys.executable
            else:
                own_vbs = os.path.join(BASE_DIR, 'start-tray.vbs')
                run_line = 'sh.Run "wscript.exe ""%s""", 0, False\n' % own_vbs
            content = (
                "' WeChat Shop helper backend - tray mode, no console window\n"
                'Set sh = CreateObject("WScript.Shell")\n'
                'q = Chr(34)\n' + run_line
            )
            # WSH 按系统 ANSI 代码页读取 .vbs，中文路径用 mbcs 才不会乱码
            try:
                with open(STARTUP_VBS, 'w', encoding='mbcs') as f:
                    f.write(content)
            except (LookupError, UnicodeError):
                with open(STARTUP_VBS, 'w', encoding='utf-8') as f:
                    f.write(content)
            msg = '已设置开机自动启动：登录后服务会在托盘里静默运行。'
        icon.update_menu()
        try:
            icon.notify(msg, '微信小店售后助手')
        except Exception:
            pass
        log(msg)
    except Exception as e:
        alert('设置开机自启失败：%s' % e)


def quit_app():
    """唯一真正退出的入口：右键托盘 → 退出。"""
    post(_quit_impl)


def _quit_impl():
    global srv
    log('收到退出指令，开始停止服务')
    try:
        if srv is not None:
            srv.shutdown()
            log('Flask 已停止')
    except Exception as e:
        log('停止 Flask 异常: %s' % e)
    try:
        icon.visible = False
        icon.stop()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
    try:
        _log_file.flush()
        _log_file.close()
    except Exception:
        pass
    # run_detached 起的消息循环线程不一定随 mainloop 结束，直接退出最干净
    os._exit(0)


# ================================================================
# 主流程
# ================================================================

def start_server(allow_takeover=True):
    from app import app as flask_app, init_db
    from werkzeug.serving import make_server

    init_db()
    for attempt in (1, 2):
        try:
            server = make_server(config.HOST, config.PORT, flask_app, threaded=True)
            th = threading.Thread(target=server.serve_forever,
                                  name='wxsx-flask', daemon=True)
            th.start()
            log('Flask 已启动: http://127.0.0.1:%d' % config.PORT)
            return server
        except OSError as e:
            log('端口绑定失败（第 %d 次）: %s' % (attempt, e))
            if allow_takeover and attempt == 1 and takeover_old_server(PORT):
                continue
            raise


def build_window():
    import tkinter as tk
    global root, lbl_status, lbl_detail

    root = tk.Tk()
    root.title('微信小店售后助手 · 服务状态')
    root.geometry('460x280')
    root.resizable(False, False)
    root.protocol('WM_DELETE_WINDOW', hide_window)
    try:
        root.iconbitmap(ICO_PATH)
    except Exception:
        pass

    frm = tk.Frame(root, padx=22, pady=18)
    frm.pack(fill='both', expand=True)

    tk.Label(frm, text='微信小店售后助手', font=('Microsoft YaHei UI', 15, 'bold'),
             fg='#1f2329').pack(anchor='w')
    lbl_status = tk.Label(frm, text='● 服务运行中', font=('Microsoft YaHei UI', 12),
                          fg='#07c160')
    lbl_status.pack(anchor='w', pady=(12, 4))
    lbl_detail = tk.Label(frm, text=STATUS['text'] + '\n启动时间：' + STATUS['started'],
                          font=('Microsoft YaHei UI', 9), fg='#6b7078',
                          justify='left')
    lbl_detail.pack(anchor='w')

    tk.Label(frm, text='关闭本窗口只会缩回右下角托盘，服务不会停止。\n'
                       '要彻底退出：右键托盘图标 →「退出」。',
             font=('Microsoft YaHei UI', 9), fg='#8a8f99', justify='left',
             wraplength=410).pack(anchor='w', pady=(16, 12))

    bar = tk.Frame(frm)
    bar.pack(fill='x')
    tk.Button(bar, text='打开数据管理页', width=16,
              command=lambda: webbrowser.open('http://127.0.0.1:%d/admin' % PORT)
              ).pack(side='left')
    tk.Button(bar, text='缩到托盘', width=12, command=hide_window).pack(side='left', padx=8)
    tk.Button(bar, text='查看日志', width=12,
              command=lambda: os.startfile(LOG_PATH)).pack(side='left')

    root.withdraw()  # 启动时没有窗口，只有托盘图标


def main():
    global srv, icon

    if not acquire_single_instance():
        alert('售后助手服务已经在运行了（右下角托盘有绿色图标）。\n'
              '不用重复启动；要停止请右键那个图标 →「退出」。', style=0x40)
        return

    log('=' * 60)
    log('托盘版服务启动')

    try:
        srv = start_server()
    except Exception as e:
        log('启动失败:\n' + traceback.format_exc())
        alert('后台服务启动失败：\n\n%s\n\n详细原因见：\n%s' % (e, LOG_PATH))
        return

    save_ico()
    build_window()

    import pystray

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: STATUS['text'], lambda i: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('显示状态窗口', lambda i: show_window(), default=True),
        pystray.MenuItem('打开数据管理页', lambda i: open_admin()),
        pystray.MenuItem('复制服务地址', lambda i: copy_addr()),
        pystray.MenuItem('打开日志文件', lambda i: open_log()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            lambda item: '取消开机自启' if is_autostart() else '设为开机自启',
            lambda i: toggle_autostart()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('退出（真正停止服务）', lambda i: quit_app()),
    )

    icon = pystray.Icon('wxsx-helper', make_icon_image(True),
                        '售后助手 · 运行中 (127.0.0.1:%d)' % PORT, menu)
    icon.run_detached()

    threading.Thread(target=health_loop, name='health', daemon=True).start()
    root.after(120, pump)
    log('托盘图标已就绪')
    root.mainloop()


def run_selftest():
    """打包后自检：不建托盘、不开窗口，起一次服务打 /api/health 就退出。

    用 WXSX_PORT=xxxx 指定临时端口，可在不干扰正在运行的正式服务时验证 exe。
    """
    import urllib.request
    global srv
    try:
        # 1) 托盘 / 图标 / 窗口依赖：这些都是动态加载，打包漏了双击才会报错
        import pystray
        import pystray._win32
        import tkinter
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        img = make_icon_image(True)
        log('SELFTEST_UI_OK tkinter=%s icon_size=%s pystray_backend=win32'
            % (tkinter.TkVersion, img.size))
        _ = pystray.Icon  # 确认托盘类可用

        # 2) HTTP 服务 + 数据库读写路径
        srv = start_server(allow_takeover=False)
        results = []
        for path in ('/api/health', '/admin', '/api/stats'):
            url = 'http://127.0.0.1:%d%s' % (PORT, path)
            with urllib.request.urlopen(url, timeout=6) as r:
                body = r.read().decode('utf-8', 'ignore')
                results.append('%s=%d' % (path, r.status))
            log('SELFTEST_HTTP %s body=%s' % (results[-1], body[:120]))
        log('SELFTEST_OK %s' % ' '.join(results))
        log('SELFTEST_DB %s' % config.DB_PATH)
        log('SELFTEST_EXE %s' % sys.executable)
        return 0
    except Exception:
        log('SELFTEST_FAIL\n' + traceback.format_exc())
        return 1


if __name__ == '__main__':
    try:
        if '--selftest' in sys.argv:
            rc = run_selftest()
            _log_file.flush()
            os._exit(rc)
        main()
    except Exception:
        log('未捕获异常:\n' + traceback.format_exc())
        alert('托盘程序异常退出：\n\n%s' % traceback.format_exc()[-800:])
