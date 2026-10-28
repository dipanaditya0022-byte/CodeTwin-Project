# CodeTwin

CodeTwin finds likely copied code in Python lab submissions and manages the review that follows:
an explained flag, a student response, a recorded decision, repeat-pair tracking and an append-only audit trail.

* **Design:** CodeTwin Design Document, 8 Oct 2026 (kept outside this repo). **Build status and results:** [docs/REPORT.md](docs/REPORT.md)
* **Stack:** React (Vite) · FastAPI · background worker · Azure SQL · Blob Storage · Cosmos DB · Storage Queue · Key Vault · Power BI

```
frontend/   React app (teacher, student and admin screens)
backend/    one Python codebase: the API (codetwin.api) and the worker (codetwin.worker)
  codetwin/similarity/   normalise → fingerprint → embed → classify → cluster → explain
  tests/                 40 pytest tests (API, roles, review flow, pipeline, integrity)
db/         codetwin_schema.sql (Azure SQL) and schema_sqlite.sql (local port of the same schema)
ml/         labelled set, copy generator, classifier training, benchmark, results
infra/      az CLI script for the Azure resources (not yet run against a subscription)
docs/       project report, Power BI guide, screenshots
```

## Run it locally (no Azure needed)

Locally the same code uses SQLite and folders under `data/` in place of Azure SQL, Blob Storage, Cosmos DB and the queue.

```bash
# backend: Python 3.12
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python -m pytest -q                       # 40 tests
python -m codetwin.cli seed-demo          # demo course, 12 students, two assignments, runs done
uvicorn codetwin.api.main:app --reload    # API on :8000, docs at /docs
python -m codetwin.worker                 # in a second terminal: processes new runs

# frontend: Node 20+
cd frontend && npm install && npm run dev # http://localhost:5173
```

Demo accounts (password `codetwin-demo-1`): `admin@demo.edu`, `teacher@demo.edu`, `student1@demo.edu` … `student12@demo.edu`.
Student 1 has an open flag on Lab 3 with a response; 22CS001 and 22CS002 are a repeat pair.

### Using the pretrained embedding model

The default embedder (`hashing`) needs no download. To use UniXcoder, as in the design:

```bash
pip install -r backend/requirements-ml.txt    # torch + transformers; ~500 MB of weights on first use
export CODETWIN_EMBEDDER=unixcoder            # set for both the API and the worker
```

### Retrain the classifier

```bash
python ml/make_dataset.py                     # regenerate the 150 copies from the 30 originals
python ml/train.py --embedder hashing         # or unixcoder; writes the model JSON and ml/results/metrics_*.json
python ml/benchmark.py --embedder unixcoder   # time a 60- and 120-file run
```

## Upload format

One `.zip` per assignment with one `.py` file per student, named by roll number: `22CS014.py`, `22CS014_lab3.py` or `22CS014/main.py`.
Files from students not enrolled in the course, non-`.py` files, files over 512 KB, non-UTF-8 files and second files for the same student are rejected with a reason.
Hidden files, `__MACOSX` and any path containing `..` are ignored. Uploaded code is only tokenised and embedded; it is never imported or run.

## Deploy to Azure

See [infra/azure_setup.sh](infra/azure_setup.sh) and section 9 of the report. Power BI setup: [docs/POWERBI.md](docs/POWERBI.md).

## Credits

Prior work: MOSS, JPlag, Dolos. Technique: k-gram fingerprinting with winnowing (Schleimer, Wilkerson and Aiken, 2003).
Libraries: React, FastAPI, scikit-learn, Hugging Face Transformers with microsoft/unixcoder-base.
AI assistance: Claude was used to shape the idea, draft the design document and schema, and write much of this code; see the report.
