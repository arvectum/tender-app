from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


TEMPLATE_COLUMNS = [
    "purchase_external_id",
    "position_external_id",
    "item_name",
    "offer_title",
    "offer_url",
    "seller_name",
    "region",
    "unit_price",
    "available_quantity",
    "delivery_price",
    "delivery_days",
    "is_relevant",
    "relevance_score",
    "comment",
]


def export_offer_template(file_path: Path) -> Path:
    file_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "OffersTemplate"
    ws.append(TEMPLATE_COLUMNS)

    sample_row = [
        "MOS-12345",
        "POS-001",
        "Картридж HP 305A CE410A",
        "Картридж HP 305A CE410A черный",
        "https://example.com/offer/1",
        "ООО Пример",
        "Москва",
        3500,
        10,
        300,
        2,
        True,
        0.92,
        "пример заполнения",
    ]
    ws.append(sample_row)

    instructions = wb.create_sheet("Instructions")
    instructions.append(["column", "description"])
    instructions.append(["purchase_external_id", "External id закупки, например MOS-12345"])
    instructions.append(["position_external_id", "External id позиции. Можно оставить пустым, тогда сопоставление по item_name"])
    instructions.append(["item_name", "Название позиции закупки (обязательно)"])
    instructions.append(["offer_title", "Название найденного рыночного предложения (обязательно)"])
    instructions.append(["offer_url", "Ссылка на предложение"])
    instructions.append(["seller_name", "Название продавца/поставщика"])
    instructions.append(["region", "Регион продавца/поставки"])
    instructions.append(["unit_price", "Цена за единицу (обязательно)"])
    instructions.append(["available_quantity", "Доступное количество"])
    instructions.append(["delivery_price", "Стоимость доставки"])
    instructions.append(["delivery_days", "Срок доставки в днях"])
    instructions.append(["is_relevant", "true/false или 1/0"])
    instructions.append(["relevance_score", "Число от 0 до 1"])
    instructions.append(["comment", "Комментарий аналитика"])

    wb.save(file_path)
    return file_path
