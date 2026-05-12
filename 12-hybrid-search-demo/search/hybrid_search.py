"""
混合检索模块
结合 GREP 精确搜索和向量语义搜索
"""

from typing import List, Dict, Tuple
from .grep_search import GrepSearch, GrepSearchResult
from .vector_search import VectorSearch, VectorSearchResult


class HybridSearchResult:
    """混合搜索结果"""
    
    def __init__(self, file_path: str, content: str, score: float, 
                 grep_score: float = 0.0, vector_score: float = 0.0, 
                 line_number: int = None):
        self.file_path = file_path
        self.content = content
        self.score = score  # 综合分数
        self.grep_score = grep_score
        self.vector_score = vector_score
        self.line_number = line_number
    
    def __repr__(self):
        return f"<HybridResult {self.file_path} score={self.score:.3f} (grep={self.grep_score:.2f}, vector={self.vector_score:.3f})>"
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "content": self.content,
            "score": self.score,
            "grep_score": self.grep_score,
            "vector_score": self.vector_score,
            "line_number": self.line_number
        }


class HybridSearch:
    """混合搜索器"""
    
    def __init__(self, code_dir: str, index_path: str = "index/vectors.pkl"):
        self.grep_search = GrepSearch(code_dir)
        self.vector_search = VectorSearch(code_dir, index_path)
        self.code_dir = code_dir
    
    def build_index(self):
        """构建向量索引"""
        self.vector_search.build_index()
    
    def load_index(self):
        """加载向量索引"""
        self.vector_search.load_index()
    
    def search(self, query: str, top_k: int = 10, 
               grep_weight: float = 0.4, vector_weight: float = 0.6,
               use_grep: bool = True, use_vector: bool = True) -> List[HybridSearchResult]:
        """
        混合搜索
        
        Args:
            query: 搜索查询
            top_k: 返回前 K 个结果
            grep_weight: GREP 搜索权重
            vector_weight: 向量搜索权重
            use_grep: 是否使用 GREP 搜索
            use_vector: 是否使用向量搜索
        
        Returns:
            混合搜索结果列表
        """
        results_map = {}  # file_path -> result
        
        # 1. GREP 精确搜索
        if use_grep:
            grep_results = self.grep_search.search_with_context(query, context_lines=5, max_results=50)
            
            for gr in grep_results:
                key = f"{gr['file_path']}:{gr.get('line_number', 0)}"
                
                if key not in results_map:
                    results_map[key] = HybridSearchResult(
                        file_path=gr['file_path'],
                        content=gr.get('context', gr['line_content']),
                        score=0.0,
                        grep_score=gr['match_score'],
                        vector_score=0.0,
                        line_number=gr.get('line_number')
                    )
                else:
                    results_map[key].grep_score = max(results_map[key].grep_score, gr['match_score'])
        
        # 2. 向量语义搜索
        if use_vector:
            try:
                vector_results = self.vector_search.search(query, top_k=50)
                
                for vr in vector_results:
                    # 使用文件路径作为 key（向量搜索是按块的）
                    key = f"{vr.file_path}:chunk{vr.chunk_id}"
                    
                    if key not in results_map:
                        results_map[key] = HybridSearchResult(
                            file_path=vr.file_path,
                            content=vr.content,
                            score=0.0,
                            grep_score=0.0,
                            vector_score=vr.similarity_score
                        )
                    else:
                        results_map[key].vector_score = max(results_map[key].vector_score, vr.similarity_score)
            except RuntimeError as e:
                print(f"向量搜索失败: {e}")
        
        # 3. 计算综合分数
        results = []
        for result in results_map.values():
            # 归一化分数
            normalized_grep = result.grep_score
            normalized_vector = result.vector_score
            
            # 加权融合
            result.score = (grep_weight * normalized_grep + 
                          vector_weight * normalized_vector)
            
            results.append(result)
        
        # 4. 排序并返回 top-k
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]
    
    def search_with_strategy(self, query: str, top_k: int = 10, 
                            strategy: str = "balanced") -> List[HybridSearchResult]:
        """
        使用预定义策略搜索
        
        Args:
            query: 搜索查询
            top_k: 返回前 K 个结果
            strategy: 搜索策略
                - "balanced": 平衡策略（GREP 40%, Vector 60%）
                - "precise": 精确策略（GREP 70%, Vector 30%）
                - "semantic": 语义策略（GREP 20%, Vector 80%）
                - "grep_only": 仅 GREP
                - "vector_only": 仅向量
        
        Returns:
            搜索结果列表
        """
        strategies = {
            "balanced": (0.4, 0.6, True, True),
            "precise": (0.7, 0.3, True, True),
            "semantic": (0.2, 0.8, True, True),
            "grep_only": (1.0, 0.0, True, False),
            "vector_only": (0.0, 1.0, False, True)
        }
        
        if strategy not in strategies:
            raise ValueError(f"未知策略: {strategy}")
        
        grep_w, vector_w, use_grep, use_vector = strategies[strategy]
        
        return self.search(query, top_k, grep_w, vector_w, use_grep, use_vector)
    
    def compare_strategies(self, query: str, top_k: int = 5) -> Dict[str, List[HybridSearchResult]]:
        """
        对比不同策略的搜索结果
        
        Args:
            query: 搜索查询
            top_k: 每个策略返回的结果数
        
        Returns:
            策略名 -> 结果列表的字典
        """
        strategies = ["grep_only", "vector_only", "balanced", "precise", "semantic"]
        
        results = {}
        for strategy in strategies:
            results[strategy] = self.search_with_strategy(query, top_k, strategy)
        
        return results
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "grep": {
                "code_dir": str(self.code_dir)
            },
            "vector": self.vector_search.get_stats()
        }


# 使用示例
if __name__ == "__main__":
    searcher = HybridSearch("../sample_code")
    
    # 构建索引（首次运行）
    # searcher.build_index()
    
    # 加载索引
    try:
        searcher.load_index()
    except FileNotFoundError:
        print("索引不存在，正在构建...")
        searcher.build_index()
    
    # 搜索
    query = "如何实现用户认证和登录功能"
    results = searcher.search(query, top_k=5)
    
    print(f"\n混合搜索结果 (查询: {query}):\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.file_path}")
        print(f"   综合分数: {r.score:.3f} (GREP: {r.grep_score:.2f}, Vector: {r.vector_score:.3f})")
        print(f"   {r.content[:150]}...\n")
    
    # 对比不同策略
    print("\n" + "="*60)
    print("策略对比:")
    print("="*60)
    
    comparison = searcher.compare_strategies(query, top_k=3)
    
    for strategy, results in comparison.items():
        print(f"\n【{strategy}】")
        for r in results:
            print(f"  - {r.file_path} (score={r.score:.3f})")
