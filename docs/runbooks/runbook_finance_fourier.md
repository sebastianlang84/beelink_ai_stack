# Runbook - Finance Fourier Analysis (Yahoo + FRED)

Ziel: Zeitreihen aus Yahoo Finance oder FRED laden und eine einfache Fourier-Spektrumanalyse auf den Daten ausfuehren.

Script: `scripts/finance_fourier_analysis.py`

## Voraussetzungen
- Python 3 auf dem Host.
- Internet-Zugriff.
- Keine API-Keys notwendig (Yahoo Chart API + FRED CSV Endpoint).

## Schnellstart
Yahoo (SPY, 5 Jahre):

```bash
./scripts/finance_fourier_analysis.py \
  --source yahoo \
  --symbol SPY \
  --yahoo-range 5y \
  --max-points 512 \
  --top-k 8
```

FRED (10Y Treasury Yield):

```bash
./scripts/finance_fourier_analysis.py \
  --source fred \
  --series-id DGS10 \
  --max-points 512 \
  --top-k 8
```

## Nuetzliche Parameter
- `--start-date YYYY-MM-DD` und `--end-date YYYY-MM-DD`: Datumsfenster einschraenken.
- `--transform raw|returns|log_returns`: Signaldefinition (Default: `log_returns`).
- `--window none|hann`: Fensterung vor DFT (Default: `hann`).
- `--max-points`: Nur die letzten N Datenpunkte verwenden (Default: 1024).
- `--min-points`: Mindestlaenge des Signals (Default: 128).
- `--top-k`: Anzahl der Top-Zyklen im Terminal und Report (Default: 10).

## Artefakte
Jeder Lauf schreibt nach:

`output/finance-fourier/<timestamp>-<source>-<series>/`

Dateien:
- `series.csv` - Rohzeitreihe.
- `signal.csv` - transformiertes/preprocessed Signal.
- `spectrum.csv` - komplettes Spektrum (positive Frequenzen).
- `report.md` - kompakte Zusammenfassung mit Top-Zyklen.

## Interpretation
- `period_days` ist die dominante Zykluslaenge in Tagen (approximiert ueber medianen Zeitschritt).
- Hohe `power` bedeutet starker periodischer Anteil im analysierten Signal.
- Bei Finanzdaten tauchen oft kurze Zyklen (2-10 Beobachtungen) auf; diese sind haeufig Marktmikrostruktur-/Kalendereffekte und nicht automatisch prognosefaehig.

## Grenzen
- Implementierung nutzt eine einfache DFT (O(N^2)) fuer moderate Datenmengen.
- Keine statistische Signifikanzpruefung, kein Forecast-Modell.
- Trading-Kalender/Feiertage werden nur ueber medianen Zeitschritt approximiert.

## Naechste Iteration (optional)
- Lomb-Scargle fuer unregelmaessige Zeitachsen.
- Signifikanztests/Bootstrapping fuer Peak-Robustheit.
- Vergleich mehrerer Assets/Serien in einem Batch-Runner.
