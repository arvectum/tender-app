# Evidence for shortlist_margin_0_25

## Browser pages traversed (Playwright, anti-bot обход через реальный браузерный рендер)
- https://zakupki.mos.ru/ (status 200)
- https://zakupki.mos.ru/auction/10208353 (status 200)
- https://zakupki.mos.ru/auction/10208351 (status 200)
- https://agregatoreat.ru/ (status 200)
- https://agregatoreat.ru/purchases/announcement (status 200)

Artifacts:
- exports/page_scan/browser_scan_results.json
- exports/page_scan/browser_scan_1.png
- exports/page_scan/browser_scan_2.png
- exports/page_scan/browser_scan_3.png
- exports/page_scan/browser_scan_4.png
- exports/page_scan/browser_scan_5.png

## External market offers used (non-zakupki)
1) purchase 10208353
- item: Стенд ProfMarker Гражданская оборона ГО и ЧС 100х75 см
- tender price: 3485.00
- offer page: https://atis-ars.ru/category/stendy/grazdanskaya-oborona
- market price used: 3264.00
- margin_pct=((3485-3264)/3485*100)=6.34

2) purchase 10208353
- item: Стенд информационный Пожарная безопасность 900х740 мм 1 карман А4
- tender price: 2985.00
- offer page: https://e-kvadrat.ru/informacionnye-stendy-s-karmanami-a4-pozharnaya-bezopasnost
- market price used: 2975.00
- margin_pct=((2985-2975)/2985*100)=0.34

3) purchase 10208351
- item: Зажим прокалывающий Al/Cu 10-50 мм2 / Al/Cu 1.5-10 мм2
- tender price: 320.00
- offer page: https://ensnab24.ru/337290/
- market price used: 277.00
- margin_pct=((320-277)/320*100)=13.44

4) purchase 10208351
- item: Колодка клеммная EKF plc-jxb-10/35gy JXB-10/3 серая 70А 50 шт
- tender price: 3500.00
- offer page: https://materials.ru/products/kolodka-klemmnaya-jxb-10-35-seraya-ekf-proxima-plc-jxb-10-35gy
- market price used: 3000.00
- margin_pct=((3500-3000)/3500*100)=14.29

## Result
- shortlist rows with margin in [0,25]: 4
