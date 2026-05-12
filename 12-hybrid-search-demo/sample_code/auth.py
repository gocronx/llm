"""
用户认证模块
提供登录、注册、JWT token 验证等功能
"""

import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict


class AuthenticationError(Exception):
    """认证异常"""
    pass


class User:
    """用户模型"""
    
    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = datetime.now()
    
    def check_password(self, password: str) -> bool:
        """验证密码"""
        return self.password_hash == self._hash_password(password)
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()


class AuthService:
    """认证服务"""
    
    SECRET_KEY = "your-secret-key-change-in-production"
    TOKEN_EXPIRY = 24  # 小时
    
    def __init__(self):
        self.users_db = {}  # 模拟数据库
    
    def register(self, username: str, email: str, password: str) -> User:
        """用户注册"""
        if username in self.users_db:
            raise AuthenticationError("用户名已存在")
        
        user_id = len(self.users_db) + 1
        password_hash = User._hash_password(password)
        user = User(user_id, username, email, password_hash)
        
        self.users_db[username] = user
        return user
    
    def login(self, username: str, password: str) -> str:
        """用户登录，返回 JWT token"""
        user = self.users_db.get(username)
        
        if not user or not user.check_password(password):
            raise AuthenticationError("用户名或密码错误")
        
        # 生成 JWT token
        token = self._generate_token(user)
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """验证 JWT token"""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token 已过期")
        except jwt.InvalidTokenError:
            raise AuthenticationError("无效的 Token")
    
    def _generate_token(self, user: User) -> str:
        """生成 JWT token"""
        expiry = datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRY)
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "exp": expiry
        }
        token = jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")
        return token
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码"""
        user = self.users_db.get(username)
        
        if not user or not user.check_password(old_password):
            raise AuthenticationError("原密码错误")
        
        user.password_hash = User._hash_password(new_password)
        return True
    
    def reset_password(self, email: str) -> str:
        """重置密码（发送邮件）"""
        # 查找用户
        user = None
        for u in self.users_db.values():
            if u.email == email:
                user = u
                break
        
        if not user:
            raise AuthenticationError("邮箱不存在")
        
        # 生成重置 token
        reset_token = self._generate_reset_token(user)
        # 实际应用中这里会发送邮件
        return reset_token
    
    def _generate_reset_token(self, user: User) -> str:
        """生成密码重置 token"""
        expiry = datetime.utcnow() + timedelta(hours=1)
        payload = {
            "user_id": user.user_id,
            "type": "password_reset",
            "exp": expiry
        }
        token = jwt.encode(payload, self.SECRET_KEY, algorithm="HS256")
        return token
