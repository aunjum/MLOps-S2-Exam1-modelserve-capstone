# Terminal commands — local testing

Run these from your machine. Replace paths if your clone lives elsewhere.

## 1. Go to the project root

Open a terminal in the repository root (the directory that contains `requirements.txt` and the `app/` folder).

```bash
cd /path/to/MLOps-S2-Exam1-modelserve-capstone-starter
```

If you are already inside the clone:

```bash
cd "$(git rev-parse --show-toplevel)"
```

## 2. Create and activate a virtual environment (recommended)

Avoids PEP 668 “externally managed environment” errors on many Linux distributions.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows (Command Prompt):

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

## 3. Upgrade pip and install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Run the full test suite (same as CI)

```bash
pytest app/tests/ -v
```

## 5. Run only the API / predict tests

```bash
pytest app/tests/test_predict.py -v
```

## 6. Run a single test by name (optional)

```bash
pytest app/tests/test_predict.py::test_predict_returns_200 -v
```

## 7. Deactivate the virtual environment when finished (optional)

```bash
deactivate
```

---

**Note:** GitHub Actions runs steps 3–4 with Python 3.12 and `pytest app/tests/ -v` after `pip install -r requirements.txt`. Matching that locally catches CI failures before you push.
