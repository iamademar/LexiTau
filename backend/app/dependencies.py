# Re-export database dependency
from .db import get_db

# Re-export authentication dependency  
from .auth import get_current_user

def ping() -> str:
    return "ok"