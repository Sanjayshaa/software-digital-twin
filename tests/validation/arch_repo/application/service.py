from domain.entity import User
from infrastructure.db import DatabaseClient


class UserService:
    def __init__(self):
        self.db = DatabaseClient()

    def fetch_user(self, user_id: str) -> User:
        return self.db.get_user(user_id)
