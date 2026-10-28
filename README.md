# $1K-Challenge Paper-Bot

Ein Paper-Trading-Bot für eine Challenge mit 1.000 $ Startkapital: Bestanden bei **1.120 $ (+12 %)**, durchgefallen bei **−3 %**.

- **Claude** analysiert den Markt mit den Trading-Skills und schlägt Trades vor (siehe [PLAYBOOK.md](PLAYBOOK.md)).
- Der **Risiko-Wächter** (`bot/risk.py`) setzt die Challenge-Regeln als festen Code durch. Claude kann ihn nicht aushebeln.
- Gehandelt werden **US-Aktien/ETFs und Krypto** (BTC, ETH, SOL, XRP, BNB, DOGE, ADA, AVAX, LINK, LTC, DOT, SUI).
- Der **Paper-Broker** (`bot/engine.py`) führt Orders gegen echte 5-Minuten-Kerzen (yfinance) aus und rechnet dabei bewusst konservativ.

## Befehle
```bash
python3 -m bot init                 # neues Paper-Konto mit 1.000 $
python3 -m bot update               # Kurse holen, Orders/Stops/Ziele abarbeiten
python3 -m bot status --events 10   # Kontostand + letzte Ereignisse
python3 -m bot scan                 # Ausbruchs-Kandidaten (--market stocks|crypto)
python3 -m bot propose NVDA --entry 190.5 --stop 186 --target 204 --reason "..."  [--dry-run]
python3 -m bot cancel 3             # wartende Order stornieren
python3 -m bot close NVDA           # Position zur nächsten Kerze schließen
python3 -m pytest -q                # Regel-Tests
```

## Was der Risiko-Wächter durchsetzt
| Regel | Wert |
|---|---|
| Risiko pro Trade | max. 0,75 % (7,50 $), höchstens die Hälfte des freien Puffers |
| Chance/Risiko | mindestens 1:3 |
| Gleichzeitig offen | max. 2 Positionen/Orders, davon max. 1 Krypto |
| Positionsgröße | max. 60 % des Kontos |
| Stop-Abstand | 0,5–6 % |
| Pause | nach 2 Verlusten in Folge oder 15 $ Tagesverlust: Rest des Tages |
| Trailing Drawdown | Grenze = Höchststand − 30 $; Stops werden automatisch nachgezogen, damit alle Stops zusammen die Grenze nicht erreichen können |
| Ziel erreicht | alles schließen, Challenge bestanden |

## Wie die Simulation rechnet
- Kauf beim Ausbruch per Stop-Limit: Liegt der Eröffnungskurs mehr als 0,3 % über dem Einstieg, gibt es keine Ausführung.
- Werden Stop und Ziel in derselben Kerze berührt, zählt der Stop.
- Eine Kurslücke unter den Stop wird zum (schlechteren) Eröffnungskurs ausgeführt.
- Ob die Verlustgrenze berührt wurde, wird an den Tiefs der Kerzen geprüft.
- Aktien-Orders gelten nur für den Tag (DAY), Krypto-Orders 24 Stunden.
- Krypto läuft rund um die Uhr: Auch Stops am Wochenende werden beim nächsten `update` nachträglich Kerze für Kerze abgerechnet.

## Offene Punkte
- Echte Challenge-Regeln bestätigen: Ist der Drawdown wirklich mitwandernd? Gibt es ein Zeitlimit? Welche Instrumente sind erlaubt?
- Alpaca-Paper-Anbindung, sobald API-Keys vorhanden sind.
