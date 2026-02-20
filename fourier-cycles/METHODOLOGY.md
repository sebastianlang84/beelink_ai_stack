# fourier-cycles Methodik (verbindliche Spezifikation)

Ziel: Perioden im Band `FOURIER_MIN_PERIOD_DAYS..FOURIER_MAX_PERIOD_DAYS` reproduzierbar finden und je Periode klar trennen in:
- absolute Kennzahlen (Amplitude, SNR, Presence, Phase-Coherence, p-value)
- relative Rangmetrik (nur Sortierung)

## 1) Daten und Preprocessing

## 1.1 Sampling
- Eingang: Yahoo/FRED Zeitreihe `levels(t)`.
- Zeitfilter: `start_date = end_date - FOURIER_TIMEFRAME_DAYS`.
- Resampling: `FOURIER_RESAMPLE_RULE` via `last().ffill()`.
- Mindestlaenge: `FOURIER_MIN_POINTS`.

## 1.2 Signalmodus
Signalmodus ist quellenabhaengig konfigurierbar:
- Yahoo: `FOURIER_SIGNAL_MODE_YAHOO`
- FRED: `FOURIER_SIGNAL_MODE_FRED`

Erlaubte Modi:
- `log_returns`: `diff(log(levels))` (bei nicht-positiven Werten Fallback auf `pct_change`)
- `pct_change`: `levels.pct_change()`
- `diff`: `levels.diff()`
- `log_level`: `log(levels)` (nur bei strikt positiven Werten)
- `level`: `levels`

## 1.3 Detrending und Standardisierung
- Optionales Detrending: `y = x - rolling_mean(x, L)` mit `L = FOURIER_DETREND_ROLLING_DAYS`.
- Standardisierung: `z = (y - mean(y)) / std(y)` (bei `std=0`: nur Mean-Abzug).
- Leckage-Reduktion: Hanning-Fenster auf das finale Signal.

## 2) Spektrum und Kandidaten

## 2.1 Spektrum
- FFT-Periodogramm auf dem finalen Signal.
- Frequenzmaske: nur `f > 0` und `period_days = 1/f` im Zielband.
- Spektrumspalten:
  - `freq_per_day`
  - `period_days`
  - `power`
  - `norm_power` (auf Summe im Zielband normiert)

## 2.2 Kandidatenfindung
- Lokale Peaks im `power`-Verlauf (nach `period_days` sortiert).
- Kandidatenabstand im Periodenraum: mindestens 10% (interne Discovery-Regel), um Duplikate zu reduzieren.
- Fallback: Top-Power-Bins, falls Peak-Finder leer bleibt.

## 3) Rolling Robustness je Kandidatenperiode P

## 3.1 Fensterdesign
- Fensterlaengen aus `FOURIER_ROLLING_WINDOWS_DAYS` (CSV, z. B. `360,720,1260`).
- Schrittweite `FOURIER_ROLLING_STEP_DAYS`.
- Fenster werden in Signalpunkten aus `step_days` abgeleitet.

## 3.2 Band-Metrik pro Fenster
Fuer Kandidatenfrequenz `f0 = 1/P`:
- Peak-Bandhalbbreite:
  - `max(local_step*1.5, f0 * FOURIER_SNR_PEAK_BANDWIDTH_RATIO)`
- Background-Ring:
  - aeusseres Band: `f0 * FOURIER_SNR_BACKGROUND_BANDWIDTH_RATIO`
  - Exclusion um Peak: `f0 * FOURIER_SNR_BACKGROUND_EXCLUSION_RATIO`

Metriken:
- `band_power_ratio = band_power / total_power`
- `snr = band_power / expected_background_power`
  - `expected_background_power = median(ring_power) * n_band_bins`

## 3.3 Harmonic Regression (phase-invariant Fit)
Modell pro Fenster:
- `y_t = c + a*cos(w t) + b*sin(w t) [+ d*t]`
- `w = 2*pi/P`
- Trendterm aktiv, wenn `FOURIER_HARMONIC_INCLUDE_TREND=true`.

Abgeleitete Groessen:
- `amplitude = sqrt(a^2 + b^2)`
- `phase = atan2(-b, a)`
- `best_lag_days = (phase / (2*pi)) * P`
- `fit_score_phase_free = R^2` aus OLS-Fit

## 3.4 Presence pro Fenster
Ein Fenster zaehlt als `present`, wenn beides gilt:
- `snr >= FOURIER_SNR_PRESENCE_THRESHOLD`
- `band_power_ratio >= FOURIER_MIN_WINDOW_POWER_RATIO`

Aggregiert je Kandidat:
- `presence_ratio = mean(present)`
- `median_window_power_ratio = median(band_power_ratio)`
- `margin_median = median(snr - FOURIER_SNR_PRESENCE_THRESHOLD)`

## 3.5 Phase-Coherence
- `phase_locking_r = |mean(exp(i*phase_w))|`, Wertebereich `[0,1]`.
- Interpretation:
  - nahe 1: Phase ueber Fenster konsistent
  - nahe 0: starke Phasendrift

## 4) Absolute Kennzahlen je Periode

Pro Kandidat werden ausgegeben:
- Amplitude: `amp_median`, `amp_p25`, `amp_min`
- Fit: `fit_score_phase_free` (Median-R2)
- SNR: `snr_global`, `snr_median`, `snr_p25`
- Lag: `best_lag_days_median`, `lag_iqr`
- Robustness: `presence_ratio`, `margin_median`, `phase_locking_r`

Zusatz (legacy-kompatibel):
- `stability_score = presence_ratio * norm_power`
- `stability_score_norm` (nur relatives Normalisat)

## 5) Signifikanz (Band-Maximum Surrogate Test)

Wenn `FOURIER_SURROGATE_COUNT > 0`:
- Erzeuge pro Surrogate ein phase-randomized Signal (FFT-Magnitude bleibt, Phasen zufaellig).
- Berechne pro Surrogate den maximalen Kandidaten-SNR im Zielband.
- `p_value_bandmax` je Kandidat:
  - Anteil der Surrogates, deren Band-Max-SNR >= beobachteter Kandidaten-SNR (`snr_global`).

Konfiguration:
- `FOURIER_SURROGATE_COUNT`
- `FOURIER_SURROGATE_SEED`

## 6) Relative Rangmetrik (nur Sortierung)

Relative UI/Selection-Rangmetrik:
- `rank_score = w_amp*z(log1p(amp_median)) + w_snr*z(log1p(snr_median)) + w_presence*z(presence_ratio) + w_phase*z(phase_locking_r)`
- Gewichte:
  - `FOURIER_RANK_WEIGHT_AMP`
  - `FOURIER_RANK_WEIGHT_SNR`
  - `FOURIER_RANK_WEIGHT_PRESENCE`
  - `FOURIER_RANK_WEIGHT_PHASE`
- Normiert fuer UI:
  - `rank_score_norm` in `[0,1]`

Hinweis: `rank_score_norm` ist explizit relativ pro Serie/Run.

## 7) Auswahlregeln fuer Top-Cycles

Ein Kandidat ist fuer finale Auswahl (`selected_cycles`) nur eligible, wenn alle Bedingungen gelten:
- `stable = presence_ratio >= FOURIER_MIN_PRESENCE_RATIO`
- `presence_ratio >= FOURIER_SELECTION_MIN_PRESENCE_RATIO`
- `phase_locking_r >= FOURIER_SELECTION_MIN_PHASE_LOCKING_R`
- `amp_median >= FOURIER_SELECTION_MIN_AMP_SIGMA`
- `p_value_bandmax <= FOURIER_SELECTION_MAX_P_VALUE_BANDMAX`
  - Default aktuell `1.00` (Signifikanzfilter nicht hart aktiv); fuer strenge Signifikanz typischerweise `0.05`.

Optionaler Zusatzfilter:
- Norm-Power-Quantil ueber `FOURIER_SELECTION_MIN_NORM_POWER_PERCENTILE` (legacy-kompatibel).

Ranking und Diversifikation:
- Sortierung nach `rank_score_norm` (absteigend), dann Presence/Phase/SNR.
- Mindestabstand zwischen finalen Perioden:
  - `FOURIER_SELECTION_MIN_PERIOD_DISTANCE_RATIO`

Top-K:
- maximal `FOURIER_SELECTION_TOP_K`.

## 8) Output-Schema

`cycles.csv` enthaelt je stabile Periode:
- `period_days`, `freq_per_day`, `power`, `norm_power`
- `amp_median`, `amp_p25`, `amp_min`
- `fit_score_phase_free`
- `snr_median`, `snr_p25`, `snr_global`
- `best_lag_days_median`, `lag_iqr`
- `presence_ratio`, `margin_median`, `phase_locking_r`
- `p_value_bandmax`
- `rank_score`, `rank_score_norm`
- `median_window_power_ratio`
- `stability_score`, `stability_score_norm`
- `stable`

`summary.json` (je Serie) enthaelt:
- Konfigurationsnahe Selektionsparameter
- `selected_cycles` (finale Auswahl)

## 9) Semantik (wichtig)
- Absolute Aussage: SNR/Presence/Phase-Coherence/p-value/Amplitude.
- Relative Aussage: `rank_score_norm`, `stability_score_norm`.
- `1.0` in relativen Metriken bedeutet nur "bester Kandidat im aktuellen Pool", nicht "physikalisch perfekter Zyklus".
