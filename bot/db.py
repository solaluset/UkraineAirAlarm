from typing import Optional, TypeVar

import asyncpg

Row = TypeVar("Row", bound=tuple[int, str, str])
RowWithRegions = TypeVar(
    "RowWithRegions", bound=tuple[int, str, str, Optional[list[int]]]
)


class ConfigStore:
    def __init__(self, *args, **kwargs):
        self.conn: asyncpg.Connection = None
        self._args = args
        self._kwargs = kwargs

    async def _prepare(self):
        if not self.conn or self.conn.is_closed():
            self.conn = await asyncpg.connect(*self._args, **self._kwargs)
            await self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                configs (
                    guild_id VARCHAR(25) PRIMARY KEY,
                    channel_id VARCHAR(25),
                    text_begin TEXT,
                    text_end TEXT,
                    regions INT ARRAY
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

    async def get(self, guild_id: int) -> Optional[RowWithRegions]:
        await self._prepare()
        row = await self.conn.fetchrow(
            """
            SELECT channel_id, text_begin, text_end, regions FROM configs
            WHERE guild_id = $1
            """,
            str(guild_id),
        )
        if row:
            return (
                int(row["channel_id"]),
                row["text_begin"],
                row["text_end"],
                row["regions"],
            )
        return None

    async def delete(self, guild_id: int):
        await self._prepare()
        await self.conn.execute(
            "DELETE FROM configs WHERE guild_id = $1",
            str(guild_id),
        )

    async def get_for(self, region_id: int) -> list[Row]:
        await self._prepare()
        return [
            (int(row["channel_id"]), row["text_begin"], row["text_end"])
            for row in await self.conn.fetch(
                """
                SELECT channel_id, text_begin, text_end FROM configs
                WHERE
                    array_length(regions, 1) IS NULL
                    OR array_position(regions, $1) IS NOT NULL
                """,
                region_id,
            )
        ]

    async def add_region(self, guild_id: int, region_id: int):
        await self._prepare()
        return (
            await self.conn.execute(
                """
                UPDATE configs
                SET regions = array_append(regions, $2)
                WHERE guild_id = $1 AND array_position(regions, $2) IS NULL
                """,
                str(guild_id),
                region_id,
            )
        ).endswith("1")

    async def remove_region(self, guild_id: int, region_id: int):
        await self._prepare()
        return (
            await self.conn.execute(
                """
                UPDATE configs
                SET regions = array_remove(regions, $2)
                WHERE guild_id = $1 AND array_position(regions, $2) IS NOT NULL
                """,
                str(guild_id),
                region_id,
            )
        ).endswith("1")

    async def remove_all_regions(self, guild_id: int):
        await self._prepare()
        await self.conn.execute(
            "UPDATE configs SET regions = $2 WHERE guild_id = $1", str(guild_id), []
        )
