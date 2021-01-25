import datetime

import discord
from discord.ext.commands import Cog

from cogs.utils import time

class AutoEmergency(Cog):
    def __init__(self, bot):
        self.bot = bot

    async def add_log(self, server, log_type, classifier, channel):

        await self.bot.db.execute("""
        INSERT INTO logs (
            guild_id,
            type,
            created_at,
            classifier
        ) VALUES (
            $1, $2, $3, $4
        )
        """, server.id, log_type, datetime.datetime.utcnow(), classifier)

        automod_logs = await self.bot.db.fetch("""
        SELECT * FROM logs
        WHERE guild_id=$1
        AND type=$2
        """, server.id, "automod")
        automod_logs = [log for log in automod_logs if datetime.datetime.utcnow()-log['created_at']<datetime.timedelta(seconds=10*60)]

        antinuke_logs = await self.bot.db.fetch("""
        SELECT * FROM logs
        WHERE guild_id=$1
        AND type=$2
        """, server.id, "antinuke")
        antinuke_logs = [log for log in antinuke_logs if datetime.datetime.utcnow()-log['created_at']<datetime.timedelta(seconds=24*60*60)]
        if len(automod_logs) >= 3 and log_type == "automod":
            seconds = (automod_logs[-1]['created_at']-automod_logs[0]['created_at']).seconds
            dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
            await self.execute_auto_emergency_automod(server, channel, len(automod_logs), time_str)
        elif len(antinuke_logs) >= 3 and log_type == "antinuke":
            seconds = (antinuke_logs[-1]['created_at']-antinuke_logs[0]['created_at']).seconds
            dt_obj = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp()+seconds)
            time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
            await self.execute_auto_emergency_antinuke(server, antinuke_logs, time_str)
        else:
            return

    async def execute_auto_emergency_automod(self, server, channel, logs_found, duration):

        overwrite = channel.overwrites_for(server.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(server.default_role, overwrite=overwrite)

        await channel.send(
            f":shield: This channel has gone into an automatic lockdown, there was **{logs_found} automod actions** executed within **{duration}**."
        )

    async def execute_auto_emergency_antinuke(self, server, antinuke_logs, duration):
        dangerous_roles = [
            role for role in server.roles
            if role.permissions.administrator
            or role.permissions.ban_members
            or role.permissions.kick_members
            or role.permissions.manage_channels
            or role.permissions.manage_roles
            or role.permissions.mention_everyone
        ]
        changed_roles = []
        listed_dang_perms = [
            'administrator',
            'ban_members',
            'kick_members',
            'manage_channels',
            'manage_roles',
            'mention_everyone',
        ]

        for role in dangerous_roles:
            try:
                dangerous_perms = []
                for p, value in role.permissions:
                    if value and p in listed_dang_perms:
                        dangerous_perms.append(p)
                overwrite = role.permissions
                overwrite.ban_members = False
                overwrite.kick_members = False
                overwrite.manage_channels = False
                overwrite.manage_roles = False
                overwrite.administrator = False
                overwrite.manage_guild = False
                overwrite.mention_everyone = False
                await role.edit(permissions=overwrite)
                dangerous_perms = ", ".join([f"`{x}`" for x in dangerous_perms])
                changed_roles.append(f"{role.name}: {dangerous_perms}")
            except:
                continue
        
        roles = "\n".join(changed_roles)
        embed = discord.Embed(color=0xdd2e44, timestamp=datetime.datetime.utcnow())
        embed.description = "\n".join([
            f":rotating_light: Auto-emergency has been activated in the guild, `{server}`.",
            f"",
            f"**Information**",
            f"There were **{len(changed_roles)} roles** affected when auto-emergency was activiated:",
            roles
        ])
        await server.owner.send(embed=embed)

def setup(bot):
    bot.add_cog(AutoEmergency(bot))