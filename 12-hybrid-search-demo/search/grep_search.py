"""
GREP 精确搜索模块
使用正则表达式进行精确关键词匹配
"""

import re
import os
from typing import List, Dict, Tuple
from pathlib import Path


class GrepSearchResult:
    """GREP 搜索结果"""
    
    def __init__(self, file_path: str, line_number: int, line_content: str, match_score: float = 1.0):
        self.file_path = file_path
        self.line_number = line_number
        self.line_content = line_content.strip()
        self.match_score = match_score
    
    def __repr__(self):
        return f"<GrepResult {self.file_path}:{self.line_number} score={self.match_score:.2f}>"
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "match_score": self.match_score
        }


class GrepSearch:
    """GREP 搜索器"""
    
    def __init__(self, code_dir: str):
        self.code_dir = Path(code_dir)
        self.file_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.h']
    
    def search(self, query: str, case_sensitive: bool = False, max_results: int = 100) -> List[GrepSearchResult]:
        """
        搜索代码库
        
        Args:
            query: 搜索关键词
            case_sensitive: 是否区分大小写
            max_results: 最大结果数
        
        Returns:
            搜索结果列表
        """
        results = []
        
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 构建正则表达式
        patterns = []
        for keyword in keywords:
            if case_sensitive:
                patterns.append(re.compile(re.escape(keyword)))
            else:
                patterns.append(re.compile(re.escape(keyword), re.IGNORECASE))
        
        # 遍历所有代码文件
        for file_path in self._get_code_files():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        # 检查是否匹配任意关键词（改为 OR 逻辑）
                        match_count = 0
                        for pattern in patterns:
                            if pattern.search(line):
                                match_count += 1
                        
                        if match_count > 0:
                            # 计算匹配分数（匹配的关键词越多，分数越高）
                            score = match_count / len(patterns)
                            
                            result = GrepSearchResult(
                                file_path=str(file_path.relative_to(self.code_dir)),
                                line_number=line_num,
                                line_content=line,
                                match_score=score
                            )
                            results.append(result)
                            
                            if len(results) >= max_results:
                                break
            except (UnicodeDecodeError, PermissionError):
                continue
            
            if len(results) >= max_results:
                break
        
        # 按分数排序
        results.sort(key=lambda x: x.match_score, reverse=True)
        
        return results
    
    def search_with_context(self, query: str, context_lines: int = 3, max_results: int = 50) -> List[Dict]:
        """
        搜索并返回上下文
        
        Args:
            query: 搜索关键词
            context_lines: 上下文行数
            max_results: 最大结果数
        
        Returns:
            包含上下文的搜索结果
        """
        basic_results = self.search(query, max_results=max_results)
        results_with_context = []
        
        for result in basic_results:
            file_path = self.code_dir / result.file_path
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 获取上下文
                start = max(0, result.line_number - context_lines - 1)
                end = min(len(lines), result.line_number + context_lines)
                context = ''.join(lines[start:end])
                
                results_with_context.append({
                    **result.to_dict(),
                    "context": context,
                    "context_start_line": start + 1,
                    "context_end_line": end
                })
            except (UnicodeDecodeError, PermissionError):
                continue
        
        return results_with_context
    
    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取关键词"""
        # 移除常见停用词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        
        # 分词（简单按空格分割）
        words = query.split()
        
        # 过滤停用词和短词
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        
        # 如果没有关键词，使用原始查询
        if not keywords:
            keywords = [query]
        
        return keywords
    
    def _get_code_files(self) -> List[Path]:
        """获取所有代码文件"""
        code_files = []
        
        for ext in self.file_extensions:
            code_files.extend(self.code_dir.rglob(f'*{ext}'))
        
        return code_files
    
    def count_matches(self, query: str) -> int:
        """统计匹配数量"""
        return len(self.search(query, max_results=10000))
    
    def search_in_file(self, file_path: str, query: str) -> List[GrepSearchResult]:
        """在指定文件中搜索"""
        results = []
        full_path = self.code_dir / file_path
        
        if not full_path.exists():
            return results
        
        keywords = self._extract_keywords(query)
        patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords]
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    match_count = sum(1 for p in patterns if p.search(line))
                    
                    if match_count > 0:
                        score = match_count / len(patterns)
                        results.append(GrepSearchResult(
                            file_path=file_path,
                            line_number=line_num,
                            line_content=line,
                            match_score=score
                        ))
        except (UnicodeDecodeError, PermissionError):
            pass
        
        return results


# 使用示例
if __name__ == "__main__":
    searcher = GrepSearch("../sample_code")
    
    # 搜索认证相关代码
    results = searcher.search("认证 登录", max_results=10)
    
    print(f"找到 {len(results)} 个结果:\n")
    for r in results:
        print(f"{r.file_path}:{r.line_number} (score={r.match_score:.2f})")
        print(f"  {r.line_content}\n")
