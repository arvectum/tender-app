from app.connectors.mos_portal.browser_fallback import _records_from_captured_payloads


def test_records_from_captured_payloads_normalizes_cards() -> None:
    payloads = [
        {
            "data": {
                "items": [
                    {
                        "id": 12345,
                        "name": "Поставка бумаги",
                        "statusName": "Прием предложений",
                        "positions": [{"name": "Бумага А4", "quantity": 10}],
                    }
                ]
            }
        }
    ]

    records = _records_from_captured_payloads(payloads, status="Прием предложений")

    assert len(records) == 1
    rec = records[0]
    assert rec["externalId"] == "12345"
    assert rec["title"] == "Поставка бумаги"
    assert rec["status"] == "Прием предложений"
    assert rec["url"].endswith("/auction/12345")
    assert isinstance(rec["items"], list)


def test_records_from_captured_payloads_deduplicates_and_keeps_url() -> None:
    payloads = [
        {
            "result": [
                {"auctionId": "A-1", "auctionName": "Лот 1", "href": "/auction/A-1"},
                {"auctionId": "A-1", "auctionName": "Лот 1 дубликат", "href": "/auction/A-1"},
            ]
        }
    ]

    records = _records_from_captured_payloads(payloads, status="S")

    assert len(records) == 1
    assert records[0]["externalId"] == "A-1"
    assert records[0]["url"] == "https://zakupki.mos.ru/auction/A-1"
