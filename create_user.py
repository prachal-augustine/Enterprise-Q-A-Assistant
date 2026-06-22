"""
Run this script to create the first user account.
Usage: python create_user.py
"""
import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DATA_DIR", "./data")
os.makedirs("./data/users_db", exist_ok=True)

from models import init_db, SessionLocal
from auth import create_user

def main():
    init_db()
    db = SessionLocal()
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    if not username or not password:
        print("Username and password cannot be empty.")
        sys.exit(1)
    try:
        user = create_user(db, username, password)
        print(f"User '{user.username}' created successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
