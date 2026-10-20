# Contributing

BorderPulse is a research project maintained by a student in El Paso. Contributions are welcome, with one rule above all others: **the model's definitions and validation targets are fixed conventions, and any change to them is a versioned model change**, not a tweak. See `CHANGELOG.md` for how every past change was recorded.

## Ground rules

1. **Reproduce first.** `pip install -r requirements.txt && python3 refresh.py --no-fetch` must run clean, with all 12 leakage checks and all 6 vintage checks passing, before and after your change.
2. **Nothing enters the composite score automatically.** New indicators go in `data/extra/` as *watch* series (register them in `data/extra/manifest.json`). Promotion into `pipeline.py`'s `signals` requires a documented out-of-sample improvement from `backtest.py` and a major version bump.
3. **Pre-register analyses.** `border_test.py` and `onset_eval.py` show the pattern: write down the variants, transforms and decision rule in the module docstring *before* looking at results, and record the date.
4. **No future data, ever.** Every statistic uses an expanding window ending at the observation month. `test_backtest.py` checks this; if you add a transform, add a check.
5. **Honest framing.** Episode counts with intervals, never month-level "precision" percentages. If a result is negative, it gets the same prominence as a positive one.
6. **Numbers come from the pipeline.** The dashboard, brief and technical note all read `borderpulse_output.json` and `validation/*.json`. Do not hand-type a number into any of them.

## Making a change

- **Display only** (dashboard layout, wording): edit `dashboard_body.html`, run `python3 build.py`, and note the change under a new minor/patch version in `CHANGELOG.md` with "score, model and data unchanged".
- **New watch indicator:** add the CSV under `data/extra/`, an entry in `data/extra/manifest.json`, a fetch step in `refresh.py` if it is automatable, and rerun `make_manifest.py`.
- **Model change:** bump `VERSION` in `pipeline.py`, add a row to the version-history table in `dashboard_body.html`, write the `CHANGELOG.md` entry, rerun the full chain, and update `technical_note.md` via `make_technote.py`.

## Reporting a data problem

Open an issue with the series ID, the month, the value you see, and the value at the source. Known gaps (e.g. the October 2025 federal data pause) are listed in `pipeline.py` and handled explicitly; please do not interpolate silently.
