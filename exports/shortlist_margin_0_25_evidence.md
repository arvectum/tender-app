# Evidence for shortlist_margin_0_25

## Scanned procurement pages (zakupki.mos.ru API snapshots)
- page 1: https://old.zakupki.mos.ru/api/Cssp/Purchase/Query?queryDto=%7B%22page%22%3A%201%2C%20%22size%22%3A%2040%2C%20%22stateName%22%3A%20%22%D0%9E%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%BE%22%7D (records_count=5000)
- page 2: https://old.zakupki.mos.ru/api/Cssp/Purchase/Query?queryDto=%7B%22page%22%3A%202%2C%20%22size%22%3A%2040%2C%20%22stateName%22%3A%20%22%D0%9E%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%BE%22%7D (records_count=5000)
- page 3: https://old.zakupki.mos.ru/api/Cssp/Purchase/Query?queryDto=%7B%22page%22%3A%203%2C%20%22size%22%3A%2040%2C%20%22stateName%22%3A%20%22%D0%9E%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%BE%22%7D (records_count=5000)
- page 4: https://old.zakupki.mos.ru/api/Cssp/Purchase/Query?queryDto=%7B%22page%22%3A%204%2C%20%22size%22%3A%2040%2C%20%22stateName%22%3A%20%22%D0%9E%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%BE%22%7D (records_count=5000)
- page 5: https://old.zakupki.mos.ru/api/Cssp/Purchase/Query?queryDto=%7B%22page%22%3A%205%2C%20%22size%22%3A%2040%2C%20%22stateName%22%3A%20%22%D0%9E%D0%BF%D1%83%D0%B1%D0%BB%D0%B8%D0%BA%D0%BE%D0%B2%D0%B0%D0%BD%D0%BE%22%7D (records_count=5000)

## External market offers checked (non-zakupki domains)
- purchase 10208353: https://standonline.ru/catalog/stendy_po_tematikam/grazhdanskaya_oborona/9002/ [standonline.ru] tender=2790.0 market=1823.0
- purchase 10208353: https://standonline.ru/catalog/stendy_po_tematikam/pozharnaya_bezopasnost/8113/ [standonline.ru] tender=2790.0 market=1823.0
- purchase 10208353: https://standonline.ru/catalog/stendy_dlya_organizatsiy/vooruzhennye_sily/13774/ [standonline.ru] tender=2790.0 market=2916.0
- purchase 10208351: https://lider-ic.ru/shop/armature-sip-of-04-1-kv/junction-clamps-04-1-kv/sealed-junction-clamps-04-1-kv/sealed-junction-clamps-for-insulated-conductors-of-04-1-kv/sliw50-piercing-clamp-alcu-10-50-mm2-alcu-15-10-mm2-sealed/ [lider-ic.ru] tender=320.0 market=209.0
- purchase 10208351: https://ekf.market/catalog/products/plc-jxb-10-35gy/ [ekf.market] tender=320.0 market=67.0

## Result
- Candidates in margin range [0,25]: 0
- Reason: all computed margins were either >25% or negative for collected external offers.