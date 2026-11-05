"""
Flask 应用入口

启动方式：
  cd server
  python app.py

或双击 start.bat

服务地址：http://127.0.0.1:5000
"""

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import config
from db import (
    init_db,
    get_db,
    get_marked,
    set_marked,
    get_batch_marked,
    get_remark,
    set_remark,
    get_stats,
)

app = Flask(__name__)
# 允许 Chrome 插件跨域访问
# 支持本机 + 局域网内其他设备访问
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://store.weixin.qq.com",
            "chrome-extension://*",
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://0.0.0.0:*",
            # 允许局域网 IP 范围（192.168.x.x / 10.x.x.x / 172.16-31.x.x）
            "http://192.168.*:*",
            "http://10.*:*",
            "http://172.16.*:*",
            "http://172.17.*:*",
            "http://172.18.*:*",
            "http://172.19.*:*",
            "http://172.20.*:*",
            "http://172.21.*:*",
            "http://172.22.*:*",
            "http://172.23.*:*",
            "http://172.24.*:*",
            "http://172.25.*:*",
            "http://172.26.*:*",
            "http://172.27.*:*",
            "http://172.28.*:*",
            "http://172.29.*:*",
            "http://172.30.*:*",
            "http://172.31.*:*",
        ]
    }
})


# ================================================================
# 健康检查
# ================================================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'wxsx-shop-helper',
        'version': '1.0.0',
    })


# ================================================================
# 标记状态接口
# ================================================================

@app.route('/api/marked', methods=['GET'])
def api_get_marked():
    """获取某售后单的标记状态
    参数：shop_name, after_sale_id
    返回：{ "mark_status": "unmarked" / "marked" / "following" }
    """
    shop_name = request.args.get('shop_name', '')
    after_sale_id = request.args.get('after_sale_id', '')
    if not shop_name or not after_sale_id:
        return jsonify({'error': '缺少参数 shop_name 或 after_sale_id'}), 400
    mark_status = get_marked(shop_name, after_sale_id)
    return jsonify({'mark_status': mark_status})


@app.route('/api/marked', methods=['POST'])
def api_set_marked():
    """设置某售后单的标记状态
    body: { "shop_name": "...", "after_sale_id": "...", "mark_status": "unmarked"/"marked"/"following" }
    兼容旧接口：marked: true/false
    """
    data = request.get_json()
    if not data or not data.get('shop_name') or not data.get('after_sale_id'):
        return jsonify({'error': '缺少参数 shop_name 或 after_sale_id'}), 400

    # 兼容旧的 marked boolean 字段
    if 'mark_status' in data:
        mark_status = data['mark_status']
    elif 'marked' in data:
        mark_status = 'marked' if data['marked'] else 'unmarked'
    else:
        mark_status = 'unmarked'

    set_marked(data['shop_name'], data['after_sale_id'], mark_status)
    return jsonify({'success': True, 'mark_status': mark_status})


@app.route('/api/marked/batch', methods=['POST'])
def api_batch_marked():
    """批量获取多个售后单的标记状态
    body: { "shop_name": "...", "after_sale_ids": ["id1", "id2", ...] }
    返回：{ "marks": { "id1": "unmarked", "id2": "marked", ... } }
    兼容旧接口：同时返回 "marked" 字段（id -> bool，已处理=true）
    """
    data = request.get_json()
    if not data or not data.get('shop_name') or not data.get('after_sale_ids'):
        return jsonify({'error': '缺少参数'}), 400
    result = get_batch_marked(data['shop_name'], data['after_sale_ids'])
    # 兼容旧接口
    marked_compat = {k: v == 'marked' for k, v in result.items()}
    return jsonify({'marks': result, 'marked': marked_compat})


# ================================================================
# 备注接口（为后续功能预留）
# ================================================================

@app.route('/api/remark', methods=['GET'])
def api_get_remark():
    """获取某售后单的备注"""
    shop_name = request.args.get('shop_name', '')
    after_sale_id = request.args.get('after_sale_id', '')
    if not shop_name or not after_sale_id:
        return jsonify({'error': '缺少参数'}), 400
    remark = get_remark(shop_name, after_sale_id)
    return jsonify({'remark': remark})


@app.route('/api/remark', methods=['POST'])
def api_set_remark():
    """设置某售后单的备注"""
    data = request.get_json()
    if not data or not data.get('shop_name') or not data.get('after_sale_id'):
        return jsonify({'error': '缺少参数'}), 400
    remark = data.get('remark', '')
    set_remark(data['shop_name'], data['after_sale_id'], remark)
    return jsonify({'success': True, 'remark': remark})


# ================================================================
# 统计接口
# ================================================================

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """获取统计数据
    参数：shop_name（可选，不传则统计全部）
    """
    shop_name = request.args.get('shop_name')
    stats = get_stats(shop_name)
    return jsonify(stats)


# ================================================================
# 数据查看页面 — 浏览器打开 http://127.0.0.1:5000/admin
# ================================================================

@app.route('/admin')
def admin_page():
    """数据查看页面 — 直接在浏览器中查看所有标记数据"""
    conn = get_db()
    cursor = conn.cursor()

    # 查询所有数据
    cursor.execute("""
        SELECT shop_name, after_sale_id, marked, remark, updated_at
        FROM custom_data
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    # 获取统计
    stats = get_stats()

    # 转换 marked 值为中文
    mark_labels = {0: '未处理', 1: '已处理', 2: '跟进'}
    mark_colors = {0: '#ffcdd2', 1: '#c8e6c9', 2: '#fff9c4'}

    rows_html = ''
    for row in rows:
        mark_val = row['marked']
        mark_label = mark_labels.get(mark_val, '未知')
        mark_color = mark_colors.get(mark_val, '#e0e0e0')
        remark = row['remark'] or ''
        updated = row['updated_at'] or ''
        rows_html += f"""
        <tr>
          <td>{row['shop_name']}</td>
          <td>{row['after_sale_id']}</td>
          <td><span class="badge" style="background:{mark_color}">{mark_label}</span></td>
          <td>{remark}</td>
          <td>{updated[:19] if updated else ''}</td>
          <td><button class="btn-del" onclick="deleteRow('{row['shop_name']}','{row['after_sale_id']}')">删除</button></td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="6" class="empty">暂无数据</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>售后数据查看</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: #f5f5f5; color: #333; padding: 20px;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 16px; }}
  .stats {{
    display: flex; gap: 16px; margin-bottom: 20px;
  }}
  .stat-card {{
    flex: 1; background: white; border-radius: 8px; padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); text-align: center;
  }}
  .stat-card .num {{ font-size: 28px; font-weight: bold; }}
  .stat-card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
  .stat-card.total .num {{ color: #333; }}
  .stat-card.unmarked .num {{ color: #e53935; }}
  .stat-card.following .num {{ color: #f9a825; }}
  .stat-card.marked .num {{ color: #43a047; }}
  table {{
    width: 100%; border-collapse: collapse; background: white;
    border-radius: 8px; overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  th, td {{
    padding: 10px 14px; text-align: left; border-bottom: 1px solid #f0f0f0;
    font-size: 14px;
  }}
  th {{ background: #fafafa; font-weight: 600; color: #666; }}
  tr:hover {{ background: #f9f9f9; }}
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 10px;
    font-size: 12px; font-weight: 500;
  }}
  .empty {{ text-align: center; color: #999; padding: 40px; }}
  .btn-del {{
    padding: 4px 12px; background: #fff; border: 1px solid #ddd;
    border-radius: 4px; cursor: pointer; font-size: 12px; color: #e53935;
  }}
  .btn-del:hover {{ background: #ffebee; }}
  .toolbar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
  }}
  .toolbar .info {{ font-size: 13px; color: #888; }}
  .toolbar .actions {{ display: flex; gap: 8px; }}
  .btn {{
    padding: 6px 16px; border: none; border-radius: 6px;
    cursor: pointer; font-size: 13px;
  }}
  .btn-refresh {{ background: #2196f3; color: white; }}
  .btn-refresh:hover {{ background: #1976d2; }}
</style>
</head>
<body>
<div class="container">
  <h1>售后标记数据</h1>
  <div class="stats">
    <div class="stat-card total"><div class="num">{stats['total']}</div><div class="label">总计</div></div>
    <div class="stat-card unmarked"><div class="num">{stats['unmarked']}</div><div class="label">未处理</div></div>
    <div class="stat-card following"><div class="num">{stats.get('following', 0)}</div><div class="label">跟进中</div></div>
    <div class="stat-card marked"><div class="num">{stats['marked']}</div><div class="label">已处理</div></div>
  </div>
  <div class="toolbar">
    <span class="info">数据库路径: {config.DB_PATH}</span>
    <div class="actions">
      <button class="btn btn-refresh" onclick="location.reload()">刷新</button>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>店铺名称</th>
        <th>售后单号</th>
        <th>标记状态</th>
        <th>备注</th>
        <th>更新时间</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>
<script>
function deleteRow(shopName, afterSaleId) {{
  if (!confirm('确认删除这条记录？')) return;
  fetch('/api/data/delete', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{shop_name: shopName, after_sale_id: afterSaleId}})
  }}).then(r => r.json()).then(data => {{
    if (data.success) location.reload();
    else alert('删除失败: ' + (data.error || ''));
  }});
}}
</script>
</body>
</html>"""
    return Response(html, content_type='text/html; charset=utf-8')


@app.route('/api/data/delete', methods=['POST'])
def api_delete_data():
    """删除一条数据记录"""
    data = request.get_json()
    if not data or not data.get('shop_name') or not data.get('after_sale_id'):
        return jsonify({'error': '缺少参数'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM custom_data WHERE shop_name=? AND after_sale_id=?",
        (data['shop_name'], data['after_sale_id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/data/export', methods=['GET'])
def api_export_data():
    """导出所有数据为 JSON"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT shop_name, after_sale_id, marked, remark, updated_at
        FROM custom_data
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    mark_labels = {0: 'unmarked', 1: 'marked', 2: 'following'}
    result = []
    for row in rows:
        result.append({
            'shop_name': row['shop_name'],
            'after_sale_id': row['after_sale_id'],
            'mark_status': mark_labels.get(row['marked'], 'unknown'),
            'remark': row['remark'] or '',
            'updated_at': row['updated_at'] or '',
        })
    return jsonify({'data': result, 'total': len(result)})

if __name__ == '__main__':
    init_db()
    print(f"[启动] 服务地址: http://{config.HOST}:{config.PORT}")
    print(f"[启动] 数据查看: http://127.0.0.1:{config.PORT}/admin")
    print(f"[启动] 数据库: {config.DB_PATH}")
    print(f"[启动] 按 Ctrl+C 停止服务")
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )
