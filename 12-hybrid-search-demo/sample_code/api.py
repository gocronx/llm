"""
RESTful API 模块
提供 HTTP 接口、路由、中间件等功能
"""

from typing import Callable, Dict, Any, Optional
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class Request:
    """HTTP 请求对象"""
    
    def __init__(self, method: str, path: str, headers: Dict, body: str, query: Dict):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.query = query
        self.json_data = None
        
        # 解析 JSON body
        if headers.get("Content-Type") == "application/json" and body:
            try:
                self.json_data = json.loads(body)
            except json.JSONDecodeError:
                pass
    
    def get_json(self) -> Optional[Dict]:
        """获取 JSON 数据"""
        return self.json_data
    
    def get_header(self, name: str) -> Optional[str]:
        """获取请求头"""
        return self.headers.get(name)


class Response:
    """HTTP 响应对象"""
    
    def __init__(self):
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self.body = ""
    
    def json(self, data: Any, status_code: int = 200):
        """返回 JSON 响应"""
        self.status_code = status_code
        self.body = json.dumps(data, ensure_ascii=False)
        return self
    
    def text(self, text: str, status_code: int = 200):
        """返回文本响应"""
        self.status_code = status_code
        self.headers["Content-Type"] = "text/plain"
        self.body = text
        return self
    
    def error(self, message: str, status_code: int = 400):
        """返回错误响应"""
        return self.json({"error": message}, status_code)


class Router:
    """路由器"""
    
    def __init__(self):
        self.routes = {}
        self.middlewares = []
    
    def add_route(self, method: str, path: str, handler: Callable):
        """添加路由"""
        key = f"{method}:{path}"
        self.routes[key] = handler
    
    def get(self, path: str):
        """GET 路由装饰器"""
        def decorator(handler: Callable):
            self.add_route("GET", path, handler)
            return handler
        return decorator
    
    def post(self, path: str):
        """POST 路由装饰器"""
        def decorator(handler: Callable):
            self.add_route("POST", path, handler)
            return handler
        return decorator
    
    def put(self, path: str):
        """PUT 路由装饰器"""
        def decorator(handler: Callable):
            self.add_route("PUT", path, handler)
            return handler
        return decorator
    
    def delete(self, path: str):
        """DELETE 路由装饰器"""
        def decorator(handler: Callable):
            self.add_route("DELETE", path, handler)
            return handler
        return decorator
    
    def use(self, middleware: Callable):
        """添加中间件"""
        self.middlewares.append(middleware)
    
    def find_handler(self, method: str, path: str) -> Optional[Callable]:
        """查找路由处理器"""
        key = f"{method}:{path}"
        return self.routes.get(key)
    
    def handle_request(self, request: Request) -> Response:
        """处理请求"""
        response = Response()
        
        # 执行中间件
        for middleware in self.middlewares:
            result = middleware(request, response)
            if result is not None:
                return result
        
        # 查找路由
        handler = self.find_handler(request.method, request.path)
        
        if handler:
            try:
                return handler(request, response)
            except Exception as e:
                return response.error(f"服务器错误: {str(e)}", 500)
        else:
            return response.error("路由不存在", 404)


# 中间件示例
def auth_middleware(request: Request, response: Response) -> Optional[Response]:
    """认证中间件"""
    # 跳过登录接口
    if request.path == "/api/login":
        return None
    
    # 检查 Authorization header
    token = request.get_header("Authorization")
    if not token:
        return response.error("未授权", 401)
    
    # 验证 token（这里简化处理）
    if not token.startswith("Bearer "):
        return response.error("无效的 token 格式", 401)
    
    return None


def cors_middleware(request: Request, response: Response) -> Optional[Response]:
    """CORS 中间件"""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    
    if request.method == "OPTIONS":
        return response.text("", 204)
    
    return None


def logging_middleware(request: Request, response: Response) -> Optional[Response]:
    """日志中间件"""
    print(f"[{request.method}] {request.path}")
    return None


# API 示例
def create_api():
    """创建 API 应用"""
    router = Router()
    
    # 添加中间件
    router.use(logging_middleware)
    router.use(cors_middleware)
    
    # 定义路由
    @router.get("/api/health")
    def health_check(req: Request, res: Response):
        return res.json({"status": "ok"})
    
    @router.post("/api/login")
    def login(req: Request, res: Response):
        data = req.get_json()
        if not data or "username" not in data or "password" not in data:
            return res.error("缺少用户名或密码", 400)
        
        # 这里应该调用 AuthService
        return res.json({
            "token": "fake-jwt-token",
            "user": {"username": data["username"]}
        })
    
    @router.get("/api/users")
    def get_users(req: Request, res: Response):
        # 这里应该从数据库查询
        return res.json({
            "users": [
                {"id": 1, "username": "alice"},
                {"id": 2, "username": "bob"}
            ]
        })
    
    @router.post("/api/users")
    def create_user(req: Request, res: Response):
        data = req.get_json()
        if not data or "username" not in data:
            return res.error("缺少用户名", 400)
        
        # 这里应该插入数据库
        return res.json({"id": 3, "username": data["username"]}, 201)
    
    return router
