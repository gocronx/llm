"""HTTP endpoints. Uses User from user.py."""

from user import User, find_user


_users: list[User] = []


def register(email: str, name: str) -> User:
    user = User(id=len(_users) + 1, email=email, name=name)
    _users.append(user)
    return user


def get_user_by_email(email: str) -> User | None:
    return find_user(_users, email)


def list_users() -> list[dict]:
    return [{"id": u.id, "email": u.email, "name": u.name} for u in _users]
