"""Explicit local operator command; no default administrator credentials."""
import getpass, sys
from sqlalchemy import select
from .models import Session, User
from .security import hash_password
if __name__ == "__main__":
    name = input("Admin username (letters/numbers/_/-): ").strip().lower()
    import re
    if not re.fullmatch(r"[a-z0-9_-]{3,50}",name): sys.exit("Invalid username")
    password = getpass.getpass("New password (10+ characters): ")
    if not 10 <= len(password) <= 128: sys.exit("Invalid password length")
    with Session.begin() as db:
        if db.scalar(select(User).where(User.username==name)): sys.exit("Username already exists; choose a new one")
        db.add(User(username=name,password_hash=hash_password(password),role="admin"))
    print("Administrator created.")
