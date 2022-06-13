import json
import logging
import re
from time import time
from os import getenv
from io import BytesIO
from typing import Optional
from base64 import b64encode
from urllib.request import quote as encode_for_url

import discord
from discord.ext import commands
from cloudinary.uploader import upload_image
from dotenv import load_dotenv

from . import db
from .api import API
from map_render import render as render_map


load_dotenv()
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

PLACEHOLDER = re.compile(r"%(\w+)%")
MANDATORY = ("name", "name_en")


DEBUG_GUILD = getenv("DEBUG_GUILD")
bot = discord.Bot(debug_guilds=[int(DEBUG_GUILD)] if DEBUG_GUILD else None)
api = API(getenv("API_KEY"))
store = db.ConfigStore(getenv("DATABASE_URL"))

REGION_IDS = api.get_regions()
REGION_NAMES = {v: k for k, v in REGION_IDS.items()}
REGION_OPTIONS = tuple(
    discord.OptionChoice(name, id_) for name, id_ in REGION_IDS.items()
)
EXAMPLE_EMBED = b64encode(
    json.dumps(
        {
            "content": "Можете використовувати",
            "embed": {
                "title": "%name%",
                "color": 14616327,
                "description": "будь-який текст",
            },
        }
    ).encode()
).decode()
DEFAULT_IMAGE_URL = "https://res.cloudinary.com/alarm-map/image/upload/v1655127823/opltbx5ak8uohpzxazd4.png"


@bot.event
async def on_ready():
    print("Ready")


@bot.event
async def on_application_command_error(ctx, exception):
    if isinstance(exception, commands.MissingPermissions):
        await ctx.respond("У вас немає права на керування сервером!")
    elif isinstance(exception, commands.NoPrivateMessage):
        await ctx.respond(
            "Цю команду не можна використовувати в приватних повідомленнях."
        )
    else:
        print(exception)
        await ctx.respond("Сталася невідома помилка.")


if DEBUG_GUILD:

    @bot.slash_command()
    async def test(ctx, channel: discord.Option(discord.TextChannel)):
        print(
            "Test result: ",
            channel.permissions_for(ctx.me)
            == (await ctx.guild.fetch_channel(channel.id)).permissions_for(ctx.me),
        )


@bot.slash_command(description="вивести інструкціі")
async def help(ctx: discord.ApplicationContext):
    embed = discord.Embed(title="Допомога", description="Як користуватися ботом?")
    embed.add_field(name="1.", value="Додайте бота на сервер.", inline=False)
    url = "https://glitchii.github.io/embedbuilder/?" + "&".join(
        (
            f"data={EXAMPLE_EMBED}",
            "placeholders",
            f"username={encode_for_url(bot.user.name)}",
            f"avatar={bot.user.display_avatar}",
        )
    )
    embed.add_field(
        name="2.",
        value=f"""Скористайтеся командою `/configure`
Оберіть канал, в який будуть приходити повідомлення.
Вкажіть, що має бути надіслано при оголошенні тривоги та її відбою.
Можна використовувати звичайний текст або [створити ембед]({url}).
Використовуйте `%name%`, щоб підставити назву області в текст, або
`%name_en%` для назви англійською.
Замість `%image%` буде підставлено посилання на поточну карту.
""",
        inline=False,
    )
    embed.add_field(
        name="3.",
        value="""Ви можете обмежити перелік регіонів, про тривогу в яких сповіщатиме бот.
Для цьго скористайтеся командою `/add_region`
За замовчуванням бот сповіщатиме про тривоги по всій території України.
""",
        inline=False,
    )
    embed.add_field(
        name="4.",
        value="""Готово! Всі сповіщення будуть приходити в канал, що ви вказали.
Налаштування можна перевірити за допомогою команди `/show_config`
Якщо хочете відключити бота, використайте `/delete_config`""",
        inline=False,
    )
    await ctx.respond(embed=embed)


@bot.slash_command(description="налаштувати бота")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def configure(
    ctx: discord.ApplicationContext,
    channel: discord.Option(discord.TextChannel, "цільовий канал", name="канал"),
    text_begin: discord.Option(
        str, "текст сповіщення про тривогу", name="оголошення_тривоги"
    ),
    text_end: discord.Option(
        str, "текст сповіщення про відбій тривоги", name="відбій_тривоги"
    ),
):
    await ctx.defer(ephemeral=True)
    # fix for pycord permissions issue
    # https://github.com/Pycord-Development/pycord/issues/1283
    channel = ctx.guild.get_channel(channel.id)
    if not channel.permissions_for(ctx.guild.me).embed_links:
        await ctx.respond(
            "У бота немає прав писати або вставляти посилання у вказаний канал!"
        )
        return
    try:
        text_begin = await show_and_reserialize(ctx, text_begin)
        text_end = await show_and_reserialize(ctx, text_end)
    except discord.HTTPException:
        await ctx.respond("Неправильно сформований ембед.")
        return
    await store.set(ctx.guild.id, channel.id, text_begin, text_end)
    await ctx.respond("Налаштування завершено!")


@bot.slash_command(description="додати регіон до списку")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def add_region(
    ctx: discord.ApplicationContext,
    region: discord.Option(int, name="регіон", choices=REGION_OPTIONS),
):
    await ctx.defer()
    if await store.add_region(ctx.guild.id, region):
        await ctx.respond("Регіон додано до списку.")
    else:
        await ctx.respond("Регіон вже є в списку або бота не налаштовано.")


@bot.slash_command(description="видалити регіон зі списку")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def remove_region(
    ctx: discord.ApplicationContext,
    region: discord.Option(int, name="регіон", choices=REGION_OPTIONS),
):
    await ctx.defer()
    if await store.remove_region(ctx.guild.id, region):
        await ctx.respond("Регіон видалено зі списку.")
    else:
        await ctx.respond("Регіону немає в списку або бота не налаштовано.")


@bot.slash_command(description="видалити список регіонів")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def remove_all_regions(ctx: discord.ApplicationContext):
    await ctx.defer()
    await store.remove_all_regions(ctx.guild.id)
    await ctx.respond("Список регіонів видалено.")


@bot.slash_command(description="показати налаштування")
@commands.guild_only()
async def show_config(ctx: discord.ApplicationContext):
    await ctx.defer()
    config = await store.get(ctx.guild.id)
    if not config:
        await ctx.respond("Бота не налаштовано!")
        return
    view = ShowConfig(config[1], config[2])
    view.message = await ctx.respond(
        f"""Канал: <#{config[0]}>
Обрані регіони: {
    ", ".join(REGION_NAMES[i] for i in config[3]) if config[3] else "вся Україна"
}.""",
        allowed_mentions=discord.AllowedMentions.none(),
        view=view,
    )


class ShowConfig(discord.ui.View):
    def __init__(self, msg1, msg2):
        super().__init__(
            ShowMessage("Показати сповіщення про тривогу", msg1),
            ShowMessage("Показати сповіщення про відбій тривоги", msg2),
            timeout=120,
        )
        self.message = None

    async def on_timeout(self) -> None:
        self.disable_all_items()
        await self.message.edit(view=self)


class ShowMessage(discord.ui.Button):
    def __init__(self, label, msg):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.msg = msg

    async def callback(self, interaction: discord.Interaction):
        text, embed = load_template(self.msg)
        await interaction.response.send_message(text, embed=embed, ephemeral=True)


@bot.slash_command(description="видалити налаштування")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def delete_config(ctx: discord.ApplicationContext):
    await ctx.defer()
    await store.delete(ctx.guild.id)
    await ctx.respond("Налаштування видалено.")


@bot.slash_command(description="показати поточну карту")
async def map(ctx: discord.ApplicationContext):
    await ctx.defer()
    start = time()
    data = await render_map()
    logging.info(f"Rendering took {time()-start:.2f}")
    await ctx.respond(file=discord.File(BytesIO(data), filename="map.png"))


def format_message(text: str, data: dict):
    return PLACEHOLDER.sub(lambda m: data.get(m.group(1)), text)


def load_template(template: str) -> tuple[str, Optional[discord.Embed]]:
    try:
        data = json.loads(template)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return (
            data.get("content", ""),
            discord.Embed.from_dict(data["embed"]) if data.get("embed") else None,
        )
    return template, None


async def show_and_reserialize(ctx, template: str):
    text, embed = load_template(format_message(template, {"image": DEFAULT_IMAGE_URL}))
    if not any(x in MANDATORY for x in PLACEHOLDER.findall(template)):
        text = "%name%\n" + text
    await ctx.respond(text, embed=embed, ephemeral=True)
    text, embed = load_template(template)
    return json.dumps({"content": text, "embed": embed.to_dict() if embed else {}})


async def send_alarm(data: dict):
    pending_updates: list[tuple[discord.Message, str]] = []
    data["image"] = DEFAULT_IMAGE_URL
    for channel_id, text_begin, text_end in await store.get_for(data["id"]):
        channel = bot.get_channel(channel_id)
        if not channel or not channel.permissions_for(channel.guild.me).send_messages:
            continue
        text = text_begin if data["alert"] else text_end
        msg, embed = load_template(format_message(text, data))
        message = await channel.send(msg, embed=embed)
        if "%image%" in text:
            pending_updates.append((message, text))

    async def update_pending():
        image = await render_map()
        data["image"] = (await bot.loop.run_in_executor(None, upload_image, image)).url
        for message, text in pending_updates:
            msg, embed = load_template(format_message(text, data))
            await message.edit(content=msg, embed=embed)

    bot.loop.create_task(update_pending())


def run():
    bot.loop.create_task(api.listen(send_alarm))
    bot.run(getenv("TOKEN"))


if __name__ == "__main__":
    run()
