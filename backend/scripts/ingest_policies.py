from pathlib import Path

from app.config import Settings
from app.persistence.database import Database
from app.retrieval.ingest import ingest_policy


def main() -> None:
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("SUPPORT_COPILOT_DATABASE_URL is required.")
    database = Database(settings.database_url)
    try:
        root = Path(__file__).resolve().parents[1] / "policies" / "source"
        for path in sorted(root.glob("*.json")):
            ingest_policy(database, path)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
