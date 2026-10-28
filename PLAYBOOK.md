# Tagesroutine für den Claude-Bot

Diese Routine führt Claude an jedem US-Handelstag aus. Alle Befehle laufen im Projektordner.

## Feste Regeln
- `data/state.json` niemals von Hand ändern. Nur der Bot schreibt diese Datei.
- `config.yaml` während einer laufenden Challenge nicht lockern.
- Lehnt der Risiko-Wächter einen Trade ab, wird er nicht umgangen: kein Wechsel auf einen anderen Typ, keine erfundenen Zahlen.
- Kein guter Trade bedeutet keinen Trade. Cash ist eine gültige Position.

## Ablauf (ab 9:00 Uhr New York, vor der Eröffnung)
1. **Stand holen:** `python3 -m bot update`. Ist der Status nicht `ACTIVE`, endet die Routine hier mit einer Meldung.
2. **Marktumfeld prüfen** (Skills ohne API-Key):
   - `market-breadth-analyzer` und `uptrend-analyzer`.
   - Bei Score unter 40 in beiden oder Regime `risk-off`: **keine neuen Trades heute.**
   - Bei gemischtem Bild höchstens 1 neuer Trade.
3. **Kandidaten suchen:** `python3 -m bot scan`.
4. **Prüfen:** Die 1–2 besten Kandidaten ansehen:
   - Bevorzugt Kandidaten mit Kontraktion < 1,0 und relativer Stärke > 0.
   - Kein Trade, wenn in den nächsten 5 Tagen Quartalszahlen anstehen (WebSearch).
   - Möglichst nicht zwei Kandidaten aus demselben Sektor.
   - Stop unter einer echten Unterstützung, Ziel mindestens 3R.
5. **Platzieren:** `python3 -m bot propose SYMBOL --entry X --stop Y --target Z --reason "..."`
   - Mit `--type stop` (Standard) kauft der Bot erst beim Ausbruch über `entry`.
   - Die Begründung kurz und konkret in `--reason` schreiben.
6. **Bericht:** `python3 -m bot status --events 10` als kurze Zusammenfassung auf Deutsch: Kontostand, Abstand zu Ziel und Grenze, neue Orders mit Begründung, geschlossene Trades.
7. **Sichern:** `data/` committen und pushen.

## Ablauf (nach 16:00 Uhr New York)
1. `python3 -m bot update`
2. Kurzer Tagesbericht; geschlossene Trades in einem Satz bewerten (Plan eingehalten?).
3. Committen und pushen.
