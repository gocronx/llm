"""
向量语义搜索模块
使用 TF-IDF 或 Embedding 进行语义相似度搜索
"""

import pickle
import numpy as np
from typing import List, Dict, Tuple
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class VectorSearchResult:
    """向量搜索结果"""
    
    def __init__(self, file_path: str, content: str, similarity_score: float, chunk_id: int = 0):
        self.file_path = file_path
        self.content = content
        self.similarity_score = similarity_score
        self.chunk_id = chunk_id
    
    def __repr__(self):
        return f"<VectorResult {self.file_path} score={self.similarity_score:.3f}>"
    
    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "content": self.content,
            "similarity_score": self.similarity_score,
            "chunk_id": self.chunk_id
        }


class VectorSearch:
    """向量搜索器（基于 TF-IDF）"""
    
    def __init__(self, code_dir: str, index_path: str = "index/vectors.pkl"):
        self.code_dir = Path(code_dir)
        self.index_path = Path(index_path)
        self.vectorizer = None
        self.vectors = None
        self.documents = []
        self.file_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.h']
    
    def build_index(self, chunk_size: int = 500):
        """
        构建向量索引
        
        Args:
            chunk_size: 文本分块大小（字符数）
        """
        print("正在构建向量索引...")
        
        # 读取所有代码文件并分块
        self.documents = []
        
        for file_path in self._get_code_files():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 分块
                chunks = self._chunk_text(content, chunk_size)
                
                for i, chunk in enumerate(chunks):
                    self.documents.append({
                        "file_path": str(file_path.relative_to(self.code_dir)),
                        "content": chunk,
                        "chunk_id": i
                    })
            except (UnicodeDecodeError, PermissionError):
                continue
        
        print(f"共读取 {len(self.documents)} 个文本块")
        
        # 构建 TF-IDF 向量（字符级，适合中文）
        texts = [doc["content"] for doc in self.documents]
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            analyzer='char',  # 字符级分析（适合中文）
            ngram_range=(1, 3),  # 1-3 个字符
            min_df=1,
            lowercase=True
        )
        self.vectors = self.vectorizer.fit_transform(texts)
        
        print(f"向量维度: {self.vectors.shape}")
        
        # 保存索引
        self._save_index()
        print(f"索引已保存到 {self.index_path}")
    
    def load_index(self):
        """加载向量索引"""
        if not self.index_path.exists():
            raise FileNotFoundError(f"索引文件不存在: {self.index_path}")
        
        with open(self.index_path, 'rb') as f:
            data = pickle.load(f)
        
        self.vectorizer = data['vectorizer']
        self.vectors = data['vectors']
        self.documents = data['documents']
        
        print(f"已加载索引: {len(self.documents)} 个文本块")
    
    def search(self, query: str, top_k: int = 10) -> List[VectorSearchResult]:
        """
        语义搜索
        
        Args:
            query: 搜索查询
            top_k: 返回前 K 个结果
        
        Returns:
            搜索结果列表
        """
        if self.vectorizer is None or self.vectors is None:
            raise RuntimeError("请先构建或加载索引")
        
        # 将查询向量化
        query_vector = self.vectorizer.transform([query])
        
        # 计算余弦相似度
        similarities = cosine_similarity(query_vector, self.vectors)[0]
        
        # 获取 top-k 结果
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # 只返回有相似度的结果
                doc = self.documents[idx]
                results.append(VectorSearchResult(
                    file_path=doc["file_path"],
                    content=doc["content"],
                    similarity_score=float(similarities[idx]),
                    chunk_id=doc["chunk_id"]
                ))
        
        return results
    
    def search_with_threshold(self, query: str, threshold: float = 0.1, max_results: int = 50) -> List[VectorSearchResult]:
        """
        带阈值的搜索
        
        Args:
            query: 搜索查询
            threshold: 相似度阈值
            max_results: 最大结果数
        
        Returns:
            搜索结果列表
        """
        results = self.search(query, top_k=max_results)
        return [r for r in results if r.similarity_score >= threshold]
    
    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
        
        Returns:
            文本块列表
        """
        # 按行分割
        lines = text.split('\n')
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            if current_size + line_size > chunk_size and current_chunk:
                # 当前块已满，保存并开始新块
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # 添加最后一块
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _get_code_files(self) -> List[Path]:
        """获取所有代码文件"""
        code_files = []
        
        for ext in self.file_extensions:
            code_files.extend(self.code_dir.rglob(f'*{ext}'))
        
        return code_files
    
    def _save_index(self):
        """保存索引"""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.index_path, 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'vectors': self.vectors,
                'documents': self.documents
            }, f)
    
    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        if self.vectors is None:
            return {"status": "未加载索引"}
        
        return {
            "total_chunks": len(self.documents),
            "vector_dimension": self.vectors.shape[1],
            "unique_files": len(set(doc["file_path"] for doc in self.documents))
        }


# 使用示例
if __name__ == "__main__":
    searcher = VectorSearch("../sample_code")
    
    # 构建索引
    searcher.build_index()
    
    # 搜索
    results = searcher.search("用户认证和登录", top_k=5)
    
    print(f"\n找到 {len(results)} 个结果:\n")
    for r in results:
        print(f"{r.file_path} (score={r.similarity_score:.3f})")
        print(f"{r.content[:200]}...\n")
