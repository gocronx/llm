# Project Notes

## Decisions
- 用 dataclass 而不是 SQLAlchemy，因为这只是 demo
- email 唯一约束没强制——register 重复调用会创建多个同 email 用户

## TODO
- 加 password hash
- find_user 应该用 dict 而不是 list 遍历
- list_users 应该分页
