import aiosqlite


class MyDb:
    # __dbname__ = "/app/db/db.db"
    __dbname__ = "db.db"

    async def db_setup(self):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user(
                        user_id INTEGER PRIMARY KEY UNIQUE NOT NULL,
                        username TEXT,
                        fullname TEXT,
                        last_public_time DATETIME,
                        is_active BOOLEAN,
                        processing_video BOOLEAN DEFAULT False
                    )
                """)

    async def sql_create_user(self, user_id=int, username=str, fullname=str, is_active=bool):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.execute("SELECT user_id FROM user WHERE user_id = ?", (user_id,)) as cursor:
                existing_user = await cursor.fetchone()

                if existing_user is None:
                    await db.execute("INSERT INTO user (user_id, username, fullname, is_active) VALUES (?, ?, ?, ?)",
                                     (user_id, username, fullname, is_active))
                    await db.commit()
                return user_id

    async def sql_get_users(self):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT user_id FROM user WHERE is_active = True")
                rows = await cursor.fetchall()
                user_ids = [row[0] for row in rows]
                return user_ids

    async def sql_get_all_users(self):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT user_id FROM user")
                rows = await cursor.fetchall()
                user_ids = [row[0] for row in rows]
                return user_ids

    async def sql_update_user_status(self, is_active, user_id):
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET is_active=? WHERE user_id=? ", (is_active, user_id))
            await db.commit()

    async def sql_update_user_last_public_time(self, last_public_time, user_id):
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET last_public_time=? WHERE user_id=? ", (last_public_time, user_id))
            await db.commit()

    async def sql_get_last_public_time(self, user_id):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT last_public_time FROM user WHERE user_id=?", (user_id,))
                last_public_time = await cursor.fetchone()
                if last_public_time:
                    return last_public_time[0]
                return False

    async def sql_set_user_processing(self, user_id, processing):
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET processing_video=? WHERE user_id=?", (processing, user_id))
            await db.commit()

    async def sql_check_user_processing(self, user_id):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT processing_video FROM user WHERE user_id=?", (user_id,))
                result = await cursor.fetchone()
                return result and result[0]

    async def sql_reset_processing_video(self):
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET processing_video=False")
            await db.commit()