from __future__ import annotations

import csv
from pathlib import Path

from app.services.small_tender_report_service import (
    build_manifest_from_attachments_dir,
    build_single_file_manifest,
    generate_small_tender_report,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_generate_small_tender_report_extraction_matching_and_risk_logic(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "P-GREEN",
                "item_name": "Huawei коммутатор S5735S 24",
                "offer_title": "Huawei коммутатор S5735S 24T4S",
                "unit_price": "90",
            },
            {
                "purchase_external_id": "P-HIGH",
                "item_name": "Huawei коммутатор S5735S 24",
                "offer_title": "Huawei коммутатор S5735S 24T4S",
                "unit_price": "70",
            },
            {
                "purchase_external_id": "P-REJECT",
                "item_name": "Huawei коммутатор S5735S 24",
                "offer_title": "Huawei коммутатор S5735S 24T4S",
                "unit_price": "40",
            },
            {
                "purchase_external_id": "P-NOMATCH",
                "item_name": "Мышь беспроводная",
                "offer_title": "Офисная мышь",
                "unit_price": "50",
            },
        ],
    )
    _write_csv(
        ref_csv,
        [
            {"purchase_external_id": "P-GREEN", "unit_price": "100"},
            {"purchase_external_id": "P-HIGH", "unit_price": "100"},
            {"purchase_external_id": "P-REJECT", "unit_price": "100"},
            {"purchase_external_id": "P-NOMATCH", "unit_price": "100"},
        ],
    )
    tz_txt.write_text("Huawei коммутатор S5735S 24T4S", encoding="utf-8")
    _write_csv(
        manifest_csv,
        [
            {"purchase_external_id": "P-GREEN", "attachment_path": str(tz_txt)},
            {"purchase_external_id": "P-HIGH", "attachment_path": str(tz_txt)},
            {"purchase_external_id": "P-REJECT", "attachment_path": str(tz_txt)},
            {"purchase_external_id": "P-NOMATCH", "attachment_path": str(tz_txt)},
        ],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    summary = generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    assert out_csv.exists()
    assert out_xlsx.exists()
    assert diag_csv.exists()
    assert summary["report_rows"] == 4
    assert summary["green_rows"] == 1
    assert summary["high_risk_rows"] == 1
    assert summary["reject_rows"] == 2

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    by_id = {row["purchase_external_id"]: row for row in rows}
    assert by_id["P-GREEN"]["tz_match_type"] == "full"
    assert by_id["P-GREEN"]["decision_status"] == "green"

    assert by_id["P-HIGH"]["decision_status"] == "high_risk"
    assert by_id["P-HIGH"]["decision_reason"] == "margin_gt_25_high_risk"

    assert by_id["P-REJECT"]["decision_status"] == "reject"
    assert by_id["P-REJECT"]["decision_reason"] == "margin_gt_50_reject"

    assert by_id["P-NOMATCH"]["tz_match_type"] == "none"
    assert by_id["P-NOMATCH"]["decision_status"] == "reject"


def test_build_single_file_manifest(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    attachment = tmp_path / "tz.txt"
    out_manifest = tmp_path / "manifest.csv"

    _write_csv(
        source_csv,
        [
            {"purchase_external_id": "P2", "item_name": "x"},
            {"purchase_external_id": "P1", "item_name": "x"},
            {"purchase_external_id": "P1", "item_name": "x"},
        ],
    )
    attachment.write_text("demo tz", encoding="utf-8")

    result = build_single_file_manifest(
        source_csv=source_csv,
        attachment_path=attachment,
        out_manifest_csv=out_manifest,
    )

    assert result == out_manifest
    with out_manifest.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert [row["purchase_external_id"] for row in rows] == ["P1", "P2"]
    assert all(row["attachment_path"] == str(attachment) for row in rows)


def test_build_manifest_from_attachments_dir_prefers_tz_files(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    attachments_root = tmp_path / "attachments"
    out_manifest = tmp_path / "manifest.csv"

    _write_csv(
        source_csv,
        [
            {"purchase_external_id": "P1", "item_name": "x"},
            {"purchase_external_id": "P2", "item_name": "x"},
        ],
    )

    p1_dir = attachments_root / "P1"
    p1_dir.mkdir(parents=True)
    (p1_dir / "Регистрация_с_ЭП_и_без_ЭП.pdf").write_text("noise", encoding="utf-8")
    (p1_dir / "Техническое_задание.docx").write_text("tz", encoding="utf-8")

    p2_dir = attachments_root / "P2"
    p2_dir.mkdir(parents=True)
    (p2_dir / "specification.pdf").write_text("tz2", encoding="utf-8")

    result = build_manifest_from_attachments_dir(
        source_csv=source_csv,
        attachments_root=attachments_root,
        out_manifest_csv=out_manifest,
    )

    assert result == out_manifest
    with out_manifest.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 3
    p1_rows = [row for row in rows if row["purchase_external_id"] == "P1"]
    assert p1_rows[0]["attachment_path"].endswith("Техническое_задание.docx")


def test_generate_small_tender_report_strict_attribute_match_from_tz_text(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz_attr.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "P-ATTR",
                "item_name": "Коммутатор сетевой Huawei, 24 порта, штука",
                "offer_title": "HUAWEI S5735S-24T4X, арт. 98012345",
                "unit_price": "90",
            }
        ],
    )
    _write_csv(
        ref_csv,
        [
            {"purchase_external_id": "P-ATTR", "unit_price": "100"},
        ],
    )
    tz_txt.write_text(
        "ТЗ: требуется модель S5735S 24T4X (артикул 98012345), количество портов: 24, ед. изм.: шт.",
        encoding="utf-8",
    )
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "P-ATTR", "attachment_path": str(tz_txt)}],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    summary = generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    assert summary["report_rows"] == 1
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tz_match_type"] == "full"
    assert rows[0]["strict_full_match"] == "True"
    assert rows[0]["decision_status"] == "green"


def test_generate_small_tender_report_fallback_when_tz_is_non_product_noise(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz_noise.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "P-FALLBACK",
                "item_name": "Поставка коммутатора Huawei",
                "offer_title": "Поставка коммутатора Huawei",
                "unit_price": "90",
            }
        ],
    )
    _write_csv(ref_csv, [{"purchase_external_id": "P-FALLBACK", "unit_price": "100"}])
    tz_txt.write_text(
        "Инструкция: регистрация организации пользователя с применением электронной подписи",
        encoding="utf-8",
    )
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "P-FALLBACK", "attachment_path": str(tz_txt)}],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tz_match_type"] == "full"
    assert rows[0]["decision_status"] == "green"


def test_generate_small_tender_report_uses_alternative_price_fields_for_margin(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "P-PRICE",
                "item_name": "Коммутатор Huawei",
                "offer_title": "Huawei S5735S-24T4S",
                "unit_price": "NaN",
                "offered_unit_price": "1 500,50",
            }
        ],
    )
    _write_csv(
        ref_csv,
        [
            {
                "purchase_external_id": "P-PRICE",
                "tender_unit_price_ref": "2 000,00",
                "unit_price": "",
            }
        ],
    )
    tz_txt.write_text("Huawei S5735S-24T4S", encoding="utf-8")
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "P-PRICE", "attachment_path": str(tz_txt)}],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    summary = generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    assert summary["report_rows"] == 1
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tender_unit_price_ref"] == "2000.0"
    assert rows[0]["market_unit_price"] == "1500.5"
    assert rows[0]["margin_pct"] == "24.98"
    assert rows[0]["decision_reason"] != "missing_price_for_margin"
    assert rows[0]["decision_status"] == "green"


def test_generate_small_tender_report_mos_portal_endpoint_fallback(tmp_path: Path, monkeypatch) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "10207839",
                "source": "mos_portal",
                "purchase_url": "https://zakupki.mos.ru/auction/10207839",
                "item_name": "Техническое задание коммутатор Huawei S5735S-24T4S",
                "offer_title": "Коммутатор Huawei S5735S-24T4S",
                "unit_price": "90",
                "offer_source_url": "https://supplier.example/huawei-s5735s-24t4s",
            }
        ],
    )
    _write_csv(ref_csv, [{"purchase_external_id": "10207839", "unit_price": "100"}])
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "10207839", "attachment_path": str(tmp_path / "missing.docx")}],
    )

    class _FakeResponse:
        def __init__(self, status_code: int = 200, json_payload: dict | None = None, content: bytes = b"", headers: dict | None = None):
            self.status_code = status_code
            self._json_payload = json_payload or {}
            self.content = content
            self.headers = headers or {}

        def json(self) -> dict:
            return self._json_payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http_{self.status_code}")

    class _FakeSession:
        def __init__(self) -> None:
            self.trust_env = True
            self.headers: dict[str, str] = {}

        def get(self, url: str, **kwargs):
            if "Auction/Get" in url:
                return _FakeResponse(
                    200,
                    json_payload={
                        "files": [
                            {"id": 1, "name": "Регистрация_с_ЭП_и_без_ЭП.pdf"},
                            {"id": 2, "name": "Техническое_задание.txt"},
                        ]
                    },
                )
            if "FileStorage/Download" in url:
                file_id = int((kwargs.get("params") or {}).get("id"))
                if file_id == 2:
                        return _FakeResponse(
                            200,
                            content=("Техническое задание коммутатор Huawei S5735S-24T4S " * 20).encode("utf-8"),
                            headers={"content-type": "text/plain"},
                        )
                return _FakeResponse(404)
            return _FakeResponse(404)

    monkeypatch.setattr("app.services.small_tender_report_service.requests.Session", _FakeSession)

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    summary = generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    assert summary["report_rows"] == 1
    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tz_extraction_status"] == "ok"
    assert rows[0]["tz_attachment_path"].startswith("mos_portal_api:2:Техническое_задание.txt")
    assert rows[0]["decision_status"] == "green"


def test_generate_small_tender_report_mos_portal_signature_match_with_noisy_tz(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz_noisy.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "10208353",
                "source": "mos_portal",
                "purchase_url": "https://zakupki.mos.ru/auction/10208353",
                "item_name": "Коммутатор Huawei S5735S-24T4X",
                "offer_title": "Коммутатор Huawei S5735S 24T4X",
                "unit_price": "90",
                "offer_source_url": "https://supplier.example/huawei-s5735s-24t4x",
            }
        ],
    )
    _write_csv(ref_csv, [{"purchase_external_id": "10208353", "unit_price": "100"}])
    tz_txt.write_text(
        """
        Техническое задание на поставку сетевого оборудования.
        Требуется Коммутатор HUAWEI S5735S-24T4X.
        Общие условия поставки, сроки, ответственность сторон и порядок приемки товара.
        Дополнительные требования к упаковке и маркировке.
        """,
        encoding="utf-8",
    )
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "10208353", "attachment_path": str(tz_txt)}],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tz_match_type"] == "full"
    assert rows[0]["strict_full_match"] == "True"
    assert rows[0]["decision_status"] == "green"


def test_generate_small_tender_report_mos_portal_signature_mismatch_reject(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    ref_csv = tmp_path / "tender_ref.csv"
    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz_mismatch.txt"

    _write_csv(
        market_csv,
        [
            {
                "purchase_external_id": "10208351",
                "source": "mos_portal",
                "purchase_url": "https://zakupki.mos.ru/auction/10208351",
                "item_name": "Коммутатор Huawei S5735S-24T4X",
                "offer_title": "Коммутатор Huawei S5735S 24T4X",
                "unit_price": "90",
                "offer_source_url": "https://supplier.example/huawei-s5735s-24t4x",
            }
        ],
    )
    _write_csv(ref_csv, [{"purchase_external_id": "10208351", "unit_price": "100"}])
    tz_txt.write_text(
        "Техническое задание: поставить коммутатор Huawei S5735S-48T4X.",
        encoding="utf-8",
    )
    _write_csv(
        manifest_csv,
        [{"purchase_external_id": "10208351", "attachment_path": str(tz_txt)}],
    )

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    generate_small_tender_report(
        market_csv=market_csv,
        tender_ref_csv=ref_csv,
        out_csv=out_csv,
        out_xlsx=out_xlsx,
        diagnostics_csv=diag_csv,
        attachments_manifest_csv=manifest_csv,
    )

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["tz_match_type"] == "none"
    assert rows[0]["strict_full_match"] == "False"
    assert rows[0]["decision_status"] == "reject"
    assert rows[0]["decision_reason"] == "strict_full_match_required:none"
