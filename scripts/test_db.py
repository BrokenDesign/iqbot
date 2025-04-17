from iqbot import db


async def async_main():
    # await db.add_user(db.User(1, 1, 100))
    # await db.add_user(db.User(1, 2, 100))
    users = await db.read_or_add_users(1, [1, 2, 3])
    print(users)


if __name__ == "__main__":
    import asyncio

    asyncio.run(async_main())
