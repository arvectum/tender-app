from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


@dataclass(frozen=True)
class CatalogDictionaries:
    categories: dict[str, Any]
    brands: list[str]
    stopwords: list[str]
    service_keywords: list[str]
    work_keywords: list[str]
    units: list[str]
    synonyms: dict[str, list[str]]


def _load_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or default
    return payload


@lru_cache(maxsize=1)
def load_dictionaries() -> CatalogDictionaries:
    root = get_settings().project_root
    dpath = root / "data" / "dictionaries"
    categories = _load_yaml(dpath / "categories.yml", {})
    brands = _load_yaml(dpath / "brands.yml", {}).get("brands", [])
    stopwords = _load_yaml(dpath / "stopwords.yml", {}).get("stopwords", [])
    service_keywords = _load_yaml(dpath / "service_keywords.yml", {}).get("keywords", [])
    work_keywords = _load_yaml(dpath / "work_keywords.yml", {}).get("keywords", [])
    units = _load_yaml(dpath / "units.yml", {}).get("units", [])
    synonyms = _load_yaml(dpath / "synonyms.yml", {}).get("synonyms", {})
    return CatalogDictionaries(
        categories=categories,
        brands=[str(x).lower() for x in brands],
        stopwords=[str(x).lower() for x in stopwords],
        service_keywords=[str(x).lower() for x in service_keywords],
        work_keywords=[str(x).lower() for x in work_keywords],
        units=[str(x).lower() for x in units],
        synonyms={str(k).lower(): [str(v).lower() for v in values] for k, values in synonyms.items()},
    )
