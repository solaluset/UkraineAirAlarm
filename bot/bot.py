import logging
import re
from time import time
from os import getenv
from io import BytesIO

import discord
from discord.ext import commands
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
    embed.add_field(
        name="2.",
        value="""Скористайтеся командою /configure
Оберіть канал, в який будуть приходити повідомлення.
Вкажіть, який текст має бути надісланий при оголошенні тривоги та її відбою.
Використовуйте `%name%`, щоб підставити назву області в текст, або
`%name_en%` для назви англійською.
""",
        inline=False,
    )
    embed.add_field(
        name="3.",
        value="""Готово! Всі сповіщення будуть приходити в канал, що ви вказали.
Налаштування можна перевірити за допомогою команди /show_config
Якщо хочете відключити бота, використайте /delete_config""",
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
    await ctx.defer()
    # fix for pycord permissions issue
    # https://github.com/Pycord-Development/pycord/issues/1283
    channel = ctx.guild.get_channel(channel.id)
    if not channel.permissions_for(ctx.guild.me).send_messages:
        await ctx.respond("У бота немає прав писати у вказаний канал!")
        return
    await store.set(
        ctx.guild.id, channel.id, force_name(text_begin), force_name(text_end)
    )
    await ctx.respond("Готово!")


@bot.slash_command(description="додати регіон до списку")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def add_region(
    ctx: discord.ApplicationContext, region: discord.Option(int, choices=REGION_OPTIONS)
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
    ctx: discord.ApplicationContext, region: discord.Option(int, choices=REGION_OPTIONS)
):
    await ctx.defer()
    if await store.remove_region(ctx.guild.id, region):
        await ctx.respond("Регіон видалено зі списку.")
    else:
        await ctx.respond("Регіона немає в списку або бота не налаштовано.")


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
    await ctx.respond(
        f"""Канал: <#{config[0]}>
Текст сповіщення про тривогу: {config[1]}
Текст сповіщення про відбій тривоги: {config[2]}""",
        allowed_mentions=discord.AllowedMentions.none(),
    )


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


def force_name(text: str):
    if not any(x in MANDATORY for x in PLACEHOLDER.findall(text)):
        return "%name%\n" + text
    return text


async def send_alarm(data: dict):
    for channel_id, text_begin, text_end in await store.get_for(data["id"]):
        channel = bot.get_channel(channel_id)
        if not channel or not channel.permissions_for(channel.guild.me).send_messages:
            continue
        text = text_begin if data["alert"] else text_end
        await channel.send(format_message(text, data))


def run():
    bot.loop.create_task(api.listen(send_alarm))
    bot.run(getenv("TOKEN"))


if __name__ == "__main__":
    run()
