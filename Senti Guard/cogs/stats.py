import datetime
import re
from collections import Counter
import json
import asyncio
import numpy as np
import aiohttp

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command, Context, CooldownMapping, BucketType, has_guild_permissions

from .utils import time
from .utils.converters import DiscordUser
from .utils import arg

_INVITE_REGEX = re.compile(r'(?:https?:\/\/)?discord(?:\.gg|\.com|app\.com\/invite)?\/[A-Za-z0-9]+')

class Stats(Cog):
    def __init__(self, bot):
        self.bot = bot
        # self.rate_limit = CooldownMapping.from_cooldown(1, 5, BucketType.member)
        self._cache = []

    @property
    def invites(self):
        return self.bot.get_cog("InviteTracking")

    @Cog.listener()
    async def on_user_update(self, before, after):
        user = after
        if user.id in self._cache: return

        if before.name != after.name:
            await self.bot.db.execute("""
            INSERT INTO usernames (
                user_id,
                before_name,
                after_name,
                changed_at
            ) VALUES (
                $1, $2, $3, $4
            )
            """, user.id, before.name, after.name, datetime.datetime.utcnow())
            self._cache.append(user.id)
            await asyncio.sleep(1)
            self._cache.remove(user.id)

    @Cog.listener()
    async def on_socket_response(self, msg):

        self.bot.socket_stats[msg.get('t')] += 1

    @Cog.listener(name="on_member_update")
    async def member_update(self, before, after):
        server = after.guild
        user = after

        if user.id in self._cache: return
        
        if before.status != after.status:
            new_status = after.status.name.lower()
            user_stats = await self.bot.db.fetchrow("SELECT * FROM user_stats WHERE user_id=$1", user.id)
            index = 0 if user_stats and len(user_stats[new_status]) <= 1 else -1
            before_index = 0 if user_stats and len(user_stats[before.status.name]) <= 1 else -1
            if not user_stats:
                # add a new starting time for their status
                # bc we wil subtract the starting-time from the ending-time
                # this will get the amount of seconds for that run
                new_stats = [json.dumps({
                    "ending_time": 0,
                    "starting_time": round(datetime.datetime.utcnow().timestamp())
                })]

                query = f"""
                INSERT INTO user_stats (
                    user_id,
                    online,
                    offline,
                    dnd,
                    idle,
                    current_status,
                    current_status_since
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7
                )
                """
                await self.bot.db.execute(query, user.id, [] if new_status != "online" else new_stats, 
                [] if new_status != "offline" else new_stats, 
                [] if new_status != "dnd" else new_stats,
                [] if new_status != "idle" else new_stats,
                new_status,
                datetime.datetime.utcnow()
                )
            elif not user_stats[new_status]:
                # add a new starting time for their status
                user_stats[new_status].append(json.dumps({
                    "ending_time": 0,
                    "starting_time": round(datetime.datetime.utcnow().timestamp())
                }))

                query = f"""
                UPDATE user_stats
                SET {new_status}=$2
                WHERE user_id=$1;
                """
                await self.bot.db.execute(query, user.id, user_stats[new_status])
                if len(user_stats[before.status.name]) > 0 and json.loads(user_stats[before.status.name][before_index])["ending_time"] == 0:
                    old = json.loads(user_stats[before.status.name][before_index])['starting_time']
                    user_stats[before.status.name].remove(json.dumps({
                        "ending_time": 0,
                        "starting_time": json.loads(user_stats[before.status.name][before_index])['starting_time']
                    }))
                    user_stats[before.status.name].append(json.dumps({
                        "ending_time": round(datetime.datetime.utcnow().timestamp()),
                        "starting_time": old
                    }))

                    query = f"""
                    UPDATE user_stats
                    SET {before.status.name}=$2
                    WHERE user_id=$1;
                    """
                    await self.bot.db.execute(query, user.id, user_stats[before.status.name])

            elif json.loads(user_stats[new_status][index])["ending_time"] > 0:
                user_stats[new_status].append(json.dumps({
                    "ending_time": 0,
                    "starting_time": round(datetime.datetime.utcnow().timestamp())
                }))

                query = f"""
                UPDATE user_stats
                SET {new_status}=$2
                WHERE user_id=$1;
                """
                await self.bot.db.execute(query, user.id, user_stats[new_status])

                if len(user_stats[before.status.name]) > 0 and json.loads(user_stats[before.status.name][before_index])["ending_time"] == 0:
                    old = json.loads(user_stats[before.status.name][before_index])['starting_time']
                    user_stats[before.status.name].remove(json.dumps({
                        "ending_time": 0,
                        "starting_time": json.loads(user_stats[before.status.name][before_index])['starting_time']
                    }))
                    user_stats[before.status.name].append(json.dumps({
                        "ending_time": round(datetime.datetime.utcnow().timestamp()),
                        "starting_time": old
                    }))

                    query = f"""
                    UPDATE user_stats
                    SET {before.status.name}=$2
                    WHERE user_id=$1;
                    """
                    await self.bot.db.execute(query, user.id, user_stats[before.status.name])
            elif len(user_stats[before.status.name]) > 0 and json.loads(user_stats[before.status.name][before_index])["ending_time"] == 0:
                
                old = json.loads(user_stats[before.status.name][before_index])['starting_time']
                user_stats[before.status.name].remove(json.dumps({
                    "ending_time": 0,
                    "starting_time": json.loads(user_stats[before.status.name][before_index])['starting_time']
                }))
                user_stats[before.status.name].append(json.dumps({
                    "ending_time": round(datetime.datetime.utcnow().timestamp()),
                    "starting_time": old
                }))

                query = f"""
                UPDATE user_stats
                SET {before.status.name}=$2
                WHERE user_id=$1;
                """
                await self.bot.db.execute(query, user.id, user_stats[before.status.name])

            await self.bot.db.execute("""
            UPDATE user_stats
            SET current_status=$2, current_status_since=$3
            WHERE user_id=$1;
            """, user.id, new_status, datetime.datetime.utcnow())

            self._cache.append(user.id)
            await asyncio.sleep(1)
            self._cache.remove(user.id)
        if before.nick != after.nick:
            try:
                await self.bot.db.execute("""
                INSERT INTO nicknames (
                    guild_id,
                    user_id,
                    before_name,
                    after_name,
                    changed_at
                ) VALUES (
                    $1, $2, $3, $4, $5
                )
                """, server.id, user.id, before.nick, after.nick, datetime.datetime.utcnow())
                self._cache.append(user.id)
                await asyncio.sleep(1)
                self._cache.remove(user.id)
            except Exception as e:
                print(e)

    async def register_command(self, ctx):
        if ctx.command is None:
            return
        
        command = ctx.command.qualified_name
        message = ctx.message
        destination = None
        if message.guild is None:
            destination = "Private messages."
            guild_id = None
        else:
            destination = f"#{message.channel} ({message.guild})"
            guild_id = ctx.guild.id

        query = """
        INSERT INTO commands (
            guild_id,
            channel_id,
            author_id,
            used_at,
            prefix,
            command,
            failed
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        )
        """
        await self.bot.db.execute(query, guild_id, ctx.channel.id, ctx.author.id, message.created_at, ctx.prefix, command, ctx.command_failed)

    @Cog.listener(name="on_command_completion")
    async def command_completion(self, ctx):
        await self.register_command(ctx)

    @command()
    async def s(self, ctx, user: DiscordUser = None):
        user = user or ctx.author
        server = ctx.guild
        user_stats = await self.bot.db.fetchrow("SELECT * FROM user_stats WHERE user_id=$1", user.id)

        if user_stats:
            
            online_total_seconds = 0
            for log in user_stats['online']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    online_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                online_total_seconds += log['ending_time'] - log['starting_time']
            online_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+online_total_seconds), brief=True, suffix=False) if online_total_seconds > 1 else "0s"
            
            offline_total_seconds = 0
            for log in user_stats['offline']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    offline_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                offline_total_seconds += log['ending_time'] - log['starting_time']
            offline_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+offline_total_seconds), brief=True, suffix=False) if offline_total_seconds > 1 else "0s"

            dnd_total_seconds = 0
            for log in user_stats['dnd']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    dnd_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                dnd_total_seconds += log['ending_time'] - log['starting_time']
            dnd_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+dnd_total_seconds), brief=True, suffix=False) if dnd_total_seconds > 1 else "0s"

            idle_total_seconds = 0
            for log in user_stats['idle']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    idle_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                idle_total_seconds += log['ending_time'] - log['starting_time']
            idle_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+idle_total_seconds), brief=True, suffix=False) if idle_total_seconds > 1 else "0s"

            total = online_total_seconds+offline_total_seconds+dnd_total_seconds+idle_total_seconds
            online_percent = round(100 * online_total_seconds/total) if user_stats['online'] else 0
            offline_percent = round(100 * offline_total_seconds/total) if user_stats['offline'] else 0
            dnd_percent = round(100 * dnd_total_seconds/total) if user_stats['dnd'] else 0
            idle_percent = round(100 * idle_total_seconds/total) if user_stats['idle'] else 0


        invite_used = await self.invites.track_user(ctx.guild, user) if await self.invites.track_user(ctx.guild, user) else "not found"
        inviter_logs = await ctx.fetch("SELECT * FROM invites WHERE inviter=$2 and guild_id=$1", ctx.guild.id, user.id)
        total_invites = 0
        for log in inviter_logs:
            total_invites += log['uses']

        query = """SELECT content,
                          COUNT(*) AS "uses"
                   FROM messages
                   WHERE guild_id=$1 AND author_id=$2
                   GROUP BY content
                """
        messages = await ctx.fetch(query, server.id, user.id)
        timed_query = """SELECT content,
                          COUNT(*) AS "uses"
                   FROM messages
                   WHERE guild_id=$1 AND author_id=$2
                   AND created_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY content
                """
        today_messages = await ctx.fetch(timed_query, server.id, user.id)
        active_query = """
        SELECT channel_id,
            COUNT(*) AS "uses"
        FROM messages
        WHERE guild_id=$1 AND author_id=$2
        GROUP BY channel_id
        ORDER BY "uses" DESC
        LIMIT 1;
        """
        active_channel = await ctx.fetch(active_query, server.id, user.id)
        active_channel = server.get_channel(active_channel[0]['channel_id']).mention if len(active_channel) > 0 else "`doesn't have one`"

        username_query = """
        SELECT * FROM usernames
        WHERE user_id=$1
        ORDER BY changed_at DESC
        LIMIT 5;
        """
        usernames_ = await ctx.fetch(username_query, user.id)
        usernames = [log['after_name'] for log in usernames_]

        nickname_query = """
        SELECT * FROM nicknames
        WHERE user_id=$1 AND guild_id=$2
        ORDER BY changed_at DESC
        LIMIT 5;
        """
        nicknames_ = await ctx.fetch(nickname_query, user.id, server.id)
        nicknames = [log['after_name'] for log in nicknames_]

        embed = discord.Embed(color=discord.Color.blurple(), timestamp=datetime.datetime.utcnow())
        embed.set_author(name=user, icon_url=user.avatar_url)
        embed.add_field(name="Message Tracking", value="\n".join([
            f":keyboard: Has sent **{len(messages):,}** messages in total, **{len(today_messages):,}** of those being sent today.",
            f":first_place: Their most active channel is {active_channel}."
        ]))
        embed.add_field(name="Invite Tracking", value="\n".join([
            f":ticket: Joined the server using the invite code `{invite_used[1] if invite_used != 'not found' else 'not found'}` by **{server.get_member(invite_used[2]) if server.get_member(invite_used[2]) else 'unkown'}**.",
            f":e_mail: Invited **{total_invites:,}** users to this server."
        ]), inline=False)
        embed.add_field(name="Status Tracking", value="\n".join([
            f":stopwatch: Has been **{user_stats['current_status']}** for `{time.human_timedelta(user_stats['current_status_since'], brief=True, suffix=False)}`.",
            f"<:online:752328954076987502> Online **{online_percent}%** for `{online_time}` in total.",
            f"<:offline:752328954039500950> Offline **{offline_percent}%** for `{offline_time}` in total.",
            f"<:idle:752328953817071637> Idle **{idle_percent}%** for `{idle_time}` in total.",
            f"<:dnd:752328954085507172> DND **{dnd_percent}%** for `{dnd_time}` in total."
        ]) if user_stats else f"I have not tracked any stats for {user}.", inline=False)
        embed.add_field(name="Username Tracking", value="\n".join([name for name in usernames if name is not None]) if usernames else "No username changes tracked.", inline=True)
        embed.add_field(name="Nickname Tracking", value="\n".join([name for name in nicknames if name is not None]) if nicknames else "No nickname changes tracked.", inline=True)
        await ctx.send(embed=embed)

        # await ctx.send(
        #     f"**Online**\n{user_stats['online']}\n"
        #     f"**Offline**\n{user_stats['offline']}\n"
        #     f"**DND**\n{user_stats['dnd']}\n"
        #     f"**Idle**\n{user_stats['idle']}"
        # )
    
    @command(aliases=['ss'])
    async def socketstats(self, ctx):
        """Show all of the socketstats provided by Discord, these are the events like ON_MESSAGE_CREATE, etc.
        """
        delta = datetime.datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60

        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes
        
        stats = ""
        for stat, value in self.bot.socket_stats.items():
            if stat is None:
                continue

            stats += "{0:<30} {1:<15} {2:.2f}/m\n".format(stat, value, value/minutes)

        await ctx.send(f"{total:,} socket events observed ({cpm:.2f}/minute)\n```\n{stats}\n```")

    @Cog.listener(name="on_command_completion")
    async def command_completion(self, ctx):
        await self.register_command(ctx)

    def censor_invite(self, obj, *, _regex=_INVITE_REGEX):
        return _regex.sub('[censored-invite]', str(obj))

    def censor_object(self, obj):
        if not isinstance(obj, str) and obj.id in self.bot.blacklist:
            return '[censored]'
        return self.censor_invite(obj)

    async def show_guild_stats(self, ctx):
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}'
        )

        embed = discord.Embed(title='Server Command Stats', colour=discord.Colour.blurple())

        # total command uses
        query = "SELECT COUNT(*), MIN(used_at) FROM commands WHERE guild_id=$1;"
        count = await ctx.fetchrow(query, ctx.guild.id)

        embed.description = f'{count[0]} commands used.'
        embed.set_footer(text='Tracking command usage since').timestamp = count[1] or datetime.datetime.utcnow()

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query, ctx.guild.id)

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands'

        embed.add_field(name='Top Commands', value=value, inline=True)

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query, ctx.guild.id)

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands.'
        embed.add_field(name='Top Commands Today', value=value, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)

        query = """SELECT author_id,
                          COUNT(*) AS "uses"
                   FROM commands
                   WHERE guild_id=$1
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """


        records = await ctx.fetch(query, ctx.guild.id)

        value = '\n'.join(f'{lookup[index]}: <@!{author_id}> ({uses} bot uses)'
                          for (index, (author_id, uses)) in enumerate(records)) or 'No bot users.'

        embed.add_field(name='Top Command Users', value=value, inline=True)

        query = """SELECT author_id,
                          COUNT(*) AS "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """


        records = await ctx.fetch(query, ctx.guild.id)

        value = '\n'.join(f'{lookup[index]}: <@!{author_id}> ({uses} bot uses)'
                          for (index, (author_id, uses)) in enumerate(records)) or 'No command users.'

        embed.add_field(name='Top Command Users Today', value=value, inline=True)
        await ctx.send(embed=embed)

    async def show_member_stats(self, ctx, member):
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}'
        )

        embed = discord.Embed(title='Command Stats', colour=member.colour)
        embed.set_author(name=str(member), icon_url=member.avatar_url)

        # total command uses
        query = "SELECT COUNT(*), MIN(used_at) FROM commands WHERE guild_id=$1 AND author_id=$2;"
        count = await ctx.fetchrow(query, ctx.guild.id, member.id)

        embed.description = f'{count[0]} commands used.'
        embed.set_footer(text='First command used').timestamp = count[1] or datetime.datetime.utcnow()

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1 AND author_id=$2
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query, ctx.guild.id, member.id)

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands'

        embed.add_field(name='Most Used Commands', value=value, inline=False)

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND author_id=$2
                   AND used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query, ctx.guild.id, member.id)

        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)'
                          for (index, (command, uses)) in enumerate(records)) or 'No Commands'

        embed.add_field(name='Most Used Commands Today', value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def stats(self, ctx, *, member: discord.Member = None):
        """Tells you command usage stats for the server or a member."""
        async with ctx.typing():
            if member is None:
                await self.show_guild_stats(ctx)
            else:
                await self.show_member_stats(ctx, member)

    @stats.command(name='global')
    @commands.is_owner()
    async def stats_global(self, ctx):
        """Global all time command statistics."""

        query = "SELECT COUNT(*) FROM commands;"
        total = await ctx.fetchrow(query)

        e = discord.Embed(title='Command Stats', colour=discord.Colour.blurple())
        e.description = f'{total[0]} commands used.'

        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}'
        )

        query = """SELECT command, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
        e.add_field(name='Top Commands', value=value, inline=False)

        query = """SELECT guild_id, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY guild_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = []
        for (index, (guild_id, uses)) in enumerate(records):
            if guild_id is None:
                guild = 'Private Message'
            else:
                guild = self.censor_object(self.bot.get_guild(guild_id) or f'<Unknown {guild_id}>')

            emoji = lookup[index]
            value.append(f'{emoji}: {guild} ({uses} uses)')

        e.add_field(name='Top Guilds', value='\n'.join(value), inline=False)

        query = """SELECT author_id, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = []
        for (index, (author_id, uses)) in enumerate(records):
            user = self.censor_object(self.bot.get_user(author_id) or f'<Unknown {author_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {user} ({uses} uses)')

        e.add_field(name='Top Users', value='\n'.join(value), inline=False)
        await ctx.send(embed=e)

    @stats.command(name='today')
    @commands.is_owner()
    async def stats_today(self, ctx):
        """Global command statistics for the day."""

        query = "SELECT failed, COUNT(*) FROM commands WHERE used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day') GROUP BY failed;"
        total = await ctx.fetch(query)
        failed = 0
        success = 0
        question = 0
        for state, count in total:
            if state is False:
                success += count
            elif state is True:
                failed += count
            else:
                question += count

        e = discord.Embed(title='Last 24 Hour Command Stats', colour=discord.Colour.blurple())
        e.description = f'{failed + success + question} commands used_at today. ' \
                        f'({success} succeeded, {failed} failed, {question} unknown)'

        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}'
        )

        query = """SELECT command, COUNT(*) AS "uses"
                   FROM commands
                   WHERE used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
        e.add_field(name='Top Commands', value=value, inline=False)

        query = """SELECT guild_id, COUNT(*) AS "uses"
                   FROM commands
                   WHERE used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY guild_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = []
        for (index, (guild_id, uses)) in enumerate(records):
            if guild_id is None:
                guild = 'Private Message'
            else:
                guild = self.censor_object(self.bot.get_guild(guild_id) or f'<Unknown {guild_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {guild} ({uses} uses)')

        e.add_field(name='Top Guilds', value='\n'.join(value), inline=False)

        query = """SELECT author_id, COUNT(*) AS "uses"
                   FROM commands
                   WHERE used_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await ctx.fetch(query)
        value = []
        for (index, (author_id, uses)) in enumerate(records):
            user = self.censor_object(self.bot.get_user(author_id) or f'<Unknown {author_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {user} ({uses} uses)')

        e.add_field(name='Top Users', value='\n'.join(value), inline=False)
        await ctx.send(embed=e)

    async def get_invite_info(self, server, user):
        invite = await self.invites.track_user(server, user)

        if not invite:
            invite = "Not found."
        else:
            code = invite[1]
            inviter = await self.bot.fetch_user(invite[2])
            if not inviter:
                inviter = "Unknown"
            else:
                inviter = f"**{inviter}** (ID: {inviter.id})"
            invite = f"`{code}` {inviter}"
        return invite

    async def get_cases(self, server, user, case_type):

        if case_type.lower() == "all":
            return len(await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2", server.id, user.id))
        else:
            return len(await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND action=$3", server.id, user.id, case_type.capitalize()))

    async def get_status(self, server, user):
        user_stats = await self.bot.db.fetchrow("SELECT * FROM user_stats WHERE user_id=$1", user.id)

        if user_stats:
            
            online_total_seconds = 0
            for log in user_stats['online']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    online_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                online_total_seconds += log['ending_time'] - log['starting_time']
            online_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+online_total_seconds), brief=True, suffix=False) if online_total_seconds > 1 else "0s"
            
            offline_total_seconds = 0
            for log in user_stats['offline']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    offline_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                offline_total_seconds += log['ending_time'] - log['starting_time']
            offline_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+offline_total_seconds), brief=True, suffix=False) if offline_total_seconds > 1 else "0s"

            dnd_total_seconds = 0
            for log in user_stats['dnd']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    dnd_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                dnd_total_seconds += log['ending_time'] - log['starting_time']
            dnd_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+dnd_total_seconds), brief=True, suffix=False) if dnd_total_seconds > 1 else "0s"

            idle_total_seconds = 0
            for log in user_stats['idle']:
                log = json.loads(log)
                if log['ending_time'] == 0:
                    idle_total_seconds += round(datetime.datetime.utcnow().timestamp()) - log['starting_time']
                    continue
                
                idle_total_seconds += log['ending_time'] - log['starting_time']
            idle_time = time.human_timedelta(datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+idle_total_seconds), brief=True, suffix=False) if idle_total_seconds > 1 else "0s"

            total = online_total_seconds+offline_total_seconds+dnd_total_seconds+idle_total_seconds
            online_percent = round(100 * online_total_seconds/total) if user_stats['online'] else 0
            offline_percent = round(100 * offline_total_seconds/total) if user_stats['offline'] else 0
            dnd_percent = round(100 * dnd_total_seconds/total) if user_stats['dnd'] else 0
            idle_percent = round(100 * idle_total_seconds/total) if user_stats['idle'] else 0
            return "\n".join([
            f":stopwatch: Has been **{user_stats['current_status']}** for `{time.human_timedelta(user_stats['current_status_since'], brief=True, suffix=False)}`.",
            f"<:online:752328954076987502> Online **{online_percent}%** for `{online_time}` in total.",
            f"<:offline:752328954039500950> Offline **{offline_percent}%** for `{offline_time}` in total.",
            f"<:idle:752328953817071637> Idle **{idle_percent}%** for `{idle_time}` in total.",
            f"<:dnd:752328954085507172> DND **{dnd_percent}%** for `{dnd_time}` in total."])
        else:
            return "No user stats have been logged."

    @command(name="serverinfo", aliaes=['si'], brief="View this guild's information.")
    async def serverinfo(self, ctx: Context):
        """View this guild's information."""

        server = ctx.guild

        messages = len(await ctx.fetch("SELECT * FROM messages WHERE guild_id=$1", server.id))
        today_messages = len(await ctx.fetch("SELECT * FROM messages WHERE guild_id=$1 AND created_at > (CURRENT_TIMESTAMP - INTERVAL '1 day')", server.id))
        
        delta = datetime.datetime.utcnow() - server.created_at
        week = delta.total_seconds() / 604800
        weekly_joins = len([member for member in server.members if datetime.datetime.utcnow()-member.joined_at<datetime.timedelta(weeks=1)])
        weekly_joins_average = round(len(server.members)/week)

        member_count = ctx.guild.member_count
        members = ctx.guild.members
        online = 0
        dnd = 0
        idle = 0
        offline = 0
        for member in members:
            if str(member.status) == "online":
                online += 1
            elif str(member.status) == "offline":
                offline += 1
            elif str(member.status) == "idle":
                idle += 1
            elif str(member.status) == "dnd":
                dnd += 1

        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = "\n".join([
            f"**Server information**",
            f"Created: {time.human_timedelta(server.created_at)}",
            f"Owner: {server.owner.mention} {server.owner}",
            "",
            f"**Role information**",
            f"Total roles: {len(server.roles)}",
            f"Top role: {server.roles[-1].mention}",
            "",
            f"**Channel information**",
            f"Total: {len(server.channels):,}",
            f"Text Channels: {len(server.text_channels):,}",
            f"Voice Channels: {len(server.voice_channels):,}",
            f"Categories: {len(server.categories):,}",
            "",
            f"**Member counts**",
            f"Total members: {member_count:,}",
            f"Weekly joins: {weekly_joins} ({weekly_joins_average} on average)",
            f"Messages: {messages:,} ({today_messages:,} sent today)",
            "",
            f"**Member statuses**",
            f"<:online:752328954076987502> Online: {online:,} ({round(100 * online/member_count)}%)",
            f"<:offline:752328954039500950> Offline: {offline:,} ({round(100 * offline/member_count)}%)",
            f"<:dnd:752328954085507172> Do not disturb: {dnd:,} ({round(100 * dnd/member_count)}%)",
            f"<:idle:752328953817071637> Idle: {idle:,} ({round(100 * idle/member_count)}%)"
        ])
        embed.set_thumbnail(url=server.icon_url)
        await ctx.send(embed=embed)

    @command(name="whois", aliases=['userinfo', 'who-is', 'user-info', 'ui', 'wi'], usage="[member:snowflake]", brief="View a member's information.")
    async def whois(self, ctx: Context, user: discord.Member = None):
        """View a member's information."""

        user = user or ctx.author
        server = ctx.guild

        messages = len(await ctx.fetch("SELECT * FROM messages WHERE guild_id=$1 AND author_id=$2", server.id, user.id))
        today_messages = len(await ctx.fetch("SELECT * FROM messages WHERE guild_id=$1 AND created_at > (CURRENT_TIMESTAMP - INTERVAL '1 day') AND author_id=$2", server.id, user.id))

        badges = []

        for badge, is_set in user.public_flags:
            if is_set and f"badge_{badge}" in self.bot.config['Emojis']:
                badges.append(self.bot.config['Emojis'][f"badge_{badge}"])

        all_cases = await self.get_cases(server, user, 'all')
        warns = await self.get_cases(server, user, 'warn')
        mutes = await self.get_cases(server, user, 'mute')
        invite_info = await self.get_invite_info(server, user)

        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_thumbnail(url=user.avatar_url)
        embed.description = "\n".join([
            f"**User information** {''.join(badges)}",
            f"Created: {time.human_timedelta(user.created_at)}",
            f"Joined: {time.human_timedelta(user.joined_at)}",
            f"ID: {user.id}",
            f"Display name: {user.display_name}",
            "",
            f"**Role information**",
            f"Total roles: {len(user.roles):,}",
            f"Highest role: {user.top_role.mention}",
            "",
            f"**Status information**",
            await self.get_status(server, user),
            f"Messages: {messages:,} ({today_messages:,} sent today)",
            "",
            f"**Moderation history**",
            f"Total cases: {all_cases:,}",
            f"Warnings: {warns:,}",
            f"Mutes: {mutes:,}",
            "",
            f"**Invite history**",
            invite_info
        ])
        await ctx.send(embed=embed)

    @command()
    async def reps(self, ctx, *, role: str):
        server = ctx.guild
        role = arg.get_role(ctx, role)
        if not role:
            return await ctx.send(f"{self.bot.x} I could not find that role")
        rep = discord.utils.get(ctx.guild.roles, name="Clan Representative")
        users = ""
        reps = 0
        for user in role.members:
            if rep in user.roles:
                reps += 1
                users += f"{user.mention}\n"
        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = f"**__There are {reps} reps currently in the {role} clan!__**\n\n{users}"
        await ctx.send(embed=embed)

    @command()
    async def members(self, ctx, *, role: str):
        server = ctx.guild 
        role = arg.get_role(ctx, role)
        if not role:
            return await ctx.send(f"{self.bot.x} I could not find that role.")
        mem = discord.utils.get(ctx.guild.roles, name=f"Clan Members")
        users = "" 
        mems = 0 
        for user in role.members:
            if mem in user.roles:
                mems += 1 
                users += f"{user.mention}\n"
        embed = discord.Embed(color=discord.Color.blurple())
        embed.description = f"**__There are {mems} members currently in the {role} clan!__**\n\n{users}"
        await ctx.send(embed=embed)

    @command()
    async def test(self, ctx):

        users = await ctx.fetch("SELECT * FROM user_stats")
        online_perc = []

        for user in users:
          
          online_total_seconds = 0
          offline_total_seconds = 0
          idle_total_seconds = 0
          dnd_total_seconds = 0

          for log in user['online']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              online_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            online_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['offline']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              offline_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            offline_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              idle_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            idle_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              dnd_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            dnd_total_seconds += log['ending_time'] - log['starting_time']

          total_seconds = online_total_seconds+offline_total_seconds+dnd_total_seconds+idle_total_seconds
          if total_seconds == 0:
            continue
          online_perc.append(online_total_seconds/total_seconds*100)

        await ctx.send(f"The average percent that someone is online in this server is: {round(sum(online_perc)/len(online_perc))}%")

    async def find_online_perc(self, users):
        online_perc = []

        for user in users:
          
          online_total_seconds = 0
          offline_total_seconds = 0
          idle_total_seconds = 0
          dnd_total_seconds = 0

          for log in user['online']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              online_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            online_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['offline']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              offline_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            offline_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              idle_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            idle_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              dnd_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            dnd_total_seconds += log['ending_time'] - log['starting_time']

          total_seconds = online_total_seconds+offline_total_seconds+dnd_total_seconds+idle_total_seconds
          if total_seconds == 0:
            continue
          online_perc.append(online_total_seconds/total_seconds*100)
        return round(sum(online_perc)/len(online_perc))

    async def find_offline_perc(self, users):
        offline_perc = []

        for user in users:
          
          online_total_seconds = 0
          offline_total_seconds = 0
          idle_total_seconds = 0
          dnd_total_seconds = 0

          for log in user['online']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              online_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            online_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['offline']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              offline_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            offline_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              idle_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            idle_total_seconds += log['ending_time'] - log['starting_time']

          for log in user['idle']:
            log = json.loads(log)
            if log['ending_time'] == 0:
              dnd_total_seconds += round(datetime.datetime.utcnow().timestamp()-log['starting_time'])
              continue
            dnd_total_seconds += log['ending_time'] - log['starting_time']

          total_seconds = online_total_seconds+offline_total_seconds+dnd_total_seconds+idle_total_seconds
          if total_seconds == 0:
            continue
          offline_perc.append(offline_total_seconds/total_seconds*100)

        return round(sum(offline_perc)/len(offline_perc))

    @command()
    async def server_stats(self, ctx):
        server = ctx.guild
        users = await ctx.fetch("SELECT * FROM user_stats")

        online_perc = await self.find_online_perc(users)
        offline_perc = await self.find_offline_perc(users)
        total_commands = len(await ctx.fetch("SELECT * FROM commands WHERE guild_id=$1", server.id))

        embed = discord.Embed()
        embed.description = "\n".join([
            f"**Average Online %:** {online_perc}%",
            f"**Average Offline %:** {offline_perc}%",
            f"**Commands Used:** {total_commands:,}"
        ])
        await ctx.send(embed=embed)

    @Cog.listener()
    async def on_member_join(self, member):

        if member.guild.id != 416051383691771916:
            return

        try:
            await member.send(f"https://sentiguard.herokuapp.com/verification/{member.guild.id} **to enter the server!**")
        except:
            pass

    @command(name="accounts", aliases=['acc'])
    @has_guild_permissions(manage_messages=True)
    async def accounts(self, ctx, discord_user: DiscordUser):

        data = None

        async with aiohttp.ClientSession().get(f"https://sentiguard.herokuapp.com/api/v1/linked_users/{discord_user.id}", headers=headers) as resp:
            data = json.loads(await resp.text())

        

def setup(bot):

    if not hasattr(bot, 'socket_stats'):
        bot.socket_stats = Counter()

    bot.add_cog(Stats(bot))