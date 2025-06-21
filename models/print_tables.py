from sqlalchemy import create_engine, inspect
from pathlib import Path

# Always use models.db in the same directory as this script
DB_Path = Path(__file__).parent / "models.db"
engine = create_engine(f"sqlite:///{DB_Path}")

inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables in the database:")
for table in tables:
    print(table) 