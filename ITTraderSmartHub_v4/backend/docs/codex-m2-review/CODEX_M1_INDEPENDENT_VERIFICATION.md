# Codex M1 independent verification — 6 November 2026

Status: M1 inspected and tested independently; M2 author changes below await an
external reviewer. No push, merge, deployment, cloud migration or trading.

## Actual repositories and preservation

| Repository | Source branch | Reviewed HEAD | Source working tree |
|---|---|---|---|
| SmartHub | `feature/workbuddy-m1-offline-engineering-20261105` | `8998f0f30abc7f814fb935e458e9c04c2a6a56a0` | Clean |
| AI Lab | `feature/workbuddy-m1-offline-engineering-20261105` | `4b2561634b9a5c8f4978e6f7ea6978790be6fd40` | Two untracked synthetic reports, preserved |

Source locations: `C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration` and `C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B`. The original checkouts were
not switched, reset, edited, merged or used for commits. Their HEADs/status were
rechecked after development. The two Lab report hashes were recorded and checked
again unchanged; this proves preservation during that observation interval, not
a reconstruction of prior agent activity.

Own isolated clones, each on `feature/codex-m2-independent-review-20261106`:

- `C:\Users\MJ\Documents\Codex\2026-11-05\c-users-mj-documents-ittradesmart-nas100\work\m2-smarthub`; local M2 commit `74f266ce9a7619a8f33f72ea4329688fc2d7a2eb`.
- `C:\Users\MJ\Documents\Codex\2026-11-05\c-users-mj-documents-ittradesmart-nas100\work\m2-lab`; local M2 commit `10517541f48424dfe970f04ce7ac15bdd2d5e896`.

Clone origins point to the respective local source repository. Nothing was
published. Current remote existence of M1 commits was not independently queried;
local refs and older publication reports are not fresh remote evidence.

## Verified WorkBuddy commit objects

SmartHub baseline `0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f`:

- `7003781d93ab0fb994c4ec4ef1a93409fc05c5d1`
- `e6dfc3049b25c5c9462d96e1861ad941ab492cc1`
- `e1fcfabddec4fcbbebf59556ab93f227863f9e10`
- Additional documentation commit `8998f0f30abc7f814fb935e458e9c04c2a6a56a0`, omitted from the request's list.

Lab baseline `6d0cc8fbde71e2d6637cc8a03bbe7fc6028a2127`:

- `28892bdafdaba56add2fd9d207af3c724288c769`
- `4b2561634b9a5c8f4978e6f7ea6978790be6fd40`

SmartHub M1 adds three test modules and six reports: nine files, 2,527 additions,
no production source changes. Lab M1 adds two production modules and six test
modules: eight files, 1,491 additions. Full paths/status are in
`M2_COMMIT_AND_FILE_INVENTORY.json`. The unsafe `feature/v5-demo-trading-bot`
branch was never checked out or used as a merge source.

## Reproduced tests and environments

| Run | Result | Interpretation |
|---|---|---|
| SmartHub unmodified M1 | 660 passed, 2 skipped | Reproduces reported count |
| Lab unmodified clean M1 clone | 496 passed, 1 failed | Missing ignored local provenance JSON |
| Final SmartHub | 675 passed, 2 skipped, 0 failed, 11.22 s | 15 new M2 cases |
| Final Lab | 517 passed, 0 skipped, 0 failed, 30.30 s | 20 new M2 cases; local provenance supplied |

The Lab failure is `test_quarantine_provenance_still_blocks_certification` in
`tests/test_m1_timebase_api_reconciliation.py`: it directly reads ignored
`data/quarantine/USTECH100M_M5_raw.provenance.json`. Only the original metadata was copied to the ignored clone path;
its SHA-256 is `a209537c38701a398d2f0a9b8e3eaf3d885be54b601d2ef85113eb18acc32b37`. No raw CSV was copied or certification field
changed. Final 517 = 497 original tests + 20 new cases. This is not a claim that
a fresh CI clone passes without the external metadata. Retain a separate local
data integration test when making the unit suite hermetic.

SmartHub skips: `test_mt5_account_registry.py:101` cannot create a symlink;
`test_nas100_research_status.py:155` lacks symlink privileges. These safety checks
remain unexecuted on this Windows account, rather than implicitly passing.

Gateway environment: Python 3.14.6, pytest 9.2.0, Flask 3.1.3,
MetaTrader5 5.0.6231, numpy 2.5.4, tzdata 2026.6.
Lab environment: Python 3.12.10, pytest 9.2.0, pandas 3.1.0,
numpy 2.5.4, scikit-learn 1.9.1, tzdata 2026.6. Existing virtual environments
were used, with no dependency installation. Lab pytest's `pythonpath=src`
selects the isolated source rather than its environment's editable install.

Reproduction: from clone backend or Lab root run the corresponding source
environment's `Scripts/python.exe -m pytest -q -rs -p no:cacheprovider
--basetemp=<new-writable-temporary-directory> tests`. Full logs are included.

## Review findings

M1 simulator tests use hand-worked stop-first exits, adverse gap prices, target
caps, incomplete/no-fill distinctions and one-time spread/slippage/commission
costs. These are useful independent expected-value checks, not broker economics
certification. OHLC paths, historical spread availability and account-currency
conversion still limit real backtests.

Walk-forward source partitions absolute event-bar intervals, purges outcomes
crossing subsequent splits and withholds test labels past the test window.
Calibration source fits base estimators on training rows and the sigmoid only
on calibration rows. M1 tests spy on fit inputs and stress boundaries. HTF
availability checks use candle close, not its open; incomplete buckets are
excluded by default. Software checks do not establish statistical independence
of a genuine final holdout or the correctness of unverified source timestamps.

The real-training preparation entry point always raises, including when every
supplied gate claims success. No real-market model is trained, evaluated or
activated by this review. Existing synthetic fits are software demonstrations.

M1 reproducibility was valuable but not complete: 12 new adversarial cases
failed before correction. See the M2 report for corrected defects and residual
limits. An additional cyclic-input regression caught a controlled-error issue
in my recursive-key correction; it was fixed and the complete suite rerun.
