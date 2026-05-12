"""
工具函数模块
提供常用的辅助函数、数据验证、格式化等功能
"""

import re
import hashlib
import base64
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple[bool, str]:
    """
    验证密码强度
    返回: (是否有效, 错误信息)
    """
    if len(password) < 8:
        return False, "密码长度至少8位"
    
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含大写字母"
    
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含小写字母"
    
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    
    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证用户名
    返回: (是否有效, 错误信息)
    """
    if len(username) < 3:
        return False, "用户名长度至少3位"
    
    if len(username) > 20:
        return False, "用户名长度不能超过20位"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "用户名只能包含字母、数字和下划线"
    
    return True, ""


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """字符串哈希"""
    if algorithm == "md5":
        return hashlib.md5(text.encode()).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(text.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(text.encode()).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")


def encode_base64(text: str) -> str:
    """Base64 编码"""
    return base64.b64encode(text.encode()).decode()


def decode_base64(encoded: str) -> str:
    """Base64 解码"""
    return base64.b64decode(encoded.encode()).decode()


def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化日期时间"""
    return dt.strftime(format)


def parse_datetime(date_str: str, format: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """解析日期时间字符串"""
    return datetime.strptime(date_str, format)


def get_time_ago(dt: datetime) -> str:
    """获取相对时间（如"3小时前"）"""
    now = datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}分钟前"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}小时前"
    elif seconds < 2592000:
        days = int(seconds / 86400)
        return f"{days}天前"
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f"{months}个月前"
    else:
        years = int(seconds / 31536000)
        return f"{years}年前"


def sanitize_html(html: str) -> str:
    """清理 HTML 标签（防止 XSS）"""
    # 简单实现，实际应用应使用专业库如 bleach
    return re.sub(r'<[^>]+>', '', html)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def slugify(text: str) -> str:
    """生成 URL 友好的 slug"""
    # 转小写
    text = text.lower()
    # 替换空格为连字符
    text = re.sub(r'\s+', '-', text)
    # 只保留字母、数字和连字符
    text = re.sub(r'[^a-z0-9-]', '', text)
    # 移除多余的连字符
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """深度合并字典"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """扁平化嵌套字典"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def remove_duplicates(lst: List, key: Optional[callable] = None) -> List:
    """去重（保持顺序）"""
    if key is None:
        seen = set()
        result = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        seen = set()
        result = []
        for item in lst:
            k = key(item)
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的 JSON 解析"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def calculate_file_hash(filepath: str, algorithm: str = "sha256") -> str:
    """计算文件哈希值"""
    hash_func = getattr(hashlib, algorithm)()
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


class Timer:
    """计时器上下文管理器"""
    
    def __init__(self, name: str = "操作"):
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, *args):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"{self.name} 耗时: {elapsed:.3f}秒")


# 使用示例
if __name__ == "__main__":
    # 验证邮箱
    print(validate_email("test@example.com"))  # True
    
    # 验证密码
    valid, msg = validate_password("Abc12345")
    print(valid, msg)  # True, ""
    
    # 时间格式化
    now = datetime.now()
    print(format_datetime(now))
    
    # 相对时间
    past = now - timedelta(hours=3)
    print(get_time_ago(past))  # "3小时前"
    
    # 计时器
    with Timer("测试操作"):
        import time
        time.sleep(0.1)
