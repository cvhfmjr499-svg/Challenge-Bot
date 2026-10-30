# Was der Bot aus seinen Trades gelernt hat

## 30.10.2026 – Auswertung nach 5 Trades (3 Gewinner, +7,71 $)

**Verluste:**
- **AVGO −6,37 $ (Stop):** schwächstes Signal bisher (Score 0,02, Volumen 45 % vom Normalwert,
  Schwung +0,22 %/h), Einstieg mittags (13:31 Uhr New York).
- **TSLA −2,94 $ (manuell):** starkes Signal, Verlust kam durch einen manuellen Verkauf vor Stop oder Ziel.

**Rückblick-Test** (`scripts/backtest_intraday.py`): Der Intraday-Scanner wurde auf alle 5-Minuten-Kerzen
vom 21. bis 30.10. angewendet, 607 ausgeführte Signale, mit der Ziel-Regel des Bots.

| Gruppe | Trades | Schnitt brutto | Schnitt nach Kraken-Spread |
|---|---|---|---|
| Alle | 607 | −0,06 R | **−0,18 R** |
| Aktien mittags (11–13 Uhr NY) | 91 | −0,30 R | −0,42 R |
| Aktien ohne Mittag | 149 | +0,01 R | −0,11 R |
| Krypto | 367 | −0,03 R | −0,15 R |
| Viel Volumen + viel Schwung | 172 | −0,25 R | schlechter als der Rest |

**Erkenntnisse:**
1. Die Intraday-Ausbruchsstrategie hatte in diesen Tagen **keinen Vorteil**. Nach Kosten verliert sie
   im Schnitt etwa 0,18 R pro Trade. Die +7,71 $ bisher waren eher Glück als Können.
2. **Mittags keine Aktien-Einstiege** (11–13 Uhr NY): klar schlechter. → Im Scanner eingebaut.
3. „Stärkere“ Signale (mehr Volumen, mehr Schwung) waren **nicht** besser, eher schlechter
   (zu spät eingestiegen). Die Vermutung nach dem AVGO-Verlust hat sich nicht bestätigt.
4. Enge Stops (unter 1 %) werden von den Kosten stark belastet: 0,08 % Spread sind bei 0,5 % Stop schon 0,16 R.

**Grenzen:** nur 10 Tage, eine Marktphase, vereinfachte Simulation. Ein Ergebnis dieser Größe ist ein
Warnsignal, kein Beweis.
