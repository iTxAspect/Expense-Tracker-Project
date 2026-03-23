# Expense Tracker — CI/CD Setup

## Pipeline Overview

```
Push / PR
    │
    ├─► 🔍 Lint (flake8 + pylint + bandit)
    │
    ├─► 🧪 Unit & Integration Tests (pytest + coverage)
    │       └─ Coverage gate: ≥ 80%
    │
    ├─► 🔒 Security Scan (pip-audit + safety + hardcoded-secret check)
    │
    └─► 📱 Android APK Build  [main branch & releases only]
            └─► 🚀 Sign & Upload to GitHub Release  [releases only]
```

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `ci.yml` | push to main/develop, PR to main, releases | Full pipeline |
| `pr-check.yml` | every PR | Fast syntax + test check (< 2 min) |
| `nightly.yml` | 02:00 UTC daily | Matrix test on Py 3.10–3.13 + dep audit |

## Repository Structure Expected

```
project/
├── app/
│   ├── database.py
│   ├── logic.py
│   ├── gui.py
│   └── buildozer.spec
├── fonts/
│   └── fontawesome-webfont.ttf
├── tests/
│   └── test_logic.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── .flake8
```

## Running Locally

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Run tests with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Lint
flake8 app/
pylint app/database.py app/logic.py

# Security check
bandit -r app/database.py app/logic.py
pip-audit -r requirements.txt
```

## GitHub Secrets Required

For the Android release signing job, add these in
**Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `ANDROID_SIGNING_KEY` | Base64-encoded `.jks` keystore file |
| `ANDROID_KEY_ALIAS` | Key alias inside the keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_PASSWORD` | Key password |

### Generate a signing keystore
```bash
keytool -genkey -v \
  -keystore expense-tracker.jks \
  -alias expense-tracker \
  -keyalg RSA -keysize 2048 \
  -validity 10000

# Encode for GitHub Secret
base64 -w 0 expense-tracker.jks
```

## Coverage Targets

| File | Target |
|------|--------|
| `database.py` | ≥ 85% |
| `logic.py`    | ≥ 85% |
| `gui.py`      | excluded (Kivy headless not supported) |
| **Overall**   | **≥ 80%** |

## Branch Strategy

```
main        ← protected; requires PR + passing CI
develop     ← integration branch
feature/*   ← individual features
hotfix/*    ← urgent production fixes
```

## Android Build Notes

- Buildozer cache (SDK/NDK ~4 GB) is cached by `buildozer.spec` hash
- First build takes ~40 minutes; subsequent builds ~10 minutes (cached)
- Debug APK is retained as an artifact for 30 days
- Release APK is signed and attached to the GitHub Release
