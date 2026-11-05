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
├── start.bat         # Windows 启动脚本
├── data/             # 数据库文件目录（自动创建）
│   └── wxsx_helper.db
└── dist-exe/         # 打包产物
    └── wxsx-helper-server.exe
```

## 快速启动

### 方式一：Python 直接运行

```bash
pip install -r requirements.txt
python app.py
```

或双击 `start.bat`

### 方式二：exe 运行（免安装 Python）

双击 `dist-exe/wxsx-helper-server.exe`

## 服务地址

| 用途       | 地址                          |
|------------|-------------------------------|
| API 健康检查 | http://127.0.0.1:5000/api/health |
| 数据查看页面 | http://127.0.0.1:5000/admin      |
| 数据导出    | http://127.0.0.1:5000/api/data/export |

局域网其他设备将 `127.0.0.1` 替换为服务器电脑的局域网 IP。

## 重新打包 exe

```bash
python build_exe.py
```

生成的 exe 在 `dist-exe/` 目录下。

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
