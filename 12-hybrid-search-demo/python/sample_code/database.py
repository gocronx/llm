"""
数据库操作模块
提供 CRUD 操作、连接池管理、事务处理等功能
"""

import sqlite3
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import threading


class DatabaseError(Exception):
    """数据库异常"""
    pass


class ConnectionPool:
    """数据库连接池"""
    
    def __init__(self, database: str, max_connections: int = 10):
        self.database = database
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取连接"""
        with self.lock:
            if self.connections:
                return self.connections.pop()
            else:
                return sqlite3.connect(self.database)
    
    def return_connection(self, conn: sqlite3.Connection):
        """归还连接"""
        with self.lock:
            if len(self.connections) < self.max_connections:
                self.connections.append(conn)
            else:
                conn.close()
    
    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()


class Database:
    """数据库操作类"""
    
    def __init__(self, database: str = "app.db"):
        self.pool = ConnectionPool(database)
    
    @contextmanager
    def get_cursor(self):
        """获取游标（上下文管理器）"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"数据库操作失败: {e}")
        finally:
            cursor.close()
            self.pool.return_connection(conn)
    
    def execute(self, query: str, params: tuple = ()) -> int:
        """执行 SQL 语句，返回影响的行数"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """查询单条记录"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """查询多条记录"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """插入数据"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid
    
    def update(self, table: str, data: Dict[str, Any], where: str, params: tuple = ()) -> int:
        """更新数据"""
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        return self.execute(query, tuple(data.values()) + params)
    
    def delete(self, table: str, where: str, params: tuple = ()) -> int:
        """删除数据"""
        query = f"DELETE FROM {table} WHERE {where}"
        return self.execute(query, params)
    
    def create_table(self, table: str, schema: str):
        """创建表"""
        query = f"CREATE TABLE IF NOT EXISTS {table} ({schema})"
        self.execute(query)
    
    def table_exists(self, table: str) -> bool:
        """检查表是否存在"""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetch_one(query, (table,))
        return result is not None
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self.pool.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"事务失败: {e}")
        finally:
            self.pool.return_connection(conn)
    
    def close(self):
        """关闭数据库连接池"""
        self.pool.close_all()


# 使用示例
def init_database():
    """初始化数据库"""
    db = Database()
    
    # 创建用户表
    db.create_table("users", """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """)
    
    # 创建文章表
    db.create_table("posts", """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    """)
    
    return db
