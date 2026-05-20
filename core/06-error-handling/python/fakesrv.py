"""fakesrv.py —— 本地起一个假的 OpenAI-compatible 服务，能按需返回 429/500/超时。
让 main.py / test.py 不依赖真 LLM 就能跑全套挡灾路径。"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    # 跨实例共享的脚本：path -> 这次该返回的 [code, retry_after, content]
    SCRIPT: dict[str, list[tuple[int, float | None, str]]] = {}

    def log_message(self, *_: object) -> None: ...  # 闭嘴

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)  # 不在乎 body 长啥样

        key = self.path
        script = self.SCRIPT.setdefault(key, [])
        if not script:
            # 没脚本：返回成功
            code, retry_after, content = 200, None, "ok"
        else:
            code, retry_after, content = script.pop(0)

        if content == "__sleep__":
            time.sleep(10)  # 让 client 超时

        self.send_response(code)
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.send_header("Content-Type", "application/json")
        body = json.dumps({
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "model": "fake",
        }).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeServer:
    """用法：
        with FakeServer() as srv:
            srv.script("/chat/completions", (429, 1.0, "ok"), (200, None, "hi"))
            ... 调 LLM 客户端，base_url=srv.base_url
    """

    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host
        self._http = HTTPServer((host, 0), _Handler)
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._http.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def script(self, path: str, *responses: tuple[int, float | None, str]) -> None:
        # path 应是 "/chat/completions"；OpenAI SDK 会自动拼到 base_url 上
        _Handler.SCRIPT[f"/v1{path}"] = list(responses)

    def __enter__(self) -> "FakeServer":
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._http.shutdown()
        self._http.server_close()
