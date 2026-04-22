# Synthetic Document Fixtures

This folder is for synthetic-only tax documents used by parser/replay tests.
No real taxpayer data is allowed.

## Generated docs
- form16_sample.pdf
- ais_sample.pdf
- tis_sample.pdf

## Regression bank
- parser_regression_cases.json

Generate with:

```bash
python tests/fixtures/synthetic_docs/generate_pdfs.py
```

Run the parser scorecard with:

```bash
PYTHONPATH=apps/workers/src python scripts/parser_scorecard.py
```
