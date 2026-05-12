"""
Web Streaming 演示
使用 FastAPI + SSE (Server-Sent Events)
"""

import os
import json
import requests
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 加载上级目录的 .env
load_dotenv("../.env")

app = FastAPI()

API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL_ID = os.getenv("MODEL_ID")

# 调试：打印配置
print(f"API_BASE_URL: {API_BASE_URL}")
print(f"MODEL_ID: {MODEL_ID}")


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页"""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/stream")
async def stream(request: Request):
    """流式响应端点"""
    data = await request.json()
    prompt = data.get('prompt', '')
    
    print(f"收到请求: {prompt}")
    
    async def generate():
        """生成器函数 - 逐块返回数据"""
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True
                },
                stream=True,
                timeout=60
            )
            
            print(f"API 响应状态: {response.status_code}")
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            
                            if data == '[DONE]':
                                yield f"data: {json.dumps({'done': True})}\n\n"
                                break
                            
                            try:
                                chunk = json.loads(data)
                                
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        print(f"发送内容: {content[:20]}...")
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                            
                            except json.JSONDecodeError as e:
                                print(f"JSON 解析错误: {e}")
                                pass
            else:
                error_msg = f'API错误: {response.status_code}'
                print(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
        
        except Exception as e:
            error_msg = f'请求异常: {str(e)}'
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


if __name__ == '__main__':
    import uvicorn
    print("启动 Web 服务器...")
    print("访问: http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
