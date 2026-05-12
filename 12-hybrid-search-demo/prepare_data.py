"""
数据准备脚本
构建向量索引
"""

import argparse
from pathlib import Path
from search import HybridSearch


def main():
    parser = argparse.ArgumentParser(description='准备混合检索数据')
    parser.add_argument('--path', type=str, default='sample_code',
                       help='代码库路径（默认: sample_code）')
    parser.add_argument('--index', type=str, default='index/vectors.pkl',
                       help='索引文件路径（默认: index/vectors.pkl）')
    
    args = parser.parse_args()
    
    print(f"代码库路径: {args.path}")
    print(f"索引路径: {args.index}\n")
    
    # 检查代码库是否存在
    if not Path(args.path).exists():
        print(f"错误: 代码库路径不存在: {args.path}")
        return
    
    # 创建混合搜索器
    searcher = HybridSearch(args.path, args.index)
    
    # 构建索引
    print("开始构建向量索引...")
    searcher.build_index()
    
    # 显示统计信息
    stats = searcher.get_stats()
    print("\n索引构建完成!")
    print(f"统计信息: {stats}")
    
    print("\n现在可以运行 demo.py 进行搜索了!")


if __name__ == "__main__":
    main()
