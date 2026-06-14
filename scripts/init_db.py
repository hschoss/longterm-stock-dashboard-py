from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import get_engine
from app.models import Base


def init_database() -> None:
    app = create_app()
    with app.app_context():
        Base.metadata.create_all(get_engine())
        print("Database schema initialized.")


if __name__ == "__main__":
    init_database()
