import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

errors = []

modules = [
    "app.core.config",
    "app.db.database",
    "app.db.models",
    "app.engines.ingestion",
    "app.engines.chunking",
    "app.engines.embedding",
    "app.engines.kpi_extractor",
    "app.engines.summarizer",
    "app.engines.risk_classifier",
    "app.engines.footnote_engine",
    "app.engines.rag_qa",
    "app.engines.anomaly_detector",
    "app.engines.peer_discovery",
    "app.services.pipeline",
    "app.services.comparison",
    "app.api.schemas",
    "app.api.routes.companies",
    "app.api.routes.filings",
    "app.api.routes.qa",
    "app.api.routes.comparison",
    "app.main",
]

for mod in modules:
    try:
        __import__(mod)
        print(f"  OK  {mod}")
    except Exception as e:
        print(f"  FAIL {mod}: {e}")
        errors.append((mod, str(e)))

print()
if errors:
    print(f"FAILED: {len(errors)} module(s)")
    sys.exit(1)
else:
    print("All imports OK")
