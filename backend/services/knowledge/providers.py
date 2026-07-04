from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


def _normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class BaseDeterministicEmbeddingProvider(ABC):
    provider_name: str
    model_name: str

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(f"{self.provider_name}:{self.model_name}:{text}".encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < self.dimensions:
            for byte in seed:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= self.dimensions:
                    break
            seed = hashlib.sha256(seed).digest()
        return _normalize_vector(values[: self.dimensions])


class DeterministicEmbeddingProvider(BaseDeterministicEmbeddingProvider):
    provider_name = "deterministic"
    model_name = "deterministic-embeddings"


class OpenAIEmbeddingProvider(DeterministicEmbeddingProvider):
    provider_name = "openai"
    model_name = "text-embedding-3-large"


class VoyageEmbeddingProvider(DeterministicEmbeddingProvider):
    provider_name = "voyage"
    model_name = "voyage-3"


class CohereEmbeddingProvider(DeterministicEmbeddingProvider):
    provider_name = "cohere"
    model_name = "embed-english-v3.0"


class AzureOpenAIEmbeddingProvider(DeterministicEmbeddingProvider):
    provider_name = "azure_openai"
    model_name = "text-embedding-3-large"


class EmbeddingProviderRegistry:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self._providers: dict[str, type[BaseDeterministicEmbeddingProvider]] = {
            "deterministic": DeterministicEmbeddingProvider,
            "openai": OpenAIEmbeddingProvider,
            "voyage": VoyageEmbeddingProvider,
            "cohere": CohereEmbeddingProvider,
            "azure_openai": AzureOpenAIEmbeddingProvider,
        }

    def get(self, provider_name: str | None) -> EmbeddingProvider:
        provider_cls = self._providers.get((provider_name or "deterministic").lower(), DeterministicEmbeddingProvider)
        return provider_cls(self.dimensions)

