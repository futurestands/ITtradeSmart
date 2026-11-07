# Fitted study retrieval

`nas100/study_retrieval.py` fits a small local TF-IDF text-retrieval model.
Corpus document frequencies determine smoothed inverse-document-frequency
weights; sublinear counts and L2 normalisation support cosine ranking. This
follows the weighting conventions documented by
[scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html).
A separate conformance test compares our weights/vectors with that reference.

This is a fitted educational search component, not an LLM fine-tune or a
BUY/SELL predictor. It does not understand charts, infer actual resting stops,
enforce broker permissions or establish ICT mastery. No full lectures were
used. The original metadata/hypothesis catalogue is preserved and augmented
by concise original primary-source summaries and explicitly marked user policy.
Third-party transcript mirrors and unaffiliated teaching sites are excluded.

## Local use

From the backend using a project Python environment:

    python tools/train_study_retriever.py fit --output PATH_TO_NEW_INDEX.json
    python tools/train_study_retriever.py query --index PATH_TO_INDEX.json "FTMO daily loss reset"

Fit refuses to overwrite an existing artifact. The JSON artifact contains
learned vocabulary, IDF and document vectors. It has no executable payload and
is not loaded through pickle. Query verifies artifact integrity and requires a
current corpus digest match; changed notes require a reviewed rebuild.
Hashes detect changes, not authorship or truth. Use only trusted local artifacts.

No broker SDK, network requests, credential handling or order API is introduced.
There is no Flask route, cloud runtime or Android integration. All query outputs
remain RESEARCH_ONLY / MODEL_NOT_READY / NO_TRADE; source text and prompt-like
queries cannot alter those flags. A cosine score is not a win probability.
Account-rule notes are dated reference, not live verification of purchased terms.

## First fit and limits

The initial corpus contains 20 cards and yielded 1,190 unigram/bigram features.
Evaluation questions were frozen and hashed before fitting; no evaluation text
entered training. A developer-authored smoke benchmark tested 24 supported and
two unrelated queries. This is a small internal routing check, not independent
expert validation, broad semantic evaluation or trading accuracy. No result
was used to tune the retrieval cutoff or corpus after the fit.

Artifacts and fit/evaluation receipts live in workspace `outputs`, outside this
source checkout. They have not been pushed or deployed. The market-training
pipeline and its data quarantine remain unchanged.

## Primary references in the supplement

- [Author's home page](https://www.theinnercircletrader.com/) and
  [Episode 6 description](https://www.youtube.com/watch?v=Bkt8B3kLATQ): study
  identity/topics only; no full lecture review.
- [MetaQuotes bar API](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py)
  and [symbol information](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py):
  acquisition conventions and available property fields.
- [FTMO 2-Step](https://ftmo.com/en/2-step-challenge/),
  [objectives](https://ftmo.com/en/trading-objectives/) and
  [news FAQ](https://ftmo.com/en/faq/can-i-trade-news/): programme/stage-specific
  reference; purchased terms remain unbound.
- [CME MNQ specifications](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html):
  futures instrument context, not a specification for USTECH100M CFDs.
