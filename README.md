# Kraken Challenge-Bot (Paper)

Ein Paper-Trading-Bot für die Kraken-Funded-Challenge mit 1.000 $ Startkapital: bestanden bei **1.120 $ (+12 %)**, Verlustgrenze fest bei **970 $**. Danach handelt er in Phase 2 weiter bis 10.000 $.

**Live-Ansicht (Handy):** https://cvhfmjr499-svg.github.io/Challenge-Bot/

- **Claude** analysiert den Markt mit den Trading-Skills und schlägt Trades vor (siehe [PLAYBOOK.md](PLAYBOOK.md)).
- Der **Risiko-Wächter** (`bot/risk.py`) setzt die Challenge-Regeln als festen Code durch. Claude kann ihn nicht aushebeln.
- Gehandelt werden **US-Aktien/ETFs und Krypto** (BTC, ETH, SOL, XRP, BNB, DOGE, ADA, AVAX, LINK, LTC, DOT, SUI).
- Der **Paper-Broker** (`bot/engine.py`) führt Orders gegen echte 1-Minuten-Kerzen (yfinance) aus, rechnet Krakens Spread (0,04 %) ein und rechnet bewusst konservativ.
- **GitHub Actions** (`.github/workflows/bot-tick.yml`) rechnet alle 5 Minuten ab und schreibt die Daten für die Handy-Seite (`docs/`).

## Optional: Live-Ansicht auf dem PC (Windows, jede Minute statt alle 5 Minuten)
Einmalig einrichten:
1. Git installieren: in der Eingabeaufforderung `winget install --id Git.Git -e`, danach die Eingabeaufforderung neu öffnen.
2. Repo holen: `git clone https://github.com/cvhfmjr499-svg/Challenge-Bot C:\challenge-bot`
   (beim ersten Mal öffnet sich ein GitHub-Login im Browser).
3. Im Ordner `C:\challenge-bot` doppelt auf **`start-live.bat`** klicken.

Danach öffnet sich http://localhost:8765 im Browser:
- Krypto-Kurse ticken im Sekundentakt (Kraken), Aktien als 1-Minuten-Kerzen (Yahoo, leicht verzögert).
- Einstieg, Stop und Ziel als Linien, Käufe und Verkäufe als Pfeile, Live-Protokoll und Kontostand.
- Solange das Fenster offen ist, rechnet der Bot jede Minute Orders, Stops und Ziele ab und gleicht sich mit GitHub ab.

Wichtig: Den Ordner `C:\challenge-bot` nicht von Hand bearbeiten. Das Programm setzt ihn bei jedem Abgleich auf den Stand von GitHub zurück.

## Befehle
```bash
python3 -m bot init                 # neues Paper-Konto mit 1.000 $
python3 -m bot update               # Kurse holen, Orders/Stops/Ziele abarbeiten
python3 -m bot status --events 10   # Kontostand + letzte Ereignisse
python3 -m bot scan                 # Ausbruchs-Kandidaten (--market stocks|crypto)
python3 -m bot propose NVDA --entry 190.5 --stop 186 --target 204 --reason "..."  [--dry-run]
python3 -m bot cancel 3             # wartende Order stornieren
python3 -m bot close NVDA           # Position zur nächsten Kerze schließen
python3 -m bot live                 # Live-Ansicht + minütliche Abrechnung (--no-sync: ohne GitHub)
python3 -m bot export               # Daten fürs Claude-Dashboard
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
| Verlustgrenze | fest 970 $ (laut Kraken auch nach dem Bestehen); alle Stops zusammen dürfen sie nie erreichen |
| Ziel erreicht | alles schließen, weiter in Phase 2 (1 % Risiko, bis 3 Positionen, Ziel ≥ 2:1) bis 10.000 $ |

## Wie die Simulation rechnet
- Kauf beim Ausbruch per Stop-Limit: Liegt der Eröffnungskurs mehr als 0,3 % über dem Einstieg, gibt es keine Ausführung.
- Werden Stop und Ziel in derselben Kerze berührt, zählt der Stop.
- Eine Kurslücke unter den Stop wird zum (schlechteren) Eröffnungskurs ausgeführt.
- Ob die Verlustgrenze berührt wurde, wird an den Tiefs der Kerzen geprüft.
- Aktien-Orders gelten nur für den Tag (DAY), Krypto-Orders 24 Stunden.
- Krypto läuft rund um die Uhr: Auch Stops am Wochenende werden beim nächsten `update` nachträglich Kerze für Kerze abgerechnet.

## Offene Punkte
- Klären, ob Kraken Funded automatisches Handeln (Bot/API) erlaubt, bevor mit echtem Geld gestartet wird.
- Welche Aktien Kraken Funded in Deutschland anbietet.
