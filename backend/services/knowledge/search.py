from __future__ import annotations

import math
from dataclasses import dataclass


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions must match")
    dot_product = sum(l * r for l, r in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return dot_product / (left_norm * right_norm)


def lexical_similarity(query: str, chunk_text: str) -> float:
    query_terms = {term for term in query.lower().split() if term}
    chunk_terms = {term for term in chunk_text.lower().split() if term}
    if not query_terms or not chunk_terms:
        return 0.0
    return len(query_terms & chunk_terms) / len(query_terms | chunk_terms)

