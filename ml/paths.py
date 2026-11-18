"""Shared paths for the ml/ workspace."""
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
REPO_DIR = ML_DIR.parent
BACKEND_DIR = REPO_DIR / "backend"

DATA_DIR = ML_DIR / "data"                 # gitignored
RAW_DIR = DATA_DIR / "raw"                 # extracted, uncleaned records
PROCESSED_DIR = DATA_DIR / "processed"     # cleaned datasets used for training
REPORTS_DIR = ML_DIR / "reports"           # metrics / eda json consumed by the GUI
FIGURES_DIR = REPORTS_DIR / "figures"

for d in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR):
    d.mkdir(parents=True, exist_ok=True)
