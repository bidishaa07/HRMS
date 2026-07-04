from app.database import SessionLocal
from app.models import User
from sqlalchemy import select


async def main():
    async with SessionLocal() as db:
        res = await db.scalar(select(User).where(User.email == 'bidishadey2007@gmail.com'))
        if res:
            print(f"User exists: name={res.name}, login_id={res.login_id}")
        else:
            print("User does not exist")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
