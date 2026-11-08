"""
数据库初始化和操作封装

表结构：
  custom_data — 自定义数据表（标记状态、备注等）
    id          INTEGER PRIMARY KEY
    shop_name   TEXT NOT NULL
    after_sale_id TEXT NOT NULL
    marked      INTEGER DEFAULT 0  (0=未处理, 1=已处理, 2=跟进)
    remark      TEXT DEFAULT ''
    custom_fields TEXT DEFAULT '{}'  (JSON 格式，存自定义字段)
    updated_at  TEXT
    UNIQUE(shop_name, after_sale_id)
"""

import sqlite3
import json
import os
from datetime import datetime
from config import DB_PATH

# 确保数据目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 返回字典格式
    conn.execute("PRAGMA journal_mode=WAL")  # 提高并发性能
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()

    # 自定义数据表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            after_sale_id TEXT NOT NULL,
            marked INTEGER DEFAULT 0,
            remark TEXT DEFAULT '',
            custom_fields TEXT DEFAULT '{}',
            updated_at TEXT,
            UNIQUE(shop_name, after_sale_id)
        )
    """)

    # 创建索引，加速查询
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_custom_data_shop
        ON custom_data(shop_name)
    """)

    conn.commit()
    conn.close()
    print(f"[数据库] 初始化完成: {DB_PATH}")


# ================================================================
# 标记状态操作
#
# marked 字段值：
#   0 = 未处理 (unmarked)
#   1 = 已处理 (marked)
#   2 = 跟进   (following)
# ================================================================

# 状态值映射
MARK_VALUES = {
    'unmarked': 0,
    'marked': 1,
    'following': 2,
}
VALUE_TO_MARK = {0: 'unmarked', 1: 'marked', 2: 'following'}


def get_marked(shop_name, after_sale_id):
    """获取某售后单的标记状态，返回字符串: 'unmarked' / 'marked' / 'following'"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT marked FROM custom_data WHERE shop_name=? AND after_sale_id=?",
        (shop_name, after_sale_id)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return VALUE_TO_MARK.get(row['marked'], 'unmarked')
    return 'unmarked'


def set_marked(shop_name, after_sale_id, mark_status):
    """设置某售后单的标记状态
    mark_status: 'unmarked' / 'marked' / 'following'
    """
    # 兼容旧的 boolean 值
    if isinstance(mark_status, bool):
        mark_status = 'marked' if mark_status else 'unmarked'

    mark_value = MARK_VALUES.get(mark_status, 0)
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO custom_data (shop_name, after_sale_id, marked, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(shop_name, after_sale_id)
        DO UPDATE SET marked=?, updated_at=?
    """, (shop_name, after_sale_id, mark_value, now,
          mark_value, now))
    conn.commit()
    conn.close()
    return True


def get_batch_marked(shop_name, after_sale_ids):
    """批量获取多个售后单的标记状态
    返回：{ "id1": "unmarked", "id2": "marked", ... }
    """
    if not after_sale_ids:
        return {}
    conn = get_db()
    cursor = conn.cursor()
    # 用 IN 查询
    placeholders = ','.join('?' * len(after_sale_ids))
    cursor.execute(
        f"SELECT after_sale_id, marked FROM custom_data WHERE shop_name=? AND after_sale_id IN ({placeholders})",
        [shop_name] + after_sale_ids
    )
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[row['after_sale_id']] = VALUE_TO_MARK.get(row['marked'], 'unmarked')
    # 未查到的默认为 unmarked
    for aid in after_sale_ids:
        if aid not in result:
            result[aid] = 'unmarked'
    return result


# ================================================================
# 附加状态（物流动作 / 电话动作 / 补货状态）
#
# 存在 custom_fields 这个 JSON 字段里，不改表结构：
#   {"logistics": "intercept", "phone": "called", "restock": "needed"}
# 空字符串表示「没选」。
#
# 为什么用 JSON 而不是加列：
#   加列要写迁移，旧库升级容易漏；这三个字段以后大概率还会加，
#   用 JSON 加一个 key 就行，不用动表。
# ================================================================

# 允许的 key，防止前端乱塞东西进 JSON
# logistics_no 是自动从列表页悬浮框抓到的发货物流单号（只存第一条）
EXTRA_KEYS = ('logistics', 'phone', 'restock', 'logistics_no')


def _empty_extra():
    """全空的附加状态"""
    return {key: '' for key in EXTRA_KEYS}


def get_extra(shop_name, after_sale_id):
    """读取某售后单的附加状态，缺省字段补空字符串"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT custom_fields FROM custom_data WHERE shop_name=? AND after_sale_id=?",
        (shop_name, after_sale_id)
    )
    row = cursor.fetchone()
    conn.close()

    result = _empty_extra()
    if row and row['custom_fields']:
        try:
            saved = json.loads(row['custom_fields'])
            if isinstance(saved, dict):
                for key in EXTRA_KEYS:
                    value = saved.get(key, '')
                    if isinstance(value, str):
                        result[key] = value
        except (ValueError, TypeError):
            pass
    return result


def patch_extra(shop_name, after_sale_id, patch):
    """合并写入附加状态（只改 patch 里带的 key，其余保持原样）"""
    if not isinstance(patch, dict):
        return get_extra(shop_name, after_sale_id)

    current = get_extra(shop_name, after_sale_id)
    for key, value in patch.items():
        if key in EXTRA_KEYS and isinstance(value, str):
            current[key] = value

    payload = json.dumps(current, ensure_ascii=False)
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO custom_data (shop_name, after_sale_id, custom_fields, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(shop_name, after_sale_id)
        DO UPDATE SET custom_fields=?, updated_at=?
    """, (shop_name, after_sale_id, payload, now, payload, now))
    conn.commit()
    conn.close()
    return current


def get_batch_extra(shop_name, after_sale_ids):
    """批量读附加状态：{ "id": {"logistics": "", ...} }"""
    if not after_sale_ids:
        return {}
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(after_sale_ids))
    cursor.execute(
        f"SELECT after_sale_id, custom_fields FROM custom_data WHERE shop_name=? AND after_sale_id IN ({placeholders})",
        [shop_name] + after_sale_ids
    )
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        item = _empty_extra()
        if row['custom_fields']:
            try:
                saved = json.loads(row['custom_fields'])
                if isinstance(saved, dict):
                    for key in EXTRA_KEYS:
                        value = saved.get(key, '')
                        if isinstance(value, str):
                            item[key] = value
            except (ValueError, TypeError):
                pass
        result[row['after_sale_id']] = item

    for aid in after_sale_ids:
        if aid not in result:
            result[aid] = _empty_extra()
    return result


# ================================================================
# 备注操作（为后续功能预留）
# ================================================================

def get_remark(shop_name, after_sale_id):
    """获取某售后单的备注"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT remark FROM custom_data WHERE shop_name=? AND after_sale_id=?",
        (shop_name, after_sale_id)
    )
    row = cursor.fetchone()
    conn.close()
    return row['remark'] if row and row['remark'] else ''


def set_remark(shop_name, after_sale_id, remark):
    """设置某售后单的备注"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO custom_data (shop_name, after_sale_id, remark, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(shop_name, after_sale_id)
        DO UPDATE SET remark=?, updated_at=?
    """, (shop_name, after_sale_id, remark, now, remark, now))
    conn.commit()
    conn.close()
    return True


# ================================================================
# 统计操作（为后续功能预留）
# ================================================================

def get_stats(shop_name=None):
    """获取统计数据"""
    conn = get_db()
    cursor = conn.cursor()

    if shop_name:
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN marked=1 THEN 1 ELSE 0 END) as marked_count, SUM(CASE WHEN marked=2 THEN 1 ELSE 0 END) as following_count FROM custom_data WHERE shop_name=?",
            (shop_name,)
        )
    else:
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN marked=1 THEN 1 ELSE 0 END) as marked_count, SUM(CASE WHEN marked=2 THEN 1 ELSE 0 END) as following_count FROM custom_data"
        )
    row = cursor.fetchone()
    conn.close()
    total = row['total'] or 0
    marked_count = row['marked_count'] or 0
    following_count = row['following_count'] or 0
    return {
        'total': total,
        'marked': marked_count,
        'following': following_count,
        'unmarked': total - marked_count - following_count,
    }
