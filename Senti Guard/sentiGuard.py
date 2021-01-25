import datetime
import aiohttp

import discord
from discord.ext import commands
from discord.ext.commands import AutoShardedBot
import yaml
import asyncpg
import aioredis

from cogs.utils.context import Context
from config import *

with open("config.yaml", "rb") as file:
    config = yaml.safe_load(file)

intents = discord.Intents.default()
intents.members = True

def get_prefix(bot, message):
    guild = message.guild

    return [f"<@{bot.user.id}> ", f"<@!{bot.user.id} ", prefixes[guild.id]]

class FeudalGuard(AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            intents=intents
        )

        self.check = ":ok_hand:"
        self.x = ":stop_sign:"

        self.db = None
        self.redis = None
        self.config = config
        # self.session = aiohttp.ClientSession(loop=self.loop)

        self.unloaded_cogs = [
            "cogs.moderation",
            "cogs.utils.modlog",
            "cogs.developer",
            "cogs.reminders",
            "cogs.invites",
            "cogs.automod",
            "cogs.messages",
            "cogs.stats",
            "cogs.utils.auto_emergency",
            "cogs.antinuke",
            "cogs.error_handler",
            "cogs.sticky_roles"
        ]
        self.no_touch = [
            447948554888282113, #Media
            418014922635476993, #community-content
            685928700373762104, # clan ads
            764514835676397588, #suggestions
            765360953079758868, # 20
            776914709797404704 # media
        ]

        self.blacklist = []

        self.add_check(self.global_command_check)

    async def on_ready(self):

        self.uptime = datetime.datetime.utcnow()
        print(f"""
  ______             _       _  _____                     _ 
 |  ____|           | |     | |/ ____|                   | |
 | |__ ___ _   _  __| | __ _| | |  __ _   _  __ _ _ __ __| |
 |  __/ _ \ | | |/ _` |/ _` | | | |_ | | | |/ _` | '__/ _` |
 | | |  __/ |_| | (_| | (_| | | |__| | |_| | (_| | | | (_| |
 |_|  \___|\__,_|\__,_|\__,_|_|\_____|\__,_|\__,_|_|  \__,_|
 FeudalGuard is now online and ready to roll!
 Starting at {self.uptime}.
 Serving {len(self.guilds):,} guilds and {len(self.users):,} users.                                                          
        """)

    # async def _create_redis_session(self) -> None:

    #     # pylint: disable=no-member
    #     self.redis = await aioredis.create_redis_pool(
    #         address=(config['Redis']['host'], config['Redis']['port']),
    #         # password=constants.Redis.password
    #     )
    #     print("Redis connection has been established.")

    async def _create_postgres_session(self) -> None:

        # pylint: disable=no-member
        self.db = await asyncpg.create_pool(
            host=config['Postgres']['host'],
            port=config['Postgres']['port'],
            database=config['Postgres']['database'],
            user=config['Postgres']['user'],
            password=config['Postgres']['password']
        )
        print("Postgres connection has been established.")

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS censors (
            word text
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS nukes (
            guild_id bigint,
            user_id bigint,
            nuke_type text,
            id bigint,
            logged_at timestamp
        )
        """)
        
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            guild_id bigint,
            type text,
            created_at timestamp,
            classifier text
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id bigint,
            guild_id bigint,
            author_id bigint,
            channel_id bigint,
            content varchar(2000),
            emojis smallint,
            mentions smallint,
            chars smallint,
            lines smallint,
            bot boolean,
            created_at timestamp
        )
        """)

        await self.db.execute("""
         CREATE TABLE IF NOT EXISTS cases (
            case_id integer,
            guild_id bigint,
            user_id bigint,
            moderator_id bigint,
            message_id bigint,
            action text,
            type smallint,
            created_at timestamp,
            duration text,
            reason varchar(2000),
            jump_url text
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS usernames (
            user_id bigint,
            before_name text,
            after_name text,
            changed_at timestamp
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS nicknames (
            guild_id bigint,
            user_id bigint,
            before_name text,
            after_name text,
            changed_at timestamp
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id bigint,
            online text[],
            offline text[],
            dnd text[],
            idle text[],
            current_status text,
            current_status_since timestamp
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            guild_id bigint,
            code text primary key,
            uses smallint,
            max_uses smallint,
            users jsonb,
            inviter bigint
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id serial primary key,
            expires timestamp,
            created timestamp,
            event text,
            extra json
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS force_mutes (
            guild_id bigint,
            user_id bigint,
            moderator_id bigint,
            duration jsonb,
            reason varchar(2000)
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            guild_id bigint,
            channel_id bigint,
            author_id bigint,
            used_at timestamp,
            prefix text,
            command text,
            failed boolean
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS sticky_roles (
            guild_id bigint,
            user_id bigint,
            roles bigint[],
            nick varchar(32)
        )
        """)

        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS timed_messages (
            guild_id bigint,
            time_id integer,
            user_id bigint,
            channel_id bigint,
            message varchar(2000),
            created_at timestamp,
            duration text
        )
        """)

    async def _load_cogs(self):

        for cog in self.unloaded_cogs:
            try:
                self.load_extension(cog)
                print(f"Loaded {cog}!")
            except Exception as e:
                print(f"Failed {cog}: {e}")

    async def login(self, *args, **kwargs):

        await self._load_cogs()
        await self._create_postgres_session()
        # await self._create_redis_session()

        await super().login(*args, **kwargs)

    async def get_context(self, message, cls=None):
        if not message.guild or message.author.bot:
            return None
        return await super().get_context(message, cls=cls)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)
        if not ctx or ctx.command is None:
            return

        await self.invoke(ctx)

    async def global_command_check(self, ctx):
        channel = ctx.channel
        user = ctx.author

        if channel.permissions_for(user).manage_messages is False and channel.id == 606974489397559326:
            return False 
        else:
            return True
        

bot = FeudalGuard()
bot.load_extension('jishaku')

bot.run(config['token'])