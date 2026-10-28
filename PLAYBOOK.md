# Tagesroutine für den Claude-Bot

Diese Routine führt Claude an jedem US-Handelstag aus. Alle Befehle laufen im Projektordner.

## Feste Regeln
- `data/state.json` niemals von Hand ändern. Nur der Bot schreibt diese Datei.
- `config.yaml` während einer laufenden Challenge nicht lockern.
- Lehnt der Risiko-Wächter einen Trade ab, wird er nicht umgangen: kein Wechsel auf einen anderen Typ, keine erfundenen Zahlen.
- Kein guter Trade bedeutet keinen Trade. Cash ist eine gültige Position.

## Vorbereitung (frischer Container)
`./scripts/setup.sh` installiert Python-Pakete und die Trading-Skills.

## Ablauf (ab 8:45 Uhr New York, vor der Eröffnung)
1. **Stand holen:** `python3 -m bot update`. Ist der Status nicht `ACTIVE`, endet die Routine hier mit einer Meldung.
2. **Marktumfeld prüfen** (Skills ohne API-Key):
   - `market-breadth-analyzer` und `uptrend-analyzer`.
   - Bei Score unter 40 in beiden oder Regime `risk-off`: **keine neuen Trades heute.**
   - Bei gemischtem Bild höchstens 1 neuer Trade.
   - **Krypto:** `crypto-regime-analyzer`. Bei `RISK_OFF` oder Score unter 40: kein neuer Krypto-Trade.
3. **Kandidaten suchen:** `python3 -m bot scan` (Aktien und Krypto; nur eins: `--market stocks` oder `--market crypto`).
4. **Prüfen:** Die 1–2 besten Kandidaten ansehen:
   - Bevorzugt Kandidaten mit Kontraktion < 1,0 und relativer Stärke > 0.
   - Kein Trade, wenn in den nächsten 5 Tagen Quartalszahlen anstehen (WebSearch).
   - Möglichst nicht zwei Kandidaten aus demselben Sektor.
   - Krypto: höchstens 1 Position (der Wächter erzwingt das). Kein Krypto-Einstieg in den 24 Stunden vor FOMC- oder CPI-Terminen.
   - Krypto-Symbole: `BTC`, `SOL`, `ETH` usw. werden automatisch zu `BTC-USD` usw. Krypto-Orders gelten 24 Stunden.
   - Stop unter einer echten Unterstützung, Ziel mindestens 3R.
5. **Platzieren:** `python3 -m bot propose SYMBOL --entry X --stop Y --target Z --reason "..."`
   - Mit `--type stop` (Standard) kauft der Bot erst beim Ausbruch über `entry`.
   - Die Begründung kurz und konkret in `--reason` schreiben.
6. **Bericht:** `python3 -m bot status --events 10` als kurze Zusammenfassung auf Deutsch: Kontostand, Abstand zu Ziel und Grenze, neue Orders mit Begründung, geschlossene Trades.
7. **Dashboard aktualisieren** (siehe unten).
8. **Sichern:** `data/` committen und pushen.

## Wochenende (nur Krypto)
Wie der Ablauf vor der Eröffnung, aber nur `crypto-regime-analyzer` und `python3 -m bot scan --market crypto`.

## Ablauf (ab 16:20 Uhr New York, nach Börsenschluss)
1. `python3 -m bot update`
2. Kurzer Tagesbericht; geschlossene Trades in einem Satz bewerten (Plan eingehalten?).
3. Dashboard aktualisieren (siehe unten).
4. Committen und pushen.

## Dashboard aktualisieren
Dashboard: https://claude.ai/artifact/72Q5ku4zJy797kTdbDUjm6
1. `python3 -m bot export` schreibt `data/dashboard/{summary,equity,trades,candles}.json`.
2. Jede der vier Dateien einzeln mit dem Artifact-Tool hochladen (`asset: true`, `url` wie oben).
3. Für jede Datei das Dokument `datasets/<name>` lesen und mit `if_version` aktualisieren:
   `source.url` = neue `/_blob/...`-URL, `source.name` = Dateiname, `updated` = `{at: <jetzt ISO>, by: "Challenge-Bot (Claude)"}`.
4. Die Seite selbst (`files/index.html`) nicht ändern. Ihre Quelle liegt in `dashboard/index.html`.
