from domain.entity import User


class DatabaseClient:
    def get_user(self, user_id: str) -> User:
        return User(id=user_id, name="Test User")
