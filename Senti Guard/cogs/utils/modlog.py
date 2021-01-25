import datetime
import json

import discord
from discord.ext import commands
from discord.ext.commands import Cog

import cogs.utils.time as time
from config import *

class Modlog(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.actions = {
            "WARN": 1,
            "MUTE": 2,
            "KICK": 3,
            "BAN": 4,
            "SOFTBAN": 5,
            "TEMPBAN": 6,
            "UNMUTE": 7,
            "UNBAN": 8,
            "FORCE-MUTE": 9
        }
        self.colors = {
            "MUTE": 0x0d92ff,
            "WARN": 0xffff4d,
            "UNMUTE": 0x87ffa9,
            "UNBAN": 0x87ffa9,
            "BAN": 0xdd2e44,
            "TEMPBAN": 0x8789ff,
            "KICK": 0xff87e1,
            "SOFTBAN": 0xff87e1,
            "FORCE-MUTE": 0x2bd1ff
        }

    @property
    def reminders(self):
        return self.bot.get_cog("Reminders")

    async def create_case(self, server, user, moderator, action, reason, duration=None):
        server_cases = await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1", server.id)
        action_type = self.actions[action.upper()]
        case = len(server_cases)+1 if server_cases is not None else 0

        if not reason:
            reason = "No reason was provided."
        
        # get the staff logs channel if the moderator id is different than the bots id
        # if the bot is id is the moderator id, it is an automated case
        chan = server.get_channel(modlog_channel_id[server.id]) if moderator.id != self.bot.user.id else server.get_channel(server_log_id[server.id])
        if not chan:
            await self.bot.db.execute("""
            INSERT INTO cases (
                case_id,
                guild_id,
                user_id,
                moderator_id,
                message_id,
                action,
                type,
                created_at,
                reason,
                duration,
                jump_url
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
            )
            """, case, server.id, user.id, moderator.id, None, action, action_type,
            datetime.datetime.utcnow(), reason, duration, None)
        else:
            action_color = self.colors[action.upper()]
            if action_type == 2 or action_type == 6:
                embed = discord.Embed(color=action_color, timestamp=datetime.datetime.utcnow())
                embed.set_author(name=f"{action} | #{case:,}", icon_url=user.avatar_url)
                embed.description = '\n'.join([
                    f"**Offender:** {user} `{user.id}` {user.mention}",
                    f"**Moderator:** {moderator} `{moderator.id}`",
                    f"**Duration:** {duration}",
                    f"**Reason:** {reason}"
                ])
                msg = await chan.send(embed=embed)
                await self.bot.db.execute("""
                INSERT INTO cases (
                    case_id,
                    guild_id,
                    user_id,
                    moderator_id,
                    message_id,
                    action,
                    type,
                    created_at,
                    reason,
                    duration,
                    jump_url
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
                )
                """, case, server.id, user.id, moderator.id, None, action, action_type,
                datetime.datetime.utcnow(), reason, duration, msg.jump_url)
            elif action_type == 9:
                embed = discord.Embed(color=action_color, timestamp=datetime.datetime.utcnow())
                embed.set_author(name=f"{action} | #{case:,}", icon_url=user.avatar_url)
                embed.description = '\n'.join([
                    f"**Offender:** {user} `{user.id}` {user.mention}",
                    f"**Moderator:** {moderator} `{moderator.id}`",
                    f"**Duration:** {duration['msg']}",
                    f"**Reason:** {reason}"
                ])
                msg = await chan.send(embed=embed)
                await self.bot.db.execute("""
                INSERT INTO cases (
                    case_id,
                    guild_id,
                    user_id,
                    moderator_id,
                    message_id,
                    action,
                    type,
                    created_at,
                    reason,
                    duration,
                    jump_url
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
                )
                """, case, server.id, user.id, moderator.id, None, action, action_type,
                datetime.datetime.utcnow(), reason, duration, msg.jump_url)
            else:
                embed = discord.Embed(color=action_color, timestamp=datetime.datetime.utcnow())
                embed.set_author(name=f"{action} | #{case:,}", icon_url=user.avatar_url)
                embed.description = '\n'.join([
                    f"**Offender:** {user} `{user.id}` {user.mention}",
                    f"**Moderator:** {moderator} `{moderator.id}`",
                    f"**Reason:** {reason}"
                ])
                msg = await chan.send(embed=embed)
                await self.bot.db.execute("""
                INSERT INTO cases (
                    case_id,
                    guild_id,
                    user_id,
                    moderator_id,
                    message_id,
                    action,
                    type,
                    created_at,
                    reason,
                    duration,
                    jump_url
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
                )
                """, case, server.id, user.id, moderator.id, None, action, action_type,
                datetime.datetime.utcnow(), reason, duration, msg.jump_url)
        return case
    async def warn(self, server, user, channel, moderator, reason):
        case = await self.create_case(server, user, moderator, "Warn", reason)

        user_warnings = len(await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND type=$3", server.id, user.id, 1))
        warning_rules = self.bot.config['warnings']
        warning_prefixed = self.prefixfy(int(user_warnings))
        msg = await channel.send(f":white_check_mark: `Case #{case:,}` {user.mention} **has been warned, this is their {warning_prefixed} warning.**")

        reason = f"Hit their **{warning_prefixed}** warning."
        if user_warnings in warning_rules:

            warning_data = warning_rules[user_warnings]

            if warning_data['action'] == "ban":
                try:
                    await user.ban(reason=f"Hitting their {warning_prefixed} warning.")
                except discord.Forbidden:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I am lacking the permissions to ban this user.")
                except discord.HTTPException:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I could not ban this user due to an odd error.")
                
                # pylint: disable=unused-variable
                reason = f"hitting their `{warning_prefixed}` warning."
                applied_case = await self.create_case(server, self.bot.user , user, "Ban", reason.capitalize())
                await msg.edit(content=f"{msg.content}\n{self.bot.check} Applied an indefinite ban to **{user}**. (`#{applied_case:,}`)")
            elif warning_data['action'] == "kick":
                try:
                    await user.kick(reason=f"Hitting their {warning_prefixed} warning.")
                except discord.Forbidden:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I am lacking the permissions to kick this user.")
                except discord.HTTPException:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I could not kick this user due to an odd error.")

                # pylint: disable=unused-variable
                reason = f"hitting their `{warning_prefixed}` warning."
                applied_case = await self.create_case(server, user, self.bot.user, "Kick", reason.capitalize())
                await msg.edit(content=f"{msg.content}\n{self.bot.check} Applied a kick to **{user}**. (`#{applied_case:,}`)")
            # specified duration mute
            elif warning_data['action'] == "mute" and warning_data.get("duration") is not None:
                try:
                    await user.add_roles(discord.Object(id=mutedrole[server.id]), reason=f"Hitting their {warning_prefixed} warning.")
                except discord.Forbidden:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I am lacking the permissions to mute this user.")
                except discord.HTTPException:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I could not mute this user due to an odd error.")
                
                query = """SELECT *
                    FROM reminders
                    WHERE extra #>> '{args,2}' = $2
                    AND extra #>> '{args,0}' = $1
                    AND event='tempmute'
                    ORDER BY expires
                    LIMIT 10;
                """
                records = await self.bot.db.fetch(query, str(server.id), str(user.id))
                if records:
                    old_unmute_dt = records[0]['expires']
                    old_seconds = (old_unmute_dt-datetime.datetime.utcnow()).seconds
                    new_unmute_dt = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+warning_data['duration']+old_seconds)

                    await self.bot.db.execute("""
                    UPDATE reminders SET expires=$1
                    WHERE event = 'tempmute'
                    AND extra #>> '{args,0}' = $2
                    AND extra #>> '{args,2}' = $3
                    """, new_unmute_dt, str(server.id), str(user.id))
                    self.bot.dispatch("timer_edit", server)
                    await msg.edit(content=f"{msg.content}\n{self.bot.check} Updated the mute time for **{user}** to {time.human_timedelta(new_unmute_dt)}.")
                else:
                    seconds = warning_data['duration']
                    until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
                    until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
                    time_str = time.human_timedelta(until_dt_obj)
                    case = await self.create_case(server, user, self.bot.user, "Mute", reason, time_str) # pylint: disable=unused-variable
                    await self.reminders.create_timer(until_dt_obj, 'tempmute', server.id, moderator.id, user.id, case, created=msg.created_at)
                    await msg.edit(content=f"{msg.content}\n:white_check_mark: `Case #{case:,}` {user.mention} **has been temp-muted for {time_str}.**")
            elif warning_data['action'] == "mute" and warning_data.get("duration") is None:
                try:
                    await user.add_roles(discord.Object(id=mutedrole[server.id]), reason=f"Hitting their {warning_prefixed} warning.")
                except discord.Forbidden:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I am lacking the permissions to mute this user.")
                except discord.HTTPException:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I could not mute this user due to an odd error.")

                case = await self.create_case(server, moderator, user, "Mute", reason, "Indefinitely")
                query = """SELECT *
                    FROM reminders
                    WHERE extra #>> '{args,2}' = $2
                    AND extra #>> '{args,0}' = $1
                    AND event='tempmute'
                    ORDER BY expires
                    LIMIT 10;
                """
                records = await self.bot.db.fetch(query, str(server.id), str(user.id))
                if records:
                    for reminder in records:
                        await self.bot.db.execute("DELETE FROM reminders WHERE id=$1", reminder['id'])

                    await msg.edit(content=f"{msg.content}\n{self.bot.check} Applied an indefinite mute to **{user}** whilst removing their previous mute timers. (`#{case:,}`)")
                else:
                    await msg.edit(content=f"{msg.content}\n{self.bot.check} Applied an indeifnite mute to **{user}**. (`#{case:,}`)")
            elif warning_data['action'] == "tempban" and warning_data.get("duration") is not None:
                try:
                    await user.ban(reason=f"Hitting their {warning_prefixed} warning.")
                except discord.Forbidden:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I am lacking the permissions to tempban this user.")
                except discord.HTTPException:
                    return await msg.edit(content=f"{msg.content}\n{self.bot.x} I could not tempban this user due to an odd error.")

                seconds = warning_data['duration']
                until_dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + seconds)
                until_dt_fm = until_dt_obj.strftime("%B, %d, %I:%M %p")
                time_str = time.human_timedelta(until_dt_obj)
                case = await self.create_case(server, user, self.bot.user, "Tempban", reason, time_str) # pylint: disable=unused-variable
                await self.reminders.create_timer(until_dt_obj, 'tempban', server.id, moderator.id, user.id, case, created=msg.created_at)
                await msg.edit(content=f"{msg.content}\n{self.bot.check} Applied a temp-ban to **{user}** until {until_dt_fm} ({time_str}). (`#{case:,}`)")

    # async def create_hastebin(self, title, description):
    #     print(1)
    #     r = await self.bot.session.post(url="https://hastebin.com/documents", data=title+description)
    #     print(2)
    #     data = await r.json()
    #     return f"https://hastebin.com/{data['key']}"

    def prefixfy(self, input):
        number = str(input)
        num = len(number) - 2
        num2 = len(number) - 1
        if int(number[num:]) < 11 or int(number[num:]) > 13:
            if int(number[num2:]) == 1:
                prefix = "st"
            elif int(number[num2:]) == 2:
                prefix = "nd"
            elif int(number[num2:]) == 3:
                prefix = "rd"
            else:
                prefix = "th"
        else:
            prefix = "th"
        return number + prefix

def setup(bot):
    bot.add_cog(Modlog(bot))