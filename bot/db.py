from typing import Optional

import asyncpg


class ConfigStore:
    def __init__(self, *args, **kwargs):
        self.conn: asyncpg.Connection = None
        self._coro = asyncpg.connect(*args, **kwargs)

    async def _prepare(self):
        if not self.conn:
            self.conn = await self._coro
            await self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                configs (
                    guild_id VARCHAR(25) PRIMARY KEY,
                    channel_id VARCHAR(25),
                    text_begin TEXT,
                    text_end TEXT
                )
            """
            )

    async def set(self, guild_id: int, channel_id: int, text_begin: str, text_end: str):
        await self._prepare()
        await self.conn.execute(
            """
            INSERT INTO configs (guild_id, channel_id, text_begin, text_end)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id) DO UPDATE
            SET channel_id = $2, text_begin = $3, text_end = $4
        """,
            str(guild_id),
            str(channel_id),
            text_begin,
            text_end,
        )

    async def get(self, guild_id: int) -> Optional[tuple[int, str, str]]:
        await self._prepare()
        row = await self.conn.fetchrow(
            "SELECT channel_id, text_begin, text_end FROM configs WHERE guild_id = $1",
            str(guild_id),
        )
        if row:
            return int(row["channel_id"]), row["text_begin"], row["text_end"]
        return None

    async def delete(self, guild_id: int):
        await self._prepare()
        await self.conn.execute(
            "DELETE FROM configs WHERE guild_id = $1",
            str(guild_id),
        )

    async def get_all(self) -> list[tuple[int, str, str]]:
        await self._prepare()
        return [
            (int(row["channel_id"]), row["text_begin"], row["text_end"])
            for row in await self.conn.fetch(
                "SELECT channel_id, text_begin, text_end FROM configs"
            )
        ]
