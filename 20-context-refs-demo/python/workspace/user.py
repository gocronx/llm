"""User model: minimal example for the @ref demo."""

from dataclasses import dataclass


@dataclass
class User:
    id: int
    email: str
    name: str

    def display(self) -> str:
        return f"{self.name} <{self.email}>"


def find_user(users: list[User], email: str) -> User | None:
    for u in users:
        if u.email == email:
            return u
    return None
