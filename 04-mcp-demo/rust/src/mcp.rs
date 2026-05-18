//! mcp.rs —— 极简 MCP-stdio 客户端。整文件 cp 进项目即可。
//!
//! MCP over stdio = JSON-RPC 2.0 over NDJSON。请求带 id，server 用同 id 回；
//! 通知（notifications/*）没 id，server 不回。
//!
//! 单线程同步实现：发一个请求就 block 等响应。LLM 调 tool 本身是串行的，
//! 一次只在跑一个工具，单线程够用，避免引入 tokio。

use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

pub struct MCPClient {
    child: Child,
    // stdin 是 Option：Drop 时 take() 出来再 drop，触发 OS 真正关闭 FD。
    // 不能用 `drop(self.stdin.write_all(b""))` —— 那只写零字节，不关连接。
    stdin: Option<ChildStdin>,
    stdout: BufReader<ChildStdout>,
    next_id: i64,
}

pub struct MCPTool {
    pub name: String,
    pub description: String,
    pub input_schema: Value,
}

impl MCPClient {
    /// 拉起 server 子进程，握手。
    pub fn spawn(command: &str, args: &[&str]) -> Result<Self, String> {
        let mut child = Command::new(command)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            // stderr 透传，server 调试输出直接进我们的 stderr
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("spawn server: {e}"))?;
        let stdin = child.stdin.take().ok_or("no stdin")?;
        let stdout = BufReader::new(child.stdout.take().ok_or("no stdout")?);
        let mut c = Self { child, stdin: Some(stdin), stdout, next_id: 0 };

        c.call("initialize", json!({
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "rust-mcp-client", "version": "0.1"},
        }))?;
        c.notify("notifications/initialized", json!({}))?;
        Ok(c)
    }

    pub fn list_tools(&mut self) -> Result<Vec<MCPTool>, String> {
        let res = self.call("tools/list", json!({}))?;
        let arr = res["tools"].as_array().ok_or("no tools array")?;
        Ok(arr.iter().map(|t| MCPTool {
            name: t["name"].as_str().unwrap_or("").to_string(),
            description: t["description"].as_str().unwrap_or("").to_string(),
            input_schema: t["inputSchema"].clone(),
        }).collect())
    }

    pub fn call_tool(&mut self, name: &str, args: Value) -> Result<String, String> {
        let res = self.call("tools/call", json!({"name": name, "arguments": args}))?;
        let mut out = String::new();
        if let Some(content) = res["content"].as_array() {
            for c in content {
                if c["type"].as_str() == Some("text") {
                    if let Some(t) = c["text"].as_str() {
                        out.push_str(t);
                    }
                }
            }
        }
        if res["isError"].as_bool() == Some(true) {
            return Err(format!("tool error: {out}"));
        }
        Ok(out)
    }

    // ---- 内部 ----

    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.next_id += 1;
        let id = self.next_id;
        self.send(&json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params}))?;

        // 同步等响应：跳过收到的通知（没 id），直到拿到匹配 id
        loop {
            let msg = self.recv()?;
            if msg.get("id").and_then(|v| v.as_i64()) != Some(id) {
                continue;
            }
            if let Some(err) = msg.get("error") {
                return Err(err["message"].as_str().unwrap_or("rpc error").to_string());
            }
            return Ok(msg["result"].clone());
        }
    }

    fn notify(&mut self, method: &str, params: Value) -> Result<(), String> {
        self.send(&json!({"jsonrpc": "2.0", "method": method, "params": params}))
    }

    fn send(&mut self, msg: &Value) -> Result<(), String> {
        let mut line = msg.to_string();
        line.push('\n');
        let stdin = self.stdin.as_mut().ok_or("stdin already closed")?;
        stdin.write_all(line.as_bytes()).map_err(|e| e.to_string())?;
        stdin.flush().map_err(|e| e.to_string())
    }

    fn recv(&mut self) -> Result<Value, String> {
        let mut line = String::new();
        let n = self.stdout.read_line(&mut line).map_err(|e| e.to_string())?;
        if n == 0 {
            return Err("server closed stdout".into());
        }
        serde_json::from_str(&line).map_err(|e| format!("bad json: {e}; line={line}"))
    }
}

impl Drop for MCPClient {
    fn drop(&mut self) {
        // take() 把 stdin 移出来再 drop，触发 OS 关闭管道；server 读到 EOF 自己退出。
        // 之后 wait 收尸防 zombie。
        drop(self.stdin.take());
        let _ = self.child.wait();
    }
}

#[cfg(test)]
mod tests {
    //! 拉 ../python/server.py 跑完整 initialize / list_tools / write+read round-trip。
    //! python server 不在就跳过。运行：`cargo test`
    use super::*;

    #[test]
    fn handshake_and_call_against_python_server() {
        let server = match std::path::PathBuf::from("../python/server.py").canonicalize() {
            Ok(p) => p,
            Err(_) => return,
        };
        let mut ws = std::env::temp_dir();
        ws.push(format!("rust-mcp-test-{}", std::process::id()));
        std::fs::create_dir_all(&ws).unwrap();

        let mut mcp = MCPClient::spawn("python3", &[server.to_str().unwrap(), ws.to_str().unwrap()])
            .expect("spawn server");
        let names: Vec<String> = mcp.list_tools().unwrap().into_iter().map(|t| t.name).collect();
        for want in ["read_file", "write_file", "list_directory"] {
            assert!(names.iter().any(|n| n == want), "missing tool: {want} (got {names:?})");
        }

        mcp.call_tool("write_file", json!({"path": "smoke.txt", "content": "from rust"})).unwrap();
        let got = mcp.call_tool("read_file", json!({"path": "smoke.txt"})).unwrap();
        assert_eq!(got, "from rust");

        let _ = std::fs::remove_dir_all(&ws);
    }
}
