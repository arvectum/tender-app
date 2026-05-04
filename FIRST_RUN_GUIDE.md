# FIRST RUN GUIDE

## 1) Запустить demo

```bash
python -m app.cli env init --mode demo
python -m app.cli doctor
python -m app.cli init-db
python -m app.cli seed-demo
python -m app.cli run-dashboard
```

Dashboard: `http://127.0.0.1:8000`  
Demo login: `admin / AdminDemo123!`

## 2) Загрузить реальные закупки (безопасно)

```bash
python -m app.cli env init --mode production
# в .env: REAL_NETWORK_ENABLED=true, REAL_RUN_MODE=true, DATABASE_URL=postgresql+...
python -m app.cli doctor
python -m app.cli real-source-check --source mos_portal --limit 5
python -m app.cli run-real-pipeline --dry-run
```

## 3) Внести цены через Excel template

```bash
python -m app.cli export-offer-template --file data/manual_offers_template.xlsx
# заполнить файл цен
python -m app.cli import-offers --file data/manual_offers.xlsx
```

## 4) Получить результат

```bash
python -m app.cli validate-data
python -m app.cli financial-check
python -m app.cli calculate
python -m app.cli evaluate
python -m app.cli export-excel
```

Файл результата: `exports/tender_small_volume_export.xlsx`

## 5) На что смотреть

- `decision` и `decision_status` (`needs_review` требует ручного подтверждения)
- `risk_level`
- `data_quality`
- `next_action`
- `explanation_summary`
