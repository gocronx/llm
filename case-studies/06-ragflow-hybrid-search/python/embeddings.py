"""embeddings.py —— 真实 embedding 客户端（OpenAI 兼容 API）。

从 .env 读 API_BASE_URL / API_KEY / MODEL_ID。
无配置时返回 None，由调用方决定是否降级到 mock。
"""

from __future__ import annotations

import logging
import os

import numpy as np
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ragflow.embeddings")


class EmbeddingClient:
    """调用 OpenAI 兼容 /embeddings 接口。"""

    def __init__(self, model: str | None = None):
        self.model = (
            model or os.getenv("EMBEDDING_MODEL_ID") or "text-embedding-3-small"
        )
        self.base_url = os.getenv("API_BASE_URL")
        self.api_key = os.getenv("API_KEY")
        self._available = bool(self.base_url and self.api_key)

    def embed(self, text: str) -> np.ndarray | None:
        if not self._available:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            resp = client.embeddings.create(model=self.model, input=text)
            data = resp.data[0].embedding
            return np.array(data, dtype=np.float32)
        except Exception as e:
            logger.error("embedding failed: %s", e)
            return None

    def embed_batch(self, texts: list[str]) -> np.ndarray | None:
        if not self._available:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            resp = client.embeddings.create(model=self.model, input=texts)
            data = [d.embedding for d in resp.data]
            return np.array(data, dtype=np.float32)
        except Exception as e:
            logger.error("embedding batch failed: %s", e)
            return None


def get_client() -> EmbeddingClient | None:
    """单例获取。无配置返回 None。"""
    return _get_client()


def _get_client() -> EmbeddingClient | None:
    base = os.getenv("API_BASE_URL")
    key = os.getenv("API_KEY")
    if not base or not key:
        return None
    return EmbeddingClient()
