import datetime
import json
from io import BytesIO
import re
from collections import Counter
from math import ceil

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command, has_guild_permissions, Context, BadArgument
from durations_nlp import Duration
from fuzzywuzzy import fuzz

from .utils.converters import DiscordUser, BannedMember
from .utils import time
from config import *

class Moderation(Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def modlog(self):
        return self.bot.get_cog("Modlog")
    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")
    @property
    def invites(self):
        return self.bot.get_cog("InviteTracking")

    @command(name="kick", aliases=['k'], usage="<user:snowflake> [reason:text]", brief="Kick a member from the guild.")
    @has_guild_permissions(kick_members=True)
    async def kick(self, ctx: Context, member: discord.Member, *, reason=None):
        """Kick a member from the guild."""

        server = ctx.guild
        if member == ctx.author:
            return await ctx.send(f"{self.bot.x} **You are not allowed to kick yourself.**")
        elif member == self.bot.user:
            return await ctx.send(f"{self.bot.x} **I am unable to kick myself.**")
        elif member.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
            return await ctx.send(f"{self.bot.x} **{member} is higher or equal to your role position.**")
        else:
            try:
                await member.kick(reason=f"{ctx.author} - {reason}")
            except discord.Forbidden:
                return await ctx.send(f"{self.bot.x} **I am missing permissions to kick {member}.**")
            except discord.HTTPException:
                return await ctx.send(f"{self.bot.x} **Something went wrong, try again later.**")
            
            case = await self.modlog.create_case(server, member, ctx.author, "Kick", reason)
            await ctx.send(
                f":white_check_mark: `Case #{case:,}` {member.mention} **has been kicked from the guild.**"
            )

    @command(name="ban", aliases=['b'], usage="<user:snowflake> [reason:text]", brief="Ban a user from the guild.")
    @has_guild_permissions(ban_members=True)
    async def ban(self, ctx: Context, user: DiscordUser, *, reason=None):
        """Ban a user from the guild."""

        server = ctx.guild
        if not user in server.members:
            pass
        else:
            if user == ctx.author:
                return await ctx.send(f"{self.bot.x} **You are not allowed to ban yourself.**")
            elif user == self.bot.user:
                return await ctx.send(f"{self.bot.x} **I am unable to ban myself.**")
            elif user.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
                return await ctx.send(f"{self.bot.x} **{user} is higher or equal to your role position.**")
        try:
            await server.ban(user, reason=f"{ctx.author} - {reason}")
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to ban {user}.**")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something went wrong, try again later.**")
        
        case = await self.modlog.create_case(server, user, ctx.author, "Ban", reason)
        await ctx.send(
            f":white_check_mark: `Case #{case:,}` {user.mention} **has been banned indefinitely from the guild.**"
        )

    @command(name="softban", aliases=['sb', 'soft-ban'], usage="<user:snowflake> [reason:text]", brief="Soft- a user from the guild.")
    @has_guild_permissions(ban_members=True)
    async def softban(self, ctx: Context, user: DiscordUser, *, reason=None):
        """Soft-ban a user from the guild.
        
        This basically just deletes their recent messages.
        Bans them and then unbans them immediately after."""

        server = ctx.guild
        if not user in server.members:
            pass
        else:
            if user == ctx.author:
                return await ctx.send(f"{self.bot.x} **You are not allowed to soft-ban yourself.**")
            elif user == self.bot.user:
                return await ctx.send(f"{self.bot.x} **I am unable to soft-ban myself.**")
            elif user.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
                return await ctx.send(f"{self.bot.x} **{user} is higher or equal to your role position.**")
        try:
            await server.ban(user, reason=f"{ctx.author} - {reason}")
            await server.unban(user, reason=f"Automatic unban from a previous softban executed by {ctx.author}.")
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to soft-ban {user}.**")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something went wrong, try again later.**")
        
        case = await self.modlog.create_case(server, user, ctx.author, "Softban", reason)
        await ctx.send(
            f":white_check_mark: `Case #{case:,}` {user.mention} **has been soft-banned from the guild.**"
        )

    @command(name="tempban", aliases=['tb', 'temp-ban'], usage="<user:snowflake> <duration:time> [reason:text]", brief="Ban a user from the guild for a certain amount of time.")
    @has_guild_permissions(ban_members=True)
    async def tempban(self, ctx: Context, user: DiscordUser, duration: str = "No reason provided.", *, reason = " "):
        """Ban a user from the guild for a certain amount of time.

        You can ban a user from the guild even if they aren't in the guild."""

        try:
            seconds = Duration(duration).to_seconds()
        except:
            seconds = "forever"
        
        if seconds == "forever" or seconds == 0:
            return await ctx.send(f"{self.bot.x} **You must specify a duration to temp-ban that user for.**")
        
        server = ctx.guild

        if not user in server.members:
            pass
        else:
            if user == ctx.author:
                return await ctx.send(f"{self.bot.x} **You are not allowed to temp-ban yourself.**")
            elif user == self.bot.user:
                return await ctx.send(f"{self.bot.x} **I am unable to temp-ban myself.**")
            elif user.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
                return await ctx.send(f"{self.bot.x} **{user} is higher or equal to your role position.**")
            
        try:
            await server.ban(user, reason=f"{ctx.author} ({duration}) - {reason}")
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to temp-ban {user}.**")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something went wrong, try again later.**")
        
        until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
        until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
        time_str = time.human_timedelta(until_dt_obj)

        case = await self.modlog.create_case(server, user, ctx.author, "Tempban", reason, time_str)
        await ctx.send(
            f":white_check_mark: `Case #{case:,}` {user.mention} **has been temp-banned from the guild for {time_str}**."
        )
        await self.reminders.create_timer(until_dt_obj, 'tempban', ctx.guild.id, ctx.author.id, user.id, case, created=ctx.message.created_at)

    @command(name="mute", aliases=['m'], usage="<user:snowflake> [duration:time] [reason:text]", brief="Mute a guild member, this will make them not able to speak.")
    @has_guild_permissions(manage_messages=True)
    async def mute(self, ctx: Context, user: discord.Member, duration: str = "No reason provided.", *, reason = " "):
        """Mute a guild member, this will make them not able to speak."""
        server = ctx.guild
        muted_role = server.get_role(mutedrole[server.id])

        try:
            seconds = Duration(duration).to_seconds()
        except:
            seconds = "forever"

        if seconds == "forever" or seconds == 0:
            reason = f"{duration} {reason}"
            duration = "forever"

        if user == ctx.author:
            return await ctx.send(f"{self.bot.x} **You are not allowed to mute yourself.**")
        elif user == self.bot.user:
            return await ctx.send(f"{self.bot.x} **I am unable to mute myself.**")
        elif user.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
            return await ctx.send(f"{self.bot.x} **{user} is higher or equal to your role position.**")
        else:
            pass
    
        try:
            await user.send(f":no_mouth: You have been muted in the guild, **{server}**, for **{duration}**, with the reason: {reason}")
        except:
            pass
        try:
            await user.add_roles(muted_role, reason=f"{ctx.author} - {reason}")
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to mute {user}.**")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something went wrong, try again later.**")
        
        if duration == "forever":
            query = """SELECT *
                FROM reminders
                WHERE extra #>> '{args,2}' = $2
                AND extra #>> '{args,0}' = $1
                AND event='tempmute'
                ORDER BY expires
                LIMIT 10;
            """
            records = await ctx.fetch(query, str(server.id), str(user.id))
            if records:
                confirmation = await ctx.prompt(f"{self.bot.x} **This user is currently registered in a mute timer. Would you like me to remove this timer?**")
                if confirmation:
                    # remove all of the user reminders
                    for reminder in records:
                        await ctx.execute("DELETE FROM reminders WHERE id=$1", reminder['id'])

                    # pylint: disable=unused-variable
                    await self.modlog.create_case(server, user, ctx.author, "Mute", reason, "Indefinitely")
                    await ctx.send(f"{self.bot.check} Applied an indefinite mute to **{user}**.")
                else:
                    await ctx.send(f"{self.bot.check} Indefinite mute for **{user}** has been aborted.")
            else:
                case = await self.modlog.create_case(server, user, ctx.author, "Mute", reason, "Indefinitely")
                await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **has been muted indefinitely.**")
        else:
            try:
                query = """SELECT *
                    FROM reminders
                    WHERE extra #>> '{args,2}' = $2
                    AND extra #>> '{args,0}' = $1
                    AND event='tempmute'
                    ORDER BY expires
                    LIMIT 10;
                """
                records = await ctx.fetch(query, str(server.id), str(user.id))
                if records:
                    old_unmute_dt = records[0]['expires']
                    old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                    new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds+old_seconds)
                    
                    confirmation = await ctx.prompt(f"{self.bot.x} **This user seems to be already tempmuted, do you want to extend their mute time to add {duration} to their mute time?**")
                    if confirmation:
                        await ctx.execute("""
                        UPDATE reminders SET expires=$1
                        WHERE event = 'tempmute'
                        AND extra #>> '{args,0}' = $2
                        AND extra #>> '{args,2}' = $3
                        """, new_unmute_dt, str(server.id), str(user.id))
                        await ctx.send(f"{self.bot.check} Updated the mute time for **{user}** to **{time.human_timedelta(new_unmute_dt)}**.")
                        self.bot.dispatch("timer_edit", server)
                        return
                    else:
                        await ctx.send(f"{self.bot.check} Tempmute for **{user}** has been aborted.")
                        return

                until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
                until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
                time_str = time.human_timedelta(until_dt_obj)

                case = await self.modlog.create_case(server, user, ctx.author, "Mute", reason, time_str) # pylint: disable=unused-variable
                await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **has been temp-muted for {time_str}.**")

                await self.reminders.create_timer(until_dt_obj, 'tempmute', ctx.guild.id, ctx.author.id, user.id, case, created=ctx.message.created_at)
            except Exception as e:
                await ctx.send(e)

    @mute.error
    async def mute_error(self, ctx, error):
        if isinstance(error, BadArgument):
            cmd = f"<forcemute <user_id> [duration] [reason]"
            
            await ctx.send(f"{self.bot.x} That user isn't in the server, however you can mute them by doing: `{cmd.strip()}`")

    @command(name="forcemute", aliases=['fm', 'force-mute'], usage="<user_id> [duration] [reason]", brief="This will automatically mute the user when they join the server.")
    @has_guild_permissions(manage_messages=True)
    async def forcemute(self, ctx: Context, user: DiscordUser, duration: str = "No reason provided.", *, reason = ""):
        """This will automatically mute the user when they join the server.

        When you forcemute someone it will automatically mute them
        when they enter the server again or if they enter the server
        for the first time."""
        
        server = ctx.guild

        try:
            seconds = Duration(duration).to_seconds()
        except:
            seconds = "forever"

        if seconds == "forever" or seconds == 0:
            reason = f"{duration} {reason}"
            duration = "forever"
        
        in_server = [member for member in server.members if user.id == member.id]
        if user is None or in_server:
            return await ctx.send(f"{self.bot.x} **Forcemute only applies to users who are not in the server.**")

        if duration == "forever":
            await ctx.execute("""
            INSERT INTO force_mutes (
                guild_id,
                user_id,
                moderator_id,
                duration,
                reason
            ) VALUES (
                $1, $2, $3, $4, $5
            )
            """, server.id, user.id, ctx.author.id, json.dumps({"msg": "Indefinitely.", "seconds": None, "prefix": None}), reason)
            # pylint: disable=unused-variable
            case = await self.modlog.create_case(server, user, ctx.author, "Force-mute", reason, {"msg": "Indefinitely.", "seconds": None, "prefix": None})
            await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **will be muted indefinitely if they join the guild.**")
        else:
            await ctx.execute("""
            INSERT INTO force_mutes (
                guild_id,
                user_id,
                moderator_id,
                duration,
                reason
            ) VALUES (
                $1, $2, $3, $4, $5
            )
            """, server.id, user.id, ctx.author.id, json.dumps({"msg": duration, "seconds": seconds, "prefix": duration}), reason)
            # pylint: disable=unused-variable
            case = await self.modlog.create_case(server, user, ctx.author, "Force-mute", reason, {"msg": duration, "seconds": seconds, "prefix": duration})
            await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **will be muted for {duration} if they join the guild.**")

    @command(name="unmute", aliases=['um'], usage="<user> [reason]", brief="Unmute a user.")
    @has_guild_permissions(manage_messages=True)
    async def unmute(self, ctx: Context, user: discord.Member, *, reason: str = None):
        """Unmute a user."""

        server = ctx.guild
        muted_role = server.get_role(mutedrole[server.id])
        
        if user == self.bot.user:
            return await ctx.send(f"{self.bot.x} I'm not muted, sorry.")
        
        try:
            await user.remove_roles(muted_role, reason=f"{ctx.author} - {reason}")
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to unmute {user}**.")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something happened, try again?**")

        case = await self.modlog.create_case(server, user, ctx.author, "Unmute", reason)
        await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **has been unmuted.**")
        query = """SELECT *
            FROM reminders
            WHERE extra #>> '{args,2}' = $2
            AND extra #>> '{args,0}' = $1
            AND event='tempmute'
            ORDER BY expires
            LIMIT 10;
        """
        records = await ctx.fetch(query, str(server.id), str(user.id))

        for record in records:
            await ctx.execute("DELETE FROM reminders WHERE id=$1", record['id'])

    @command(name="unban", aliases=['ub'], usage="<user> [reason]", brief="Unban a user.")
    @has_guild_permissions(ban_members=True)
    async def unban(self, ctx: Context, user: BannedMember, *, reason: str = None):
        """Unban a user from the server.

        The user argument must be an ID or Name#Discrim
        of the user.
        """

        try:
            await ctx.guild.unban(user.user, reason=reason)
        except discord.Forbidden:
            return await ctx.send(f"{self.bot.x} **I am missing permissions to unban {user}**.")
        except discord.HTTPException:
            return await ctx.send(f"{self.bot.x} **Something happened, try again?**")

        case = await self.modlog.create_case(ctx.guild, ctx.author, user.user, "Unban", reason)
        await ctx.send(f":white_check_mark: `Case #{case:,}` {user.mention} **has been unbanned from the guild ban list.**")

    @command(name="warn", aliases=['w', 'strike'], usage="<user> [reason]", brief="Warn a user.")
    @has_guild_permissions(manage_messages=True)
    async def warn(self, ctx: Context, user: discord.Member, *, reason: str = None):
        """Warn a user."""

        server = ctx.guild

        if user == ctx.author:
            return await ctx.send(f"{self.bot.x} **You are unable to warn yourself.**")
        
        if user == self.bot.user:
            return await ctx.send(f"{self.bot.x} **I am unable to warn myself.**")

        if user.top_role.position >= ctx.author.top_role.position and ctx.author != server.owner:
            return await ctx.send(f"{self.bot.x} **{user} is higher than or equal to your role position.**")

        await self.modlog.warn(server, user, ctx.channel, ctx.author, reason)
        print("test")
        if server.id == 416051383691771916 and "bypass" in reason and not "--ignore" in reason:
            
            def check(m):
                return m.author.id == user.id and m.channel.id == ctx.channel.id
            userHistory = await ctx.channel.history(limit=15).filter(check).flatten()
            censoredWords = await ctx.fetch("SELECT * FROM censors")
            censoredWords = [censor['word'] for censor in censoredWords]
            similarWords = []
            for msg in userHistory:
                for censoredWord in censoredWords:
                    for word in msg.content.split():
                        word = word.lower()

                        data = fuzz.ratio(word, censoredWord)

                        if data < 60:
                            continue
                        
                        similarWords.append(f"**Similar Word:** {word}\n**Close Word:** {censoredWord}\n**Chance:** {data}%")
            
            if len(similarWords) == 0:
                return

            await ctx.author.send(f":warning: I have found **{len(similarWords)}** possible bypasses from {user.mention}'s recent warns.")
            for similarWord in similarWords:
                msg = await ctx.author.send(similarWord)
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")

    @command(name="removewarn", aliases=['rw', 'remove-warn'], usage="<case_id:int>", brief="Remove a warn from a user's warnings.")
    @has_guild_permissions(manage_messages=True)
    async def removewarn(self, ctx: Context, case_id = None):
        """Remove a warn from a user's warnings.

        You can see the case id by looking at the warning message
        or looking through the user's warnings.
        """
        
        server = ctx.guild

        case_id = int(case_id.replace(",", "").replace("#", ""))
        found_case = await ctx.fetchrow("SELECT * FROM cases WHERE guild_id=$1 AND case_id=$2", server.id, case_id)

        if not found_case:
            return await ctx.send(f"{self.bot.x} **I could not find a case with the ID of `{case_id:,}`.**")
        
        if found_case['type'] != 1:
            return await ctx.send(f"{self.bot.x} **The specified case ID isn't attached to a warning.**")
        
        await ctx.execute("DELETE FROM cases WHERE guild_id=$1 AND case_id=$2", server.id, case_id)
        
        case_user = await self.bot.fetch_user(found_case['user_id'])
        await ctx.send(f"{self.bot.check} Successfully removed the warning, `#{case_id:,}`, from **{case_user}**.")

    @command(name="clearwarns", aliases=['cw'], usage="<user>", brief="Remove all the warnings from a user.")
    @has_guild_permissions(manage_messages=True)
    async def clearwarns(self, ctx: Context, user: DiscordUser):
        """Remove all the warnings from a user."""

        server = ctx.guild

        found_warns = await ctx.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND type=$3", server.id, user.id, 1)

        if not found_warns:
            return await ctx.send(f"{self.bot.x} **There were no warnings found for this user.**")
        
        confirmation = await ctx.prompt(f":octagonal_sign: **Are you sure you want to remove {len(found_warns)} warnings from {user}?**")
        if not confirmation:
            return await ctx.send(f"{self.bot.check} Aborted.")

        await ctx.execute("DELETE FROM cases WHERE guild_id=$1 AND user_id=$2 AND type=$3", server.id, user.id, 1)

        await ctx.send(f"{self.bot.check} Successfully removed **{len(found_warns)}** warnings from **{user}**.")

    @command(name="pardon", usage="<case_id>", brief="Remove/pardon a case from a user or server.")
    @has_guild_permissions(manage_messages=True)
    async def pardon(self, ctx: Context, case_id: str):
        """Remove/pardon a case from a user or server.

        This can be any type of case."""

        server = ctx.guild

        case_id = int(case_id.replace(",", "").replace("#", ""))
        found_case = await ctx.fetchrow("SELECT * FROM cases WHERE guild_id=$1 AND case_id=$2", server.id, case_id)

        if not found_case:
            return await ctx.send(f"{self.bot.x} **There was no matching case with that case ID.**")
        
        await ctx.execute("DELETE FROM cases WHERE guild_id=$1 AND case_id=$2", server.id, case_id)
        
        user = await self.bot.fetch_user(found_case['user_id'])
        await ctx.send(f"{self.bot.check} Successfully pardoned that case, the case type was a `{found_case['action'].lower()}` and belonged to **{user}**.")

    @command(name="check", aliases=['mi', 'muteinformation', 'mute-information', 'muteinfo', 'mute-info'], brief="See why someone is muted.")
    @has_guild_permissions(manage_messages=True)
    async def check(self, ctx: Context, user: discord.Member):
        """See why someone is muted."""
        server = ctx.guild

        if user._roles.has(self.bot.config['mutedrole']):
            latest_case = await ctx.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND type=2", server.id, user.id)
            if not latest_case:
                return await ctx.send(f"{self.bot.x} **I could not find any mute records for this user.**")
            case = latest_case[-1] if len(latest_case) > 1 else latest_case[0]
            reason = case['reason']
            # case_on = case['created_at'].strftime("%A, %B, %d, %I:%M %p")
            moderator = await self.bot.fetch_user(case['moderator_id'])
            duration = f"for **{case['duration']}**"

            await ctx.send(
                f"{self.bot.check} **{user}** was muted by **{moderator}** {duration}, with the reason of: {reason}"
            )

    @command(name="warnings", aliases=['warns'], usage="<user:snowlfake>", brief="View the history of a user's warnings.")
    @has_guild_permissions(manage_messages=True)
    async def warnings(self, ctx: Context, user: discord.Member):
        """View the history of a user's warnings."""

        server = ctx.guild

        warnings = await ctx.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND action='Warn' ORDER BY case_id DESC;", server.id, user.id)
        if not warnings:
            return await ctx.send(f"{self.bot.x} I could not find any warnings for this member.")
        
        pages = ceil(len(warnings)/6)
        embed = await self.case_embed(server, user, warnings[:6], "Warnings")
        embed.description = f"This member has {len(warnings)} warning(s)."
        embed.set_footer(text=f"Page (1/{pages})")
        message = await ctx.send(embed=embed)
        if len(warnings) > 6:
            await message.add_reaction("◀")
            await message.add_reaction("❌")
            await message.add_reaction("▶")
        def reactioncheck(reaction, user):
            if user == ctx.author:
                if reaction.message.id == message.id:
                    if reaction.emoji == "▶" or reaction.emoji == "❌" or reaction.emoji == "◀" or reaction.emoji == "🇮":
                        return True
        x = 0
        while True:
            reaction, user2 = await self.bot.wait_for("reaction_add", check=reactioncheck)
            if reaction.emoji == "◀":
                x -= 6
                if x < 0:
                    x = 0
                await message.remove_reaction("◀", user2)
            elif reaction.emoji == "❌":
                await message.delete()
            elif reaction.emoji == "▶":
                x += 8
                if x > len(warnings):
                    x = len(warnings) - 6
            embed = await self.case_embed(server, user, warnings[x:x+6], "Warnings")
            embed.description = f"This member has {len(warnings)} warning(s)."
            embed.set_footer(text=f'Page ({x//6+1}/{pages})')
            await message.edit(embed=embed)
            await message.remove_reaction("▶", user2)

    @command(name="modlog", aliases=['mod-log'], usage="<user:snowlfake>", brief="View the moderation history of a member.")
    @has_guild_permissions(manage_messages=True)
    async def modlog_(self, ctx: Context, user: discord.Member):
        """View the moderation history of a member."""

        server = ctx.guild

        cases = await ctx.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 ORDER BY case_id DESC;", server.id, user.id)
        if not cases:
            return await ctx.send(f"{self.bot.x} I could not find any past moderation cases for this member.")
        
        pages = ceil(len(cases)/6)
        embed = await self.case_embed(server, user, cases[:6], "Modlog")
        embed.description = f"This member has {len(cases)} case(s)."
        embed.set_footer(text=f"Page (1/{pages})")
        message = await ctx.send(embed=embed)
        if len(cases) > 6:
            await message.add_reaction("◀")
            await message.add_reaction("❌")
            await message.add_reaction("▶")
        def reactioncheck(reaction, user):
            if user == ctx.author:
                if reaction.message.id == message.id:
                    if reaction.emoji == "▶" or reaction.emoji == "❌" or reaction.emoji == "◀" or reaction.emoji == "🇮":
                        return True
        x = 0
        while True:
            reaction, user2 = await self.bot.wait_for("reaction_add", check=reactioncheck)
            if reaction.emoji == "◀":
                x -= 6
                if x < 0:
                    x = 0
                await message.remove_reaction("◀", user2)
            elif reaction.emoji == "❌":
                await message.delete()
            elif reaction.emoji == "▶":
                x += 8
                if x > len(cases):
                    x = len(cases) - 6
            embed = await self.case_embed(server, user, cases[x:x+6], "Modlog")
            embed.description = f"This member has {len(cases)} case(s)."
            embed.set_footer(text=f'Page ({x//6+1}/{pages})')
            await message.edit(embed=embed)
            await message.remove_reaction("▶", user2)

    @command(name="unlock", aliases=['unlockdown', 'un-lock-down'], usage="<channel:snowflake>", brief="Unlock a previous locked channel.")
    @has_guild_permissions(manage_messages=True)
    async def unlockdown(self, ctx: Context, channel: discord.TextChannel = None):
        """Unlock a previous locked channel."""

        server = ctx.guild
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(server.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(server.default_role, overwrite=overwrite)
        await ctx.send(f"{self.bot.check} Unlocked {channel.mention}.")


    @command(name="lock", aliases=['lock-down', 'lockdown'], usage="<channel:snowflake> [duration:text]", brief="Lockdown a channel for a certain amount of time.")
    @has_guild_permissions(manage_messages=True)
    async def lockdown(self, ctx: Context, channel: discord.TextChannel = None, duration: str = "No reason provided.", *, reason = ""):
        """Lockdown a channel for a certain amount of time."""
        server = ctx.guild
        try:
            seconds = Duration(duration).to_seconds()
        except:
            seconds = "forever"

        if seconds == 0 or seconds == "forever":
            reason = f'{duration} {reason}'
            duration = 'forever'

        if channel is None:
            channel = ctx.channel
            overwrite = channel.overwrites_for(server.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(server.default_role, overwrite=overwrite)
            await ctx.send(f"{self.bot.check} Indefinitely locked {channel.mention}.")
            return
        
        if duration == "forever":
            overwrite = channel.overwrites_for(server.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(server.default_role, overwrite=overwrite)
            await ctx.send(f"{self.bot.check} Indefinitely locked {channel.mention}.")
        else:
            overwrite = channel.overwrites_for(server.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(server.default_role, overwrite=overwrite)
            await ctx.send(f"{self.bot.check} Locked {channel.mention} for **{duration}**.")
            until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
            await self.reminders.create_timer(until_dt_obj, 'templock', ctx.guild.id, ctx.author.id, channel.id, 0, created=ctx.message.created_at)

    @lockdown.error
    async def lockdown_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            duration = ctx.message.content.split()[1]
            reason = "".join(ctx.message.content.split()[2::])
            server = ctx.guild
            channel = ctx.channel
            try:
                seconds = Duration(duration).to_seconds()
            except:
                seconds = "forever"

            if seconds == 0 or seconds == "forever":
                reason = f'{duration} {reason}'
                duration = 'forever'

            if duration == "forever":
                overwrite = channel.overwrites_for(server.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(server.default_role, overwrite=overwrite)
                await ctx.send(f"{self.bot.check} Indefinitely locked {channel.mention}.")
            else:
                overwrite = channel.overwrites_for(server.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(server.default_role, overwrite=overwrite)
                await ctx.send(f"{self.bot.check} Locked {channel.mention} for **{duration}**.")
                until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
                await self.reminders.create_timer(until_dt_obj, 'templock', ctx.guild.id, ctx.author.id, channel.id, 0, created=ctx.message.created_at)

    @command(name="case", aliases=['vc', 'view-case', 'viewcase'], usage="<case_id:int>", brief="View a case's information.")
    @has_guild_permissions(manage_messages=True)
    async def case(self, ctx: Context, case_id: str):
        """View a case's information."""

        server = ctx.guild

        case_id = int(case_id.replace(",", "").replace("#", ""))
        case = await ctx.fetchrow("SELECT * FROM cases WHERE guild_id=$1 AND case_id=$2", server.id, case_id)
        if not case:
            return await ctx.send(f"{self.bot.x} **I could not find a case that matched that ID.**")
        
        user = await self.bot.fetch_user(case['user_id'])
        moderator = await self.bot.fetch_user(case['moderator_id'])

        embed = discord.Embed(color=self.modlog.colors[case['action'].upper()], timestamp=case['created_at'])
        embed.set_author(name=f"Case #{case['case_id']:,} | {case['action'].lower().capitalize()}", icon_url=user.avatar_url)
        embed.description = "\n".join([
            f"**Offender:** {user} {user.mention} `{user.id}`",
            f"**Moderator:** {moderator} `{moderator.id}`",
            f"**Duration:** {case['duration']}\n**Reason:** {case['reason']}" if case['action'].lower() == "mute" or case['action'].lower() == "tempban" or case['action'].lower() == "forcemute" else f"**Reason:** {case['reason']}",
            f"**Jump:** [Click here]({case['jump_url']})"
        ])
        embed.set_footer(text="Case created at")
        await ctx.send(embed=embed)

    @commands.group(aliases=['purge'])
    @commands.guild_only()
    @has_guild_permissions(manage_messages=True)
    async def remove(self, ctx):
        """Removes messages that meet a criteria.
        In order to use this command, you must have Manage Messages permissions.
        Note that the bot needs Manage Messages as well. These commands cannot
        be used in a private message.
        When the command is done doing its work, you will get a message
        detailing which users got removed and how many messages got removed.
        """

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send(f'Too many messages to search given ({limit}/2000)')

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
        except discord.Forbidden as e:
            return await ctx.send('I do not have permissions to delete messages.')
        except discord.HTTPException as e:
            return await ctx.send(f'Error: {e} (try a smaller search?)')

        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)

        if len(to_send) > 2000:
            await ctx.send(f'{self.bot.check} Successfully removed {deleted} messages.', delete_after=10)
        else:
            await ctx.send(to_send, delete_after=10)

    @remove.command()
    async def embeds(self, ctx, search=100):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @remove.command()
    async def files(self, ctx, search=100):
        """Removes messages that have attachments in them."""
        await self.do_removal(ctx, search, lambda e: len(e.attachments))

    @remove.command()
    async def images(self, ctx, search=100):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @remove.command(name='all')
    async def _remove_all(self, ctx, search=100):
        """Removes all messages."""
        await self.do_removal(ctx, search, lambda e: True)

    @remove.command()
    async def user(self, ctx, member: discord.Member, search=100):
        """Removes all messages by the member."""
        await self.do_removal(ctx, search, lambda e: e.author == member)

    @remove.command()
    async def contains(self, ctx, *, substr: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send('The substring length must be at least 3 characters.')
        else:
            await self.do_removal(ctx, 100, lambda e: substr in e.content)

    @remove.command(name='bot', aliases=['bots'])
    async def _bot(self, ctx, prefix=None, search=100):
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)

    @remove.command(name='emoji', aliases=['emojis'])
    async def _emoji(self, ctx, search=100):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r'<a?:[a-zA-Z0-9\_]+:([0-9]+)>')
        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @remove.command(name='reactions')
    async def _reactions(self, ctx, search=100):
        """Removes all reactions from messages that have them."""

        if search > 2000:
            return await ctx.send(f'Too many messages to search for ({search}/2000)')

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(f'{self.bot.check} Successfully removed {total_reactions} reactions.')

    @Cog.listener()
    async def on_tempban_timer_complete(self, timer):
        guild_id, mod_id, member_id, case_id = timer.args
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        
        moderator = guild.get_member(mod_id)
        user = await self.bot.fetch_user(member_id)

        case = await self.bot.db.fetchrow("SELECT * FROM cases WHERE guild_id=$1 AND case_id=$2", guild.id, case_id)
        reason = f"Automatic unban from a previous temp-ban ([`#{case_id:,}`]({case['jump_url']})), made **{time.human_timedelta(timer.created_at, brief=True)}**."
        await guild.unban(discord.Object(id=member_id), reason=reason)
        await self.modlog.create_case(guild, user, self.bot.user, "Unban", reason)

    @Cog.listener()
    async def on_tempmute_timer_complete(self, timer):
        guild_id, mod_id, member_id, case_id = timer.args
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        
        moderator = guild.get_member(mod_id)
        user = guild.get_member(member_id)
        muted_role =  guild.get_role(mutedrole[guild.id])

        case = await self.bot.db.fetchrow("SELECT * FROM cases WHERE guild_id=$1 AND case_id=$2", guild.id, case_id)
        reason = f"Automatic unmute from a previous temp-mute ([`#{case_id:,}`]({case['jump_url']})), made **{time.human_timedelta(timer.created_at, brief=True)}**."
        await user.remove_roles(muted_role, reason=reason)
        await self.modlog.create_case(guild, user, self.bot.user, "Unmute", reason)

    @Cog.listener()
    async def on_templock_timer_complete(self, timer):
        guild_id, mod_id, channel_id, case_id = timer.args
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return 
        channel = guild.get_channel(channel_id)
        overwrite = channel.overwrites_for(guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(guild.default_role, overwrite=overwrite)

        await channel.send(f"{self.bot.check} Lockdown created **{time.human_timedelta(timer.created_at)}** has expired.")

    async def case_embed(self, server, user, cases, title):

        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_author(name=f"{title} for {user}", icon_url=user.avatar_url)

        for case in cases:
            moderator = server.get_member(case['moderator_id'])
            if case['type'] == "Tempban" or case['type'] == "Mute":
                embed.add_field(name=f"Case #{case['case_id']:,} | {case['created_at']}", value="\n".join([
                    f"Moderator: {moderator} {moderator.mention if moderator else ''}",
                    f"Duration: {case['duration']}",
                    f"Jump URL: [Click here]({case['jump_url']})",
                    f"Reason: {case['reason']}"
                ]), inline=False)
            else:
                embed.add_field(name=f"Case #{case['case_id']:,} | {case['created_at']}", value="\n".join([
                    f"Moderator: {moderator} {moderator.mention if moderator else ''}",
                    f"Jump URL: [Click here]({case['jump_url']})",
                    f"Reason: {case['reason']}"
                ]), inline=False)
        return embed

def setup(bot):
    bot.add_cog(Moderation(bot))