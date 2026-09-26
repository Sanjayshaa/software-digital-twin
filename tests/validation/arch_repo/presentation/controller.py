from application.service import UserService

class UserController:
    def __init__(self):
        self.service = UserService()

    def handle_request(self, user_id: str):
        return self.service.fetch_user(user_id)
