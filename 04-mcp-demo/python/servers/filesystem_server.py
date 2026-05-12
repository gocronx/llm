"""
MCP Server 示例 - 文件系统服务器
提供文件读取、写入、列表等功能
"""

import os
import json
from typing import Any, Dict, List
from mcp.server import Server
from mcp.types import Tool, TextContent


class FileSystemServer:
    """文件系统 MCP Server"""
    
    def __init__(self, base_path: str = "."):
        self.base_path = os.path.abspath(base_path)
        self.server = Server("filesystem-server")
        self._register_tools()
    
    def _register_tools(self):
        """注册工具"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出所有可用工具"""
            return [
                Tool(
                    name="read_file",
                    description="读取文件内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径（相对于基础路径）"
                            }
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="write_file",
                    description="写入文件内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径（相对于基础路径）"
                            },
                            "content": {
                                "type": "string",
                                "description": "要写入的内容"
                            }
                        },
                        "required": ["path", "content"]
                    }
                ),
                Tool(
                    name="list_directory",
                    description="列出目录内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "目录路径（相对于基础路径）",
                                "default": "."
                            }
                        }
                    }
                ),
                Tool(
                    name="file_exists",
                    description="检查文件是否存在",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径（相对于基础路径）"
                            }
                        },
                        "required": ["path"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """调用工具"""
            
            if name == "read_file":
                return await self._read_file(arguments["path"])
            
            elif name == "write_file":
                return await self._write_file(arguments["path"], arguments["content"])
            
            elif name == "list_directory":
                path = arguments.get("path", ".")
                return await self._list_directory(path)
            
            elif name == "file_exists":
                return await self._file_exists(arguments["path"])
            
            else:
                return [TextContent(
                    type="text",
                    text=f"未知工具: {name}"
                )]
    
    def _get_full_path(self, path: str) -> str:
        """获取完整路径并验证安全性"""
        full_path = os.path.abspath(os.path.join(self.base_path, path))
        
        # 安全检查：确保路径在基础路径内
        if not full_path.startswith(self.base_path):
            raise ValueError(f"路径 {path} 超出允许范围")
        
        return full_path
    
    async def _read_file(self, path: str) -> List[TextContent]:
        """读取文件"""
        try:
            full_path = self._get_full_path(path)
            
            if not os.path.exists(full_path):
                return [TextContent(
                    type="text",
                    text=f"文件不存在: {path}"
                )]
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return [TextContent(
                type="text",
                text=f"文件内容 ({path}):\n\n{content}"
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"读取文件失败: {str(e)}"
            )]
    
    async def _write_file(self, path: str, content: str) -> List[TextContent]:
        """写入文件"""
        try:
            full_path = self._get_full_path(path)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return [TextContent(
                type="text",
                text=f"成功写入文件: {path}"
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"写入文件失败: {str(e)}"
            )]
    
    async def _list_directory(self, path: str) -> List[TextContent]:
        """列出目录"""
        try:
            full_path = self._get_full_path(path)
            
            if not os.path.exists(full_path):
                return [TextContent(
                    type="text",
                    text=f"目录不存在: {path}"
                )]
            
            if not os.path.isdir(full_path):
                return [TextContent(
                    type="text",
                    text=f"不是目录: {path}"
                )]
            
            items = os.listdir(full_path)
            items.sort()
            
            result = f"目录内容 ({path}):\n\n"
            for item in items:
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    result += f"📁 {item}/\n"
                else:
                    size = os.path.getsize(item_path)
                    result += f"📄 {item} ({size} bytes)\n"
            
            return [TextContent(
                type="text",
                text=result
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"列出目录失败: {str(e)}"
            )]
    
    async def _file_exists(self, path: str) -> List[TextContent]:
        """检查文件是否存在"""
        try:
            full_path = self._get_full_path(path)
            exists = os.path.exists(full_path)
            
            return [TextContent(
                type="text",
                text=f"文件 {path} {'存在' if exists else '不存在'}"
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"检查文件失败: {str(e)}"
            )]
    
    async def run(self):
        """运行服务器"""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


if __name__ == "__main__":
    import asyncio
    
    # 创建测试目录
    test_dir = "test_workspace"
    os.makedirs(test_dir, exist_ok=True)
    
    server = FileSystemServer(test_dir)
    asyncio.run(server.run())
