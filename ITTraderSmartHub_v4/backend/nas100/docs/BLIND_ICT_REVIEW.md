# Blind chart annotation before market-model training

This local workflow prepares causal chart-review tasks and imports the owner's
judgments for further review. It does not fit an estimator, certify the data,
change the training lock, calculate profitability or authorize orders.

## Prepare a private packet

From `backend`, use an existing authorized CSV and its independently retained
SHA-256 from `evidence/time_integrity/dataset_eligibility.json`:

```powershell
python tools/prepare_ict_review.py --csv evidence/USTECH100M_M15.csv --expected-sha256 8bbaf1751398c19658736dd24f752bd3adb63745ac12950e7eff840275f72d27 --timeframe-minutes 15 --review-stop 3000 --output-dir C:/private/new-review-packet
```

The source bytes are hashed once and that same immutable in-memory snapshot is
parsed. Hash mismatch fails before creating output. The output directory must
not already exist; sources and old packets are never overwritten. Market CSVs,
generated HTML and returned annotations stay private and are not source assets.

The packet selects at most twelve systematic, nonoverlapping 96-bar windows
with stride 128, from the explicitly bounded review prefix. Each window ends at
its own anchor close. Later candles, outcomes, model answers and returns are
absent from the HTML/JSON. The remaining tail is withheld from this packet;
that fact alone does not certify a final holdout never seen by any researcher.

Open `review.html` directly in a browser. It uses no network resources and its
content policy blocks connections. For each chart choose a setup hypothesis,
NO SETUP or UNCERTAIN, explain what was visible, and optionally add a lesson
reference and chart invalidation reason. Save each annotation, then export a
JSON copy. Draft browser storage is convenient, not a backup. Never label
examples by looking at what price did afterward.

The candles' UTC labels remain unverified source declarations. Gaps are shown
as unclassified and are never filled or declared market closures. Clock-based
session/news labels are disabled. These charts are not proof of faithfully
encoding Huddleston's discretionary methodology or a profitable strategy.

## Import the exported judgments

Retain the packet SHA-256 from the preparation receipt, independently of the
returned annotation file. Then run:

```powershell
python tools/import_ict_annotations.py --packet C:/private/new-review-packet/review_packet.json --annotations C:/private/smarthub-ict-annotations.json --expected-packet-sha256 <preparation-receipt-hash> --out C:/private/new-import.json
```

The importer checks the pinned packet digest, source binding, exact document
fields, task membership/uniqueness, allowed labels, nonempty bounded reasons,
UTC annotation timestamps and safety assertions. Duplicate/nonfinite JSON is
rejected. Output is exclusively created. It remains an operator's annotation
claim, not independently reviewed ground truth; hashes prove integrity against
the retained pin, not authorship or truth. There is no automatic model ingestion.

## Next acceptance gates

1. Independent clock/session, contract/cost and historical-data evidence.
2. Reviewed annotation definitions, blind adjudication and label agreement.
3. A frozen feature/label horizon, chronological splits, purge/embargo policy and
   independently reserved final holdout. Setup annotations and future trade
   outcomes are different labels and must remain separate.
4. A reviewed real-training activation after the existing gates pass, followed
   by calibration, walk-forward testing, cost sensitivity and independent review.

Until then: `TIMEBASE_UNVERIFIED`, `MODEL_NOT_READY`, `NO_TRADE`. The existing
MT5 exporter permission checks and unconditional real-training lock are unchanged.
