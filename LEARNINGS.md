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

## 30.10.2026 – Erster Gegenentwurf: Rücksetzer im Aufwärtstrend kaufen (`scripts/backtest_pullback.py`)

Regel: Kurs über der 200-Tage-Linie, RSI(2) unter 5 bzw. 10 → Kauf zur nächsten Eröffnung.
Verkauf beim ersten Schlusskurs über der 5-Tage-Linie, Stop 2–3 ATR, spätestens nach 5–7 Tagen.
2 Jahre Tageskurse, 90 Aktien/ETFs und 12 Coins, inklusive 0,04 % Spread je Seite.

| Variante | Trades | Treffer | Schnitt | Haltedauer |
|---|---|---|---|---|
| Aktien, RSI2 < 5, Stop 2 ATR | 443 | 67 % | +0,11 R | 3 Tage |
| Aktien, RSI2 < 10, Stop 2 ATR | 869 | 66 % | +0,08 R | 3 Tage |
| Krypto, RSI2 < 5, Stop 2 ATR | 50 | 70 % | +0,10 R | 3 Tage |

**Einordnung:** Diese Strategie ist im Plus, im Gegensatz zur Intraday-Strategie (−0,18 R). Der Vorteil pro Trade
ist aber klein, und der Test hat Schwächen: Die Aktienliste besteht aus heutigen Gewinnern (Überlebens-Verzerrung),
und die Werte wurden nicht an einem getrennten Zeitraum geprüft. Nächster Schritt: Prüfung an getrennten Zeiträumen
und mit einer breiteren Aktienliste, danach Paper-Handel mit normalem Risiko.

## 04.11.2026 – Test-Konto (ohne Challenge-Regeln, 5x Hebel)

| Trade | Stop-Abstand | Ergebnis |
|---|---|---|
| SUI Long | 0,73 % | +0,44 $ |
| AVAX Long | 0,52 % | +5,67 $ |
| SOL Long | 0,34 % | −10,80 $ (−1,26 R, nach 3 Minuten) |

**Erkenntnis:** Der einzige Verlust hatte den engsten Stop. Bei 0,34 % reicht normales Rauschen, und Spread plus
Ausführung kosten rund ein Viertel des Risikos (daher −1,26 R statt −1 R). Passt zum Rückblick-Test vom 30.10.
→ Stop jetzt mindestens 0,6 % vom Einstieg (`bot/dips.py`, `config_free.yaml`).

**Abgelehnter PLTR-Short (korrigiert):** Ursache war ein Fehler im Bot, nicht ein veraltetes Signal. Die Befehlszeile
übergab die Seite (long/short) an der falschen Stelle, dadurch wurde jeder Short als ungültiger Long abgelehnt.
Behoben, mit Test über die Befehlszeile (`test_cli_places_short_order`).

**Aufgefallen (SOL-Rally 15:30):** Die Rücksetzer-Regel steigt in steile Anstiege nicht ein, weil RSI(2) nie unter 25 fällt.
→ Trend-Rücksetzer ergänzt: bei Kurs ≥ 0,3 % über/unter EMA 50 reicht RSI(2) < 40 bzw. > 60. Noch nicht im Rückblick getestet.

## 07.11.2026 – Auswertung der 17 Test-Trades vom 4.11. (Ergebnis −47,78 $)

| Einstieg | Trades | Ergebnis |
|---|---|---|
| RSI(2) 37–43 (gelockert für „mehr Trades“) | 5 | **alle im Minus**: AMD −33,32, ANET −33,46, SUI −13,58, XRP −11,05, AMZN −0,34 |
| RSI(2) unter 25 (tiefer Rücksetzer) | 9 | netto im Plus (COIN +20,59, AVAX +5,67, …; SOL −10,80 wegen zu engem Stop) |
| Ausstieg bei ±0 durch Break-even ab +0,3 R | 5 | QQQ, ANET, MSFT, TSLA: Trades beendet, bevor sie laufen konnten |

**Rückblick-Test Krypto, 7 Tage, 5-Min-Kerzen** (`scripts/backtest_crypto_dips.py`):

| Schwelle | Long | Short |
|---|---|---|
| RSI(2) < 10 bzw. > 90 | −0,26 R, 192 Trades | −0,15 R, 210 Trades |
| RSI(2) < 25 bzw. > 75 | −0,24 R, 587 Trades | −0,18 R, 685 Trades |
| RSI(2) < 40 bzw. > 60 | −0,23 R, 1.013 Trades (Summe −66 %) | −0,23 R, 1.126 Trades (Summe −87 %) |

**Erkenntnisse:**
1. Lockerere Einstiege bringen mehr Trades und vor allem mehr Verlust. „Viele Trades“ und „keine Verluste“ widersprechen sich.
2. Zurück zu extremen Rücksetzern: RSI(2) < 10 / > 90, keine gelockerten Trend-Einstiege.
3. Break-even erst ab +0,6 R (statt 0,3 R), Nachziehen ab +1 R mit 0,6 R Abstand.
4. Auch so ist die Strategie im Rückblick nach Kosten im Minus; der Test zeigt, wie viel.

## 08.11.2026 – Lauf bei GitHub, 7.11. 23:45 bis 8.11. 11:00 (Start 952,22 $, Ende 950,61 $)

- **Nur 1 Trade:** LINK Short (RSI2 88,6), 8 Stunden gehalten, zum Ende geschlossen: −1,61 $.
- **GitHub hat statt alle 5 Minuten nur 15-mal in 11 Stunden gestartet** (etwa alle 45–50 Minuten). Geplante Abläufe
  werden bei GitHub gedrosselt. Für viele Trades reicht das nicht; ein durchgehender Ablauf (z. B. auf einem eigenen
  Rechner oder Server) prüft jede Minute.
- **Zielkonflikt bestätigt:** Mindestrisiko 80 $ + strenge Einstiege (RSI2 < 15 / > 85) + Wochenende (nur Krypto)
  ergeben sehr wenige Trades. Viele Trades gehen nur mit lockereren Regeln, und die verlieren laut Rückblick mehr.
