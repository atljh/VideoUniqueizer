import aiosqlite


class MyDb:
    __dbname__ = "db.db"

    async def db_setup(self):
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bots(
                        bot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bot_token TEXT UNIQUE NOT NULL
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user(
                        user_id INTEGER NOT NULL,
                        bot_id INTEGER NOT NULL,
                        username TEXT,
                        fullname TEXT,
                        last_public_time DATETIME,
                        is_active BOOLEAN,
                        processing_video BOOLEAN DEFAULT 0,
                        PRIMARY KEY (user_id, bot_id),
                        FOREIGN KEY (bot_id) REFERENCES bots (bot_id) ON DELETE CASCADE
                    )
                """)

    async def sql_create_bot(self, bot_token: str):
        """Создаёт нового бота в базе данных, если его ещё нет"""
        async with aiosqlite.connect(self.__dbname__) as db:
            cursor = await db.execute("SELECT bot_id FROM bots WHERE bot_token = ?", (bot_token,))
            exists = await cursor.fetchone()

            if not exists:
                cursor = await db.execute("INSERT INTO bots (bot_token) VALUES (?)", (bot_token,))
                bot_id = cursor.lastrowid
                await db.commit()
                return bot_id
            else:
                return exists[0]

    async def sql_get_bot_id(self, bot_token: str):
        """Получает ID бота по его токену"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT bot_id FROM bots WHERE bot_token = ?", (bot_token,))
                result = await cursor.fetchone()
                return result[0] if result else None

    async def sql_create_user(self, user_id: int, bot_token: str, username: str, fullname: str, is_active: bool):
        bot_id = await self.sql_create_bot(bot_token)
        """Создаёт пользователя, привязанного к боту"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.execute("SELECT user_id FROM user WHERE user_id = ? AND bot_id = ?", (user_id, bot_id)) as cursor:
                existing_user = await cursor.fetchone()

                if existing_user is None:
                    await db.execute("INSERT INTO user (user_id, bot_id, username, fullname, is_active) VALUES (?, ?, ?, ?, ?)",
                                    (user_id, bot_id, username, fullname, is_active))
                    await db.commit()
                return user_id

    async def sql_get_users_by_bot(self, bot_token: str):
        bot_id = await self.sql_get_bot_id(bot_token)
        """Получает список пользователей, привязанных к конкретному боту"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT user_id FROM user WHERE bot_id = ? AND is_active = True", (bot_id,))
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def sql_get_all_users(self):
        """Получает список всех пользователей всех ботов"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT user_id FROM user")
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def sql_update_user_status(self, is_active: bool, user_id: int, bot_token: str):
        bot_id = await self.sql_get_bot_id(bot_token)
        """Обновляет статус активности пользователя"""
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET is_active=? WHERE user_id=? AND bot_id=?", (is_active, user_id, bot_id))
            await db.commit()

    async def sql_update_user_last_public_time(self, last_public_time, user_id: int, bot_id: int):
        """Обновляет время последней публикации пользователя"""
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET last_public_time=? WHERE user_id=? AND bot_id=?", (last_public_time, user_id, bot_id))
            await db.commit()

    async def sql_get_last_public_time(self, user_id: int, bot_id: int):
        """Получает время последней публикации пользователя"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT last_public_time FROM user WHERE user_id=? AND bot_id=?", (user_id, bot_id))
                last_public_time = await cursor.fetchone()
                return last_public_time[0] if last_public_time else False

    async def sql_set_user_processing(self, user_id: int, bot_token: str, processing: bool):
        bot_id = await self.sql_get_bot_id(bot_token)
        """Устанавливает статус обработки видео пользователю"""
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET processing_video=? WHERE user_id=? AND bot_id=?", (processing, user_id, bot_id))
            await db.commit()

    async def sql_check_user_processing(self, user_id: int, bot_token: str):
        bot_id = await self.sql_get_bot_id(bot_token)
        """Проверяет, находится ли пользователь в процессе обработки видео"""
        async with aiosqlite.connect(self.__dbname__) as db:
            async with db.cursor() as cursor:
                await cursor.execute("SELECT processing_video FROM user WHERE user_id=? AND bot_id=?", (user_id, bot_id))
                result = await cursor.fetchone()
                return result and result[0]

    async def sql_reset_processing_video(self):
        """Сбрасывает флаг обработки видео для всех пользователей конкретного бота"""
        async with aiosqlite.connect(self.__dbname__) as db:
            await db.execute("UPDATE user SET processing_video=False")
            await db.commit()
