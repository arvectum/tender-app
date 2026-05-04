# BUSINESS_RULES

- Источник по умолчанию: `.env`.
- Override: таблица `business_rules` через `/settings/business-rules`.
- После изменения правил выполняйте:
  - `python -m app.cli rematch-offers --all`
  - `python -m app.cli recalculate --all --with-attributes`
  - `python -m app.cli evaluate`
