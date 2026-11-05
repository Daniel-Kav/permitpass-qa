"""Runtime settings, read once from the environment."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./permitpass.db")
