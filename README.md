# 微信小店售后增强 - 后端服务

## 项目说明

Flask 本地服务器 + SQLite 数据库，为 Chrome 插件提供售后标记数据存储。

## 目录结构

```
wxsx-helper-server/
├── app.py            # Flask 入口（API 路由 + admin 页面）
├── config.py         # 配置（端口、监听地址、数据库路径）
├── db.py             # SQLite 操作封装
├── build_exe.py      # PyInstaller 打包脚本
├── requirements.txt  # Python 依赖
├── start.bat         # Windows 启动脚本（带防火墙配置）
├── tray_app.py       # 托盘版后台服务（无控制台窗口）
├── start-tray.vbs    # 源码版托盘启动器（pythonw）
├── 微信小店售后助手.exe  # 独立单文件版（推荐，双击即用）
├── data/             # 数据库 / 日志 / 图标（exe 同级，勿删）
│   ├── wxsx_helper.db
│   ├── tray.log          # 服务日志
│   └── tray_icon.ico     # 托盘图标
└── dist-exe/         # 打包中间产物
    └── WXSX-Helper.exe
```

## 独立 exe 版（推荐，日常使用）

双击项目根目录的 `微信小店售后助手.exe` 即可，不需要装 Python、不需要 `.venv`、
不需要任何 VBS/BAT。单文件约 23 MB，无黑框，只在右下角托盘留一个绿色「S」图标。

- **exe 与 `data\` 目录同级**：直接沿用现有的 `data\wxsx_helper.db`，已有标记数据不丢
- **左键图标 / 菜单「显示状态窗口」**：打开状态小窗
- **状态小窗点 X 关闭**：只缩回托盘，服务继续运行，不会被误关
- **右键托盘图标 →「退出（真正停止服务）」**：唯一真正停止服务的方式
- 右键菜单还有：打开数据管理页、复制服务地址、打开日志、设为 / 取消开机自启
  （exe 版的开机自启项直接指向 exe 自己，不依赖 Python）

> 从源码版切换：先右键旧托盘图标 →「退出」，再双击 exe 即可；端口 5000 会短暂断开 1~2 秒。

## 托盘模式（源码运行）

服务不再需要常驻一个 cmd 黑框。双击工作区根目录的 `启动后台服务.vbs`（或本目录的
`start-tray.vbs`），进程用 `pythonw.exe` 无窗口运行，只在右下角系统托盘留一个绿色
「S」图标。

- **左键图标 / 菜单「显示状态窗口」**：打开状态小窗
- **状态小窗点 X 关闭**：只缩回托盘，服务继续运行，不会被误关
- **右键托盘图标 →「退出（真正停止服务）」**：唯一真正停止服务的方式
- 右键菜单还提供：打开数据管理页、复制服务地址、打开日志、设为 / 取消开机自启

首次启动时如果旧的控制台服务还占着 5000 端口，会弹窗询问是否结束它并接管。

日志文件：`data/tray.log`。服务异常时图标变红。

## 快速启动

### 方式一：Python 直接运行

```bash
pip install -r requirements.txt
python app.py
```

或双击 `start.bat`

### 方式二：exe 运行（免安装 Python，推荐）

双击项目根目录的 `微信小店售后助手.exe`

## 服务地址

| 用途       | 地址                          |
|------------|-------------------------------|
| API 健康检查 | http://127.0.0.1:5000/api/health |
| 数据查看页面 | http://127.0.0.1:5000/admin      |
| 数据导出    | http://127.0.0.1:5000/api/data/export |

局域网其他设备将 `127.0.0.1` 替换为服务器电脑的局域网 IP。

## 重新打包 exe

```bash
.venv\Scripts\python.exe build_exe.py
```

产物：`dist-exe\WXSX-Helper.exe`（英文原名），脚本会自动复制一份到项目根目录
并命名为 `微信小店售后助手.exe`。`--onefile --noconsole`，无黑框。

打包后自检（用临时端口，不干扰正在运行的正式服务）：

```bash
set WXSX_PORT=5099
微信小店售后助手.exe --selftest
```

退出码 0 表示通过；详细结果看 `data\tray.log` 里的 `SELFTEST_UI_OK` /
`SELFTEST_HTTP` / `SELFTEST_OK` 行。自检会验证托盘依赖、图标字体、Flask 服务、
`/api/health`、`/admin`、`/api/stats` 以及数据库路径。

## API 列表

| 方法   | 路径                | 说明                     |
|--------|---------------------|--------------------------|
| GET    | /api/health         | 健康检查                 |
| GET    | /api/marked         | 获取标记状态             |
| POST   | /api/marked         | 设置标记状态             |
| POST   | /api/marked/batch   | 批量获取标记状态         |
| GET    | /api/remark         | 获取备注                 |
| POST   | /api/remark         | 设置备注                 |
| GET    | /api/stats          | 统计数据                 |
| GET    | /admin              | 数据查看页面（HTML）     |
| GET    | /api/data/export    | 导出全部数据（JSON）     |
| POST   | /api/data/delete    | 删除一条记录             |
