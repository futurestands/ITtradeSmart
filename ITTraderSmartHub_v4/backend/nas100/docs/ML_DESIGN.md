# Technical design: trainable NAS100 setup-quality model (future phase)

**Status: design only. No model exists, no training has been run, and no performance is
claimed. No win rate or profitability is promised or implied.** Prerequisite: the
deterministic engine (this package) validated on real data.

## 1. Role of the model
The model does **not** originate trades. It scores setups the rule engine already produced
(sweep -> structure shift -> open FVG) to estimate whether net outcomes after costs are
better than the base rate for that setup type. It may filter or rank; it can never override the
risk layer, session/data-quality blockers or the infrastructure-stress ceiling.
Until the acceptance gates in section 7 pass, the app shows setups as "rule-based, unvalidated".

## 2. Data required (missing today)
* USTECH100M M1 (preferably) or M5 OHLC with per-bar spread, covering several years and
  multiple regimes (trend, range, high-vol shocks). Check actual depth with `copy_rates_range`;
  demo servers often hold limited history. Tick data for entry-fill realism if available.
* `symbol_info` history (contract specs change), broker server-time/DST rules, trading-session
  breaks, index-CFD roll/adjustment treatment.
* Commission/spread/slippage assumptions per session.
* An optional scheduled-economic-events calendar with documented licensing and
  as-of publication times; do not assume historical revised values were known at t0.
* Licensing: use only data the broker/provider permits for this purpose.

## 3. Observations and labels (triple barrier, causal)
Unit = one engine setup at its decision candle t0 (all features from candles closed at t0).
* Entry: limit at FVG midpoint, **filled only if a later candle trades through it** within
  `max_wait` bars; unfilled setups get label "no_fill" and are excluded from outcome training
  but counted (fill rate is itself a result).
* Barriers: engine stop, engine target, and a time barrier `max_hold` (e.g. 48 M5 bars).
* If stop and target are both inside one candle, assume **stop first** (conservative).
* Label: net R-multiple after spread + commission + a slippage assumption; classification
  target `net_R > 0` (and keep net R for regression/expectancy). Timeout exits are marked to
  market at the time barrier.
* Sample-overlap: each label spans t0..exit; record `t_exit` for purging (section 5).

## 4. Features (all computed at t0, stationary, no raw price levels)
Structure: LTF/HTF trend state, bars since last BOS/CHoCH, BOS/CHoCH counts in a window,
swing-label sequence; sweep depth and wick ratio in ATR; displacement size in ATR; FVG size
in ATR, distance price-to-zone, depth of retracement into zone; distance to stop/target in ATR;
planned RR. Volatility: ATR percentile, short/long ATR ratio, efficiency ratio, consolidation
flag, gap-at-open size. Session: london/ny/overlap/ny_open flags, minutes since session open,
weekday. Execution: spread/ATR. Context: position within prior-day range, distance to nearest
untouched liquidity (HTF). Excluded: absolute time index, price level, any future-derived value,
the outcome of neighbouring setups.

## 5. Training and validation
* Chronological only. **Purged, embargoed walk-forward**: for each fold, drop training
  samples whose `[t0, t_exit]` overlaps the test window and embargo at least
  `max_wait + max_hold` bars (the full possible label horizon) after it.
  Anchored and rolling variants compared.
* A final **untouched holdout** (most recent period) opened once, after all choices are frozen.
* Hyperparameter search only inside training folds (nested), with the number of trials logged
  and a small budget; also perturb engine config (swing L/R, ATR multiples) to test fragility,
  not to pick the best-looking value.
* Model ladder: (0) base rate and rules-only; (1) L2 logistic regression;
  (2) shallow gradient-boosted trees (optionally monotone constraints);
  (3) random forest as a cross-check. Deep learning only if data volume supports it and it
  beats the ladder out of sample.
* Class/cost imbalance handled via weighting or thresholds chosen on validation folds only.
* Sample size: report events per fold/regime; refuse to fit when too few.

## 6. Calibration
Out-of-fold probabilities -> reliability curve, Brier score, log loss, expected calibration error
with bootstrap CIs, per session and regime. Calibrator (Platt/isotonic) fitted on a calibration
segment strictly before the test segment, never on the test fold. **A probability is shown to the
user only if calibration meets the pre-registered criteria on every holdout fold;** otherwise the
UI shows no number.

## 7. Performance measurement and acceptance gates
Primary: net expectancy (R per trade) after costs with **block-bootstrap** confidence intervals,
hit rate vs the break-even rate implied by RR, profit factor, max drawdown, trade count,
exposure time, and stability across folds/sessions/regimes. Compare against: rules-only,
random entries with identical stops/targets (permutation test), and cost sensitivity (+50%
spread/slippage). Account for multiple testing (log of every variant tried; deflated-Sharpe or
reality-check style adjustment).
**Gates are written down before the holdout is opened** (e.g. lower CI bound of net expectancy
above zero in a stated majority of folds, calibration criteria met, results survive cost stress
and config perturbation). Failing the gates means the model is not shipped; it is not retuned on
the holdout.

## 8. Deployment and governance
* Artifact = model + feature list/hash + engine-config hash + git commit + data range +
  metrics ("model card"). Logistic coefficients can be exported for on-device Kotlin scoring;
  trees via ONNX or served by the gateway.
* Fail closed: missing/stale features or schema mismatch => no score, rule-only NO TRADE logic.
* Shadow (paper) period before any user-facing score; drift monitoring and scheduled retraining
  with the same gates; versions auditable and reversible.
* Training stays offline (local/Colab-free tier/NAS100-AI-Lab style project); only the frozen
  artifact ships. No paid APIs.

## 9. Honest limits
Markets are non-stationary; demo data and fills differ from live; a model can look good in
backtest and fail live; few setups per month limit statistical power. Expect "no reliable edge
found" to be a possible, acceptable outcome.
