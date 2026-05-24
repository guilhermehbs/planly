import os
from pathlib import Path

from core.env import load_env_file


load_env_file()
APP_TITLE = os.environ.get("PLANLY_APP_TITLE", "Planly")
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = Path(os.environ.get("PLANLY_DB_PATH", BASE_DIR / "planejamento_financeiro.db")).expanduser()
