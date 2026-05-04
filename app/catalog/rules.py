from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9\-/]+")
ARTICLE_RE = re.compile(r"\b[A-ZА-Я]{1,4}\d{2,}[A-ZА-Я0-9\-]*\b")
MODEL_RE = re.compile(r"\b\d{2,4}[A-ZА-Я]{0,3}\b|\b[A-ZА-Я]{1,3}\d{2,4}\b")
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

ORIGINAL_KEYWORDS = {"оригинал", "оригинальный", "original"}
COMPATIBLE_KEYWORDS = {"совместимый", "аналог", "replacement", "compatible", "неоригинальный"}
COLORS = {
    "черный": "black",
    "чёрный": "black",
    "black": "black",
    "белый": "white",
    "white": "white",
    "цветной": "color",
}
