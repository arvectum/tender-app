# ARCHITECTURE

- `app/connectors`: импорт закупок (mos_portal/eat).
- `app/price_search`: поиск и нормализация рыночных предложений.
- `app/matching`, `app/catalog`: match v2 и item attributes.
- `app/services/calculation_service.py`: себестоимость, налоги, маржа.
- `app/scoring`, `app/services/decision_service.py`: scoring v2, стратегии, решения.
- `app/scheduler`: регулярные jobs.
- `app/main.py`: dashboard + JSON API.
- `migrations/versions`: схема БД.
