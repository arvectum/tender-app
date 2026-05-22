# Active goods strict-match coverage

Generated at: `2026-05-22T18:39:58.747350`

## Data sources used
- `exports/small_tender_tender_ref_auction_prod.csv` (mtime: `2026-05-22T10:31:33.593818`)
- `exports/small_tender_report_auction_prod.csv` (mtime: `2026-05-22T12:26:44.994646`)

## Freshness / rerun note
Повторный прогон pipeline не выполнялся: использованы уже актуальные артефакты текущего прогона (дата модификации файлов выше), чтобы не дублировать сетевой обход.

## Method
- Denominator (`total_active_goods_purchases`): количество уникальных `purchase_external_id` из `small_tender_tender_ref_auction_prod.csv`.
- Numerator (`matched_purchases_count`): количество уникальных закупок из этого множества, где в `small_tender_report_auction_prod.csv` есть хотя бы одна строка с `strict_full_match=True`.
- Coverage: `matched_purchases_count / total_active_goods_purchases * 100`.

## Result
- total_active_goods_purchases: **5**
- matched_purchases_count: **0**
- coverage_pct: **0.00%**

## Purchase IDs
- Active goods purchases: `10208336, 10208351, 10208352, 10208353, 10208354`
- Strict-match purchases: `(none)`
