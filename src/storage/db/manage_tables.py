from src.storage.db.connection import engine  # Use the shared engine from connection.py
from src.storage.db.models import Base        # Import Base with all ORM models
import sys

if __name__ == "__main__":
    # Usage: python -m src.storage.db.create_tables [create|delete]
    action = "create"
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()

    if action == "create":
        # Create all tables defined in models.py using the shared engine
        Base.metadata.create_all(engine)
        print("All tables created successfully.")
    elif action == "delete":
        # Drop all tables defined in models.py using the shared engine
        Base.metadata.drop_all(engine)
        print("All tables deleted successfully.")
    else:
        print("Unknown action. Use 'create' or 'delete'.")