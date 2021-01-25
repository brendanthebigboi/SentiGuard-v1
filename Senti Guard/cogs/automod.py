import datetime
import asyncio
import re
import aiohttp

import discord
from discord.ext import commands
from discord.ext.commands import Cog

from .utils import time
from .utils import ratelimit
from config import *

WEB_LINK = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
DISCORD_INVITE = re.compile(r'discord(\.com|\.gg)[\/invite\/]?(?:(?!.*[Ii10OolL]).[a-zA-Z0-9]{5,6}|[a-zA-Z0-9\-]{2,32})')

class Automod(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blacklisted_words = [
            'nigger',
            'n.i.g.g.e.r',
            'nigga',
            'n1g',
            'n.i.g.g.a',
            'nigg',
            'n.i.g.g',
            'n i g g e r',
            'n i g g a',
            'n1ga',
            'n1gga',
            'nibba',
            'neggros',
            'f4ggot',
            'f4gg0t',
            'maggot',
            'f4g',
            'n!gger',
            'Ñigg€r',
            'nigg=r',
            'Ñ*gga',
            'Ñ*gger',
            'Ñïgga',
            'Ñ.gerr',
            'fag',
            'fags',
            'chink',
            'coon',
            'c0on',
            'co0n',
            '©️oon',
            '©️0on',
            '©️o0n',
            'c00n',
            'faggot',
            'spic',
            'spicc',
            'spiccs',
            'negro',
            'negros',
            'niga',
            'nige',
            'niges',
            'nigas',
            'n1gga',
            'n1ggas',
            'niggers',
            'Ñig',
            'Nig',
            'ñig',
            'Ńig',
            'nîg',
            'nïg',
            'níg',
            'nīg',
            'nįg',
            'nìg',
            'ńigga',
            'ñigga'
            'nîgga',
            'nîggà',
            'nïgga',
            'nígga',
            'nīgga',
            'nįgga',
            'nìgga',
            'niggà',
            'Niggá',
            'Niggâ',
            'Niggä',
            'Niggæ',
            'Niggã',
            'Niggå',
            'Niggā'
            'nîgger',
            'nïgger',
            'nígger',
            'nīgger',
            'nįgger',
            'nìgger',
            'ñigger',
            'ńigger',
            'niggèr',
            'niggér',
            'niggêr',
            'niggër',
            'niggēr',
            'niggėr',
            'niggęr',
            'ńîggèr',
            'nïggér',
            'níggêr',
            'njjja',
            'njgga',
            'niuua',
            'Nig*er',
            'Nig/ger',
            'kigger',
            'knigger',
            '￦igger',
            '￦igga',
            'n1gg4',
            'nigg4',
            'n igga',
            'ni gga',
            'n i g g a',
            'ni g g a',
            'nigg a',
            'niggger',
            'nibbber',
            'nibber',
            'FĀGGET',
            'fĀgget',
            'FĀGGOT',
            'fĀggot',
            'nagger',
            'nagga',
            'n igga',
            'n igger',
            'n i g g e r',
            'n i g g a',
            'Níggèr',
            'n igga',
            'ni gga',
            'n i gga',
            'nig ga',
            'faggót',
            'fa ggót',
            'fag gót',
            'fagg ót',
            'faggó t',
            "n!gger"
        ]
        self.headers = {'api-key': 'ca5907f3-9cf2-4ef2-b40c-bdcc9020e122'}

    @property
    def modlog(self):
        return self.bot.get_cog("Modlog")
    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")
    @property
    def invites(self):
        return self.bot.get_cog("InviteTracking")
    @property
    def auto_emergency(self):
        return self.bot.get_cog("AutoEmergency")

    async def check_nsfw(self, message: discord.Message):
        link_found = None
        if (not message.attachments or not message.attachments[0].width):
            link =  r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            regex = re.compile(link)
            emojis = re.compile(r'<a?:[a-zA-Z0-9\__]+:([0-9]+)>')
            emojis_found = emojis.findall(message.content)
            if regex.findall(message.content):
                link_found = regex.findall(message.content)[0]
                pass
            elif emojis_found:
                emoji_id = int(emojis_found[0])
                link_found = f"https://cdn.discordapp.com/emojis/{emoji_id}"
            else:
                return {'nsfw': False}

        if not link_found:
            link_found = message.attachments[0].proxy_url

        data = None
        fields = {
            "image": link_found
        }

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.deepai.org/api/nsfw-detector", data=fields, headers=self.headers) as resp:
                data = await resp.json()

        print(data)
        if not "output" in data:
            return {'nsfw': False}

        rawData = data['output']
        nsfw_score = rawData['nsfw_score']
        print(nsfw_score*100)
        if nsfw_score < .55:
            return {'nsfw': False}
        
        return {'nsfw': True, 'chance': nsfw_score*100}

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        message = after
        if not message.guild or message.author == self.bot.user or message.channel.id in self.bot.no_touch:
            return
        
        server = message.guild
        try:
            no_restrictions = [role for role in server.get_member(message.author.id).roles if role.name.lower() == "no restrictions" and server.get_member(message.author.id)]
            if no_restrictions:
                return
        except:
            return

        channels = [
            742368134425739284,
            740748530863439913,
            740755301510414367,
            740997853425434724,
            796781293412417556 ,
            793763570302189590
        ]

        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
        duplicated_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND content=$4
        """, server.id, message.author.id, message.channel.id, message.content)
        duplicated_messages = [m for m in duplicated_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=13)]

        channel_duplicated_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND channel_id=$2 
        AND content=$3
        """, server.id, message.channel.id, message.content)
        channel_duplicated_messages = [m for m in channel_duplicated_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=20)]

        burst_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        """, server.id, message.author.id, message.channel.id)
        burst_messages = [m for m in burst_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=2)]

        mentions = 0
        mention_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND mentions > 0
        """, server.id, message.author.id, message.channel.id)
        mention_messages = [m for m in mention_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=30)]
        for m in mention_messages:
            mentions += m['mentions']

        emojis = 0
        emoji_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND emojis > 0
        """, server.id, message.author.id, message.channel.id)
        emoji_messages = [m for m in emoji_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=20)]
        for m in emoji_messages:
            emojis += m['emojis']
        
        muted_role = server.get_role(mutedrole[server.id])
        nsfw = await self.check_nsfw(message)

        if len(duplicated_messages) >= 8:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*3

            duration = (duplicated_messages[-1]['created_at']-duplicated_messages[0]['created_at']).seconds
            reason = f"Duplicated messages **({len(duplicated_messages)} messages/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antidup", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in duplicated_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)

        elif len(channel_duplicated_messages) >= 13:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

 

            seconds = 10*60
            duration = (channel_duplicated_messages[-1]['created_at']-channel_duplicated_messages[0]['created_at']).seconds
            reason = f"Multiple duplicated messages sent in a short period of time\n**Interval:** {len(duplicated_messages)} messages in {duration} seconds"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
            until_dt_fm = until_dt_obj.strftime("%A, %B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)
            await message.channel.send(f":shield: This channel has gone into lockdown for **{time_str}**. `({len(channel_duplicated_messages)} messages/{duration} seconds)`")
            await self.reminders.create_timer(until_dt_obj, 'templock', server.id, self.bot.user.id, message.channel.id, 0, created=message.created_at)

        elif len(burst_messages) >= 5:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*3

            duration = (burst_messages[-1]['created_at']-burst_messages[0]['created_at']).seconds
            reason = f"Burst messages **({len(burst_messages)} messages/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antiburst", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in burst_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif mentions >= 8:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return
            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*8

            duration = (mention_messages[-1]['created_at']-mention_messages[0]['created_at']).seconds
            reason = f"Mass mentions **({mentions} mentions/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)
            await self.auto_emergency.add_log(server, "automod", "massmentions", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in mention_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif emojis >= 8:
            
            duration = (emoji_messages[-1]['created_at']-emoji_messages[0]['created_at']).seconds
            reason = f"Multiple emojis **({emojis} emojis/{duration} seconds)**"
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, reason)
            await self.auto_emergency.add_log(server, "automod", "massemojis", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in emoji_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif len(message.content.split('\n')) >= 12 and message.channel.id != 741000647188414504 or len(message.content) >= 1200 and message.channel.id != 741000647188414504:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*1

            lines = len(message.content.split('\n'))
            reason = f"Message containing flood content. **({lines} lines and {len(message.content)} characters)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antiflood", message.channel)
            await message.delete()
        elif any(word in message.content.lower().split() for word in self.blacklisted_words) and server.id != 658089953837842432:
            
            w = " ".join([word for word in message.content.lower().split() if word in self.blacklisted_words])
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Censored word (**{w}**)")
        elif DISCORD_INVITE.findall(message.content) and message.channel.id not in self.bot.no_touch and message.channel.id not in channels:
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Message contained a Discord invite.")
        elif WEB_LINK.findall(message.content) and "https://tenor.com" not in message.content.lower() and "https://cdn.discordapp.com" not in message.content.lower() and "https://discord.com" not in message.content.lower() and message.channel.id != 776914709797404704 and message.channel.id != 774936763311325215 and message.channel.id not in channels:
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Message contained a web link.")
        elif nsfw['nsfw'] == True:
            
            await message.delete()

            try:
                await message.author.add_roles(muted_role)
            except:
                return
            
            seconds = 3600*3
            reason = f"Sent a message that contained a **{nsfw['chance']:.2f}%** NSFW rating."
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (NSFW Score {nsfw['chance']:.2f}) (`Case #{case}`)")
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)


    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author == self.bot.user or message.channel.id in self.bot.no_touch:
            return
        
        server = message.guild
        try:
            no_restrictions = [role for role in server.get_member(message.author.id).roles if role.name.lower() == "no restrictions" and server.get_member(message.author.id)]
            if no_restrictions:
                return
        except:
            return

        channels = [
            742368134425739284,
            740748530863439913,
            740755301510414367,
            740997853425434724,
            796781293412417556 ,
            793763570302189590
        ]

        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
        duplicated_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND content=$4
        """, server.id, message.author.id, message.channel.id, message.content)
        duplicated_messages = [m for m in duplicated_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=13)]

        channel_duplicated_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND channel_id=$2 
        AND content=$3
        """, server.id, message.channel.id, message.content)
        channel_duplicated_messages = [m for m in channel_duplicated_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=20)]

        burst_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        """, server.id, message.author.id, message.channel.id)
        burst_messages = [m for m in burst_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=2)]

        mentions = 0
        mention_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND mentions > 0
        """, server.id, message.author.id, message.channel.id)
        mention_messages = [m for m in mention_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=30)]
        for m in mention_messages:
            mentions += m['mentions']

        emojis = 0
        emoji_messages = await self.bot.db.fetch("""
        SELECT * FROM messages
        WHERE guild_id=$1 AND author_id=$2 
        AND channel_id=$3
        AND emojis > 0
        """, server.id, message.author.id, message.channel.id)
        emoji_messages = [m for m in emoji_messages if datetime.datetime.utcnow()-m['created_at']<datetime.timedelta(seconds=20)]
        for m in emoji_messages:
            emojis += m['emojis']
        
        muted_role = server.get_role(mutedrole[server.id])
        nsfw = await self.check_nsfw(message)

        if len(duplicated_messages) >= 8:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*3

            duration = (duplicated_messages[-1]['created_at']-duplicated_messages[0]['created_at']).seconds
            reason = f"Duplicated messages **({len(duplicated_messages)} messages/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await self.bot.db.fetch(query, str(server.id), str(message.author.id))
            if records:
                old_unmute_dt = records[0]['expires']
                old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)

                await self.bot.db.execute("""
                UPDATE reminders SET expires=$1
                WHERE event = 'tempmute'
                AND extra #>> '{args,0}' = $2
                AND extra #>> '{args,2}' = $3
                """, new_unmute_dt, str(server.id), str(message.author.id))
                self.bot.dispatch("timer_edit", server)
            else:  
                await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antidup", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in duplicated_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)

        elif len(channel_duplicated_messages) >= 13:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

 

            seconds = 10*60
            duration = (channel_duplicated_messages[-1]['created_at']-channel_duplicated_messages[0]['created_at']).seconds
            reason = f"Multiple duplicated messages sent in a short period of time\n**Interval:** {len(duplicated_messages)} messages in {duration} seconds"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
            until_dt_fm = until_dt_obj.strftime("%A, %B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)
            await message.channel.send(f":shield: This channel has gone into lockdown for **{time_str}**. `({len(channel_duplicated_messages)} messages/{duration} seconds)`")
            await self.reminders.create_timer(until_dt_obj, 'templock', server.id, self.bot.user.id, message.channel.id, 0, created=message.created_at)

        elif len(burst_messages) >= 5:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*3

            duration = (burst_messages[-1]['created_at']-burst_messages[0]['created_at']).seconds
            reason = f"Burst messages **({len(burst_messages)} messages/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await self.bot.db.fetch(query, str(server.id), str(message.author.id))
            if records:
                old_unmute_dt = records[0]['expires']
                old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)

                await self.bot.db.execute("""
                UPDATE reminders SET expires=$1
                WHERE event = 'tempmute'
                AND extra #>> '{args,0}' = $2
                AND extra #>> '{args,2}' = $3
                """, new_unmute_dt, str(server.id), str(message.author.id))
                self.bot.dispatch("timer_edit", server)
            else:  
                await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antiburst", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in burst_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif mentions >= 8:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return
            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*8

            duration = (mention_messages[-1]['created_at']-mention_messages[0]['created_at']).seconds
            reason = f"Mass mentions **({mentions} mentions/{duration} seconds)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
           
            await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await self.bot.db.fetch(query, str(server.id), str(message.author.id))
            if records:
                old_unmute_dt = records[0]['expires']
                old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)

                await self.bot.db.execute("""
                UPDATE reminders SET expires=$1
                WHERE event = 'tempmute'
                AND extra #>> '{args,0}' = $2
                AND extra #>> '{args,2}' = $3
                """, new_unmute_dt, str(server.id), str(message.author.id))
                self.bot.dispatch("timer_edit", server)
            else:  
                await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in mention_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif emojis >= 8:
            
            duration = (emoji_messages[-1]['created_at']-emoji_messages[0]['created_at']).seconds
            reason = f"Multiple emojis **({emojis} emojis/{duration} seconds)**"
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, reason)
            await self.auto_emergency.add_log(server, "automod", "massemojis", message.channel)
            def check(m):
                return m.author.id == message.author.id and [m_ for m_ in emoji_messages if m.id == m_['message_id']]
            history = await message.channel.history().filter(check).flatten()
            await message.channel.delete_messages(history)
        elif len(message.content.split('\n')) >= 12 and message.channel.id != 741000647188414504 or len(message.content) >= 1200 and message.channel.id != 741000647188414504:
            ratelimited = ratelimit.ratelimit_dup(message, current)
            if ratelimited: return

            try:
                await message.author.add_roles(muted_role)
            except:
                pass

            seconds = 3600*1

            lines = len(message.content.split('\n'))
            reason = f"Message containing flood content. **({lines} lines and {len(message.content)} characters)**"
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (`Case #{case}`)")
            
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await self.bot.db.fetch(query, str(server.id), str(message.author.id))
            if records:
                old_unmute_dt = records[0]['expires']
                old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)

                await self.bot.db.execute("""
                UPDATE reminders SET expires=$1
                WHERE event = 'tempmute'
                AND extra #>> '{args,0}' = $2
                AND extra #>> '{args,2}' = $3
                """, new_unmute_dt, str(server.id), str(message.author.id))
                self.bot.dispatch("timer_edit", server)
            else:  
                await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)

            await self.auto_emergency.add_log(server, "automod", "antiflood", message.channel)
            await message.delete()
        elif any(word in message.content.lower().split() for word in self.blacklisted_words) and server.id != 658089953837842432:
            
            w = " ".join([word for word in message.content.lower().split() if word in self.blacklisted_words])
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Censored word (**{w}**)")
        elif DISCORD_INVITE.findall(message.content) and message.channel.id not in self.bot.no_touch and message.channel.id not in channels:
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Message contained a Discord invite.")
        elif WEB_LINK.findall(message.content) and "https://tenor.com" not in message.content.lower() and "https://cdn.discordapp.com" not in message.content.lower() and "https://discord.com" not in message.content.lower() and message.channel.id != 776914709797404704 and message.channel.id != 774936763311325215 and message.channel.id not in channels:
            await message.delete()
            await self.modlog.warn(server, message.author, message.channel, self.bot.user, f"Message contained a web link.")
        elif nsfw['nsfw'] == True:
            
            await message.delete()

            try:
                await message.author.add_roles(muted_role)
            except:
                return
            
            seconds = 3600*3
            reason = f"Sent a message that contained a **{nsfw['chance']:.2f}%** NSFW rating."
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
            time_str = time.human_timedelta(until_dt_obj)

            case = await self.modlog.create_case(server, message.author, self.bot.user, "Mute", reason, time_str)
            await message.channel.send(f"{self.bot.check} Applied a mute to **{message.author}** until {until_dt_fm} ({time_str}). (NSFW Score {nsfw['chance']:.2f}) (`Case #{case}`)")
            
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await self.bot.db.fetch(query, str(server.id), str(message.author.id))
            if records:
                old_unmute_dt = records[0]['expires']
                old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)

                await self.bot.db.execute("""
                UPDATE reminders SET expires=$1
                WHERE event = 'tempmute'
                AND extra #>> '{args,0}' = $2
                AND extra #>> '{args,2}' = $3
                """, new_unmute_dt, str(server.id), str(message.author.id))
                self.bot.dispatch("timer_edit", server)
            else:  
                await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, self.bot.user.id, message.author.id, case, created=message.created_at)


    @Cog.listener()
    async def on_member_join(self, member):
        await asyncio.sleep(0.1)
        server = member.guild

        latest = [m for m in server.members if round(datetime.datetime.utcnow().timestamp()-m.joined_at.timestamp()) < 15]
        muted_role = server.get_role(mutedrole[server.id])

        if len(latest) >= 6:
            
            for m in latest:
                try:
                    await m.add_roles(muted_role)
                except:
                    pass

                try:
                    await m.send(f":shield: You have been muted in **{server}** for triggering the raid-shield. If this is a mistake, please DM a staff member.")
                except:
                    pass
                
                invite = await self.invites.track_user(server, m)

                if not invite:
                    invite = "Not found."
                else:
                    code = invite[1]
                    inviter = server.get_member(invite[2])
                    if not inviter:
                        inviter = "Unknown"
                    else:
                        inviter = f"**{inviter}** (ID: {inviter.id})"
                    invite = f"`{code}` {inviter}"
                
                await self.modlog.create_case(server, m, self.bot.user, "Mute", f"Triggering the raid-shield, multiple users joined in a short time.\n**Invite:** {invite}", "Indefinite")

def setup(bot):
    bot.add_cog(Automod(bot))