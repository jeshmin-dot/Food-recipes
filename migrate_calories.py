from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

import config

engine = create_engine(config.DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE recipes ADD COLUMN calories INT NULL"))
        conn.commit()
        print("Migration applied: recipes.calories column added.")
    except OperationalError as exc:
        if "1060" in str(exc) or "Duplicate column" in str(exc):
            print("Column already exists - nothing to do.")
        else:
            raise