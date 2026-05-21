from __future__ import annotations

import csv
from pathlib import Path

from app.services.small_tender_report_service import build_single_file_manifest, generate_small_tender_report


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
