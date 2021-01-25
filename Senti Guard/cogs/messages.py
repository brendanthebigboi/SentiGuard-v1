import datetime
import re

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command
from durations_nlp import Duration

USER_MENTION = re.compile("<@(?:!|)(\d+)>")
ROLE_MENTION = re.compile("<@&(\d+)>")
DEFAULT_EMOJI = re.compile("[\U0001F000-\U0001FFFF]")
CUSTOM_EMOJI = re.compile(r'<a?:[a-zA-Z0-9\__]+:([0-9]+)>')

class MessageTracking(Cog):
    def __init__(self, bot):
        self.bot = bot

    def find_mentions(self, content: str):
        return len(USER_MENTION.findall(content))+len(ROLE_MENTION.findall(content))
    
    def find_emojis(self, content: str):
        return len(DEFAULT_EMOJI.findall(content))+len(CUSTOM_EMOJI.findall(content))

    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        
        if not message.guild:
            return

        server = message.guild
        author = message.author
        channel = message.channel

        mentions = self.find_mentions(message.content)
        emojis = self.find_emojis(message.content)
        lines = len(message.content.split('\n'))
        characters = len(message.content)

        await self.bot.db.execute("""
        INSERT INTO messages (
            message_id,
            guild_id,
            author_id,
            channel_id,
            content,
            emojis,
            mentions,
            chars,
            lines,
            bot,
            created_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
        )
        """, message.id, server.id, author.id, channel.id, message.content, emojis, mentions, characters, lines, author.bot, message.created_at)
        await self.reminders.create_timer(
            datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + 30),
            'tempmessage',
            server.id,
            author.id,
            message.id,
            channel.id,
            created=message.created_at
        )

    @command(name="message", usage="<channel:snowflake> <duration:time> <message:text>", brief="Send a message every X time in a specified channel.")
    @commands.has_guild_permissions(manage_guild=True)
    async def message(self, ctx, channel: discord.TextChannel, duration, *, message: commands.clean_content):
        """Send a message every X time in a specified channel."""

        server = ctx.guild

        seconds = Duration(duration).to_seconds()
        dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)

        timed_messages = await ctx.fetch("SELECT * FROM timed_messages WHERE guild_id=$1", server.id)
        await ctx.execute("""
        INSERT INTO timed_messages (
            guild_id,
            time_id,
            user_id,
            channel_id,
            message,
            created_at,
            duration
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
        """, server.id, len(timed_messages)+1, ctx.author.id, channel.id, message, datetime.datetime.utcnow(), duration)

        await self.reminders.create_timer(dt_obj, 'message', ctx.guild.id, message, channel.id, seconds, len(timed_messages)+1, created=ctx.message.created_at)
        await ctx.send(f"{self.bot.check} There will be a message sent in {channel.mention} every {duration}. (`ID: {len(timed_messages)+1}`)")

    @command(name="messages")
    @commands.has_guild_permissions(manage_guild=True)
    async def messages(self, ctx):

        server = ctx.guild

        timed_messages = await ctx.fetch("SELECT * FROM timed_messages WHERE guild_id=$1", server.id)

        all_together = []
        for msg in timed_messages:
            if len(msg['message']) > 70:
                message = f"{msg['message'][:70 ]}..."
            else:
                message = msg['message']
            channel = server.get_channel(msg['channel_id'])
            all_together.append(
                f"[#{msg['time_id']:,} | #{channel.name} | {msg['duration']}] - {message}"
            )
        
        all = "\n".join(all_together) if all_together else 'There are no added timed messages.'
        await ctx.send(f"```cs\n{all}\n```")
    
    @command(name="delete_message")
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_message(self, ctx, time_id: int):

        server = ctx.guild

        deleted = await ctx.execute("DELETE FROM timed_messages WHERE guild_id=$1 AND time_id=$2", server.id, time_id)

        if not deleted:
            await ctx.send(f"{self.bot.x} I could not find a timed mssage with that ID.")
        
        await ctx.send(f"{self.bot.check} Deleted that timed message.")
    
    @Cog.listener()
    async def on_message_timer_complete(self, timer):
        guild_id, message, channel_id, seconds, time_id = timer.args

        guild = self.bot.get_guild(guild_id)
        if not guild: return

        channel = guild.get_channel(channel_id)
        if not channel: return

        timed_message = await self.bot.db.fetchrow("SELECT * FROM timed_messages WHERE guild_id=$1 AND time_id=$2", guild.id, time_id)
        if not timed_message:
            return

        dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
        await self.reminders.create_timer(dt_obj, 'message', guild.id, message, channel.id, seconds, time_id, created=datetime.datetime.utcnow())

        await channel.send(message)

    @Cog.listener()
    async def on_tempmessage_timer_complete(self, timer):
        guild_id, author_id, message_id, channel_id = timer.args
        await self.bot.wait_until_ready()

        await self.bot.db.execute("DELETE FROM messages WHERE message_id=$1", message_id)
        

def setup(bot):
    bot.add_cog(MessageTracking(bot))