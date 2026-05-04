from __future__ import annotations

from app.catalog.dictionaries import CatalogDictionaries
from app.catalog.rules import ARTICLE_RE, COLORS, MODEL_RE, NUMBER_RE, TOKEN_RE


def extract_tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text.lower()) if token.strip()]


def extract_brand(tokens: list[str], dictionaries: CatalogDictionaries) -> str | None:
    for token in tokens:
        if token.lower() in dictionaries.brands:
            return token.upper()
    return None


def extract_article(text_upper: str) -> str | None:
    match = ARTICLE_RE.search(text_upper)
    return match.group(0) if match else None


def extract_model(text_upper: str, article: str | None) -> str | None:
    for match in MODEL_RE.findall(text_upper):
        if article and match == article:
            continue
        if any(ch.isdigit() for ch in match):
            return match
    return None


def extract_color(tokens: list[str]) -> str | None:
    for token in tokens:
        mapped = COLORS.get(token)
        if mapped:
            return mapped
    return None


def extract_numbers(text: str) -> list[str]:
    return NUMBER_RE.findall(text)


def extract_units(tokens: list[str], units: list[str]) -> list[str]:
    units_set = set(units)
    return [token for token in tokens if token in units_set]
