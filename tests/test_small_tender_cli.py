from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

os.environ["APP_MODE"] = "demo"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,.zakupki.mos.ru,zakupki.mos.ru,api.zakupki.mos.ru,.agregatoreat.ru,agregatoreat.ru"
os.environ["no_proxy"] = os.environ["NO_PROXY"]

from app.cli import cli


runner = CliRunner()


def test_small_tender_manifest_cli(tmp_path: Path) -> None:
    source_csv = tmp_path / "source.csv"
    source_csv.write_text("purchase_external_id,item_name\nP1,abc\nP2,def\n", encoding="utf-8")
    attachment = tmp_path / "tz.txt"
    attachment.write_text("demo", encoding="utf-8")
    out_manifest = tmp_path / "manifest.csv"

    result = runner.invoke(
        cli,
        [
            "small-tender-manifest",
            "--source-csv",
            str(source_csv),
            "--attachment-path",
            str(attachment),
            "--out-manifest-csv",
            str(out_manifest),
        ],
    )

    assert result.exit_code == 0
    assert out_manifest.exists()
    assert "Manifest generated" in result.stdout


def test_small_tender_report_cli(tmp_path: Path) -> None:
    market_csv = tmp_path / "market.csv"
    market_csv.write_text("purchase_external_id,item_name,offer_title,unit_price\nP1,Huawei S5735S,Huawei S5735S,90\n", encoding="utf-8")
    ref_csv = tmp_path / "ref.csv"
    ref_csv.write_text("purchase_external_id,unit_price\nP1,100\n", encoding="utf-8")

    manifest_csv = tmp_path / "manifest.csv"
    tz_txt = tmp_path / "tz.txt"
    tz_txt.write_text("Huawei S5735S", encoding="utf-8")
    manifest_csv.write_text(f"purchase_external_id,attachment_path\nP1,{tz_txt}\n", encoding="utf-8")

    out_csv = tmp_path / "report.csv"
    out_xlsx = tmp_path / "report.xlsx"
    diag_csv = tmp_path / "diag.csv"

    result = runner.invoke(
        cli,
        [
            "small-tender-report",
            "--market-csv",
            str(market_csv),
            "--tender-ref-csv",
            str(ref_csv),
            "--attachments-manifest-csv",
            str(manifest_csv),
            "--out-csv",
            str(out_csv),
            "--out-xlsx",
            str(out_xlsx),
            "--diagnostics-csv",
            str(diag_csv),
        ],
    )

    assert result.exit_code == 0
    assert out_csv.exists()
    assert out_xlsx.exists()
    assert diag_csv.exists()
    assert "Small tender report generated" in result.stdout
