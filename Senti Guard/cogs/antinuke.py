from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord.ext.commands import Cog

from .utils import time

class Antinuke(Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def modlog(self):
        return self.bot.get_cog("Modlog")
    @property
    def auto_emergency(self):
        return self.bot.get_cog("AutoEmergency")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.ChannelType):

        server = channel.guild

        async for entry in server.audit_logs(action=discord.AuditLogAction.channel_delete, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != channel.id:
                continue
            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "channel_deletion",
                    channel.id,
                    datetime.utcnow(),
                )
            except Exception as e:
                print(e)
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_deletion")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Deleted {len(recent_logs)} channels in {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_deletion")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Deleted {len(recent_logs)} channels in {time_str}")
                    await self.auto_emergency.add_log(server, "antinuke", "channel_delete", None)
                except discord.Forbidden:
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_deletion")
                    pass
                async for channel_deletion in server.audit_logs(user=user, limit=len(recent_logs), action=discord.AuditLogAction.channel_delete):
                    deleted_channel = channel_deletion.before
                    if deleted_channel.type == 2:
                        await server.create_voice_channel(
                            name=deleted_channel.name,
                            overwrites=dict(deleted_channel.overwrites),
                            bitrate=deleted_channel.bitrate
                        )
                    elif deleted_channel.type == 0:
                        await server.create_text_channel(
                            name=deleted_channel.name,
                            overwrites=dict(deleted_channel.overwrites),
                            nsfw=deleted_channel.nsfw,
                            slowmode_delay=deleted_channel.slowmode_delay
                        )
                    else:
                        await server.create_category(
                            name=deleted_channel.name,
                            overwrites=dict(deleted_channel.overwrites)
                        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.ChannelType):
        server = channel.guild
        print(channel)
        async for entry in server.audit_logs(action=discord.AuditLogAction.channel_create, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != channel.id:
                continue
            if user.top_role.position >=server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "channel_creation",
                    channel.id,
                    datetime.utcnow(),
                )
            except:
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_creation")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Created {len(recent_logs)} channels within {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_creation")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Created {len(recent_logs)} channels in {time_str}.")
                    await self.auto_emergency.add_log(server, "antinuke", "channel_create", None)
                except discord.Forbidden:
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "channel_creation")
                    continue
                async for created_channel in server.audit_logs(user=user, limit=len(recent_logs), action=discord.AuditLogAction.channel_create):
                    await created_channel.target.delete()

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        server = role.guild

        async for entry in server.audit_logs(action=discord.AuditLogAction.role_delete, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != role.id:
                continue
            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "role_deletion",
                    role.id,
                    datetime.utcnow(),
                )
            except:
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_deletion")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                # await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2", server.id, user.id)
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Deleted {len(recent_logs)} roles in {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_deletion")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Deleted {len(recent_logs)} roles in {time_str}")
                    await self.auto_emergency.add_log(server, "antinuke", "role_delete", None)
                except discord.Forbidden:
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_deletion")
                    pass
                async for role_deletion in server.audit_logs(user=entry.user, limit=len(recent_logs), action=discord.AuditLogAction.role_delete):
                    deleted_role = role_deletion.before
                    await server.create_role(
                        name=deleted_role.name,
                        permissions=deleted_role.permissions,
                        color=deleted_role.color,
                        hoist=deleted_role.hoist,
                        mentionable=deleted_role.mentionable
                    )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        server = role.guild

        async for entry in server.audit_logs(action=discord.AuditLogAction.role_create, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != role.id:
                continue
            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "role_creation",
                    role.id,
                    datetime.utcnow(),
                )
            except:
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_creation")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                # await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2", server.id, user.id)
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Created {len(recent_logs)} roles in {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_creation")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Created {len(recent_logs)} roles in {time_str}.")
                    await self.auto_emergency.add_log(server, "antinuke", "role_create", None)
                except discord.Forbidden:
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "role_creation")
                    continue
                async for created_role in server.audit_logs(user=user, limit=len(recent_logs), action=discord.AuditLogAction.role_create, after=datetime.utcnow()-timedelta(minutes=30)):
                    await created_role.target.delete()

    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        server = guild

        async for entry in server.audit_logs(action=discord.AuditLogAction.ban, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != member.id:
                continue
            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "member_ban",
                    user.id,
                    datetime.utcnow()
                )
            except Exception as e:
                print(e)
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "member_ban")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Banned {len(recent_logs)} users in {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 and nuke_type=$3", server.id, user.id, "member_ban")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Banned {len(recent_logs)} members in {time_str}.")
                    await self.auto_emergency.add_log(server, "antinuke", "member_ban", None)
                except:
                    print('Tried to ban that user.')
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type = $3", server.id, user.id, "member_ban")
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        server = member.guild
        async for entry in server.audit_logs(action=discord.AuditLogAction.kick, after=datetime.utcnow()-timedelta(minutes=30)):
            user = entry.user
            if user == self.bot.user:
                continue
            if entry.target.id != member.id:
                continue
            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                continue
            try:
                await self.bot.db.execute("INSERT INTO nukes (guild_id, user_id, nuke_type, id, logged_at) VALUES($1, $2, $3, $4, $5)",
                    server.id,
                    user.id,
                    "member_kick",
                    user.id,
                    datetime.utcnow()
                )
            except Exception as e:
                print(e)
                continue
            logs = await self.bot.db.fetch("SELECT * FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type=$3", server.id, user.id, "member_kick")
            recent_logs = [log for log in logs if datetime.utcnow() - log['logged_at'] <= timedelta(minutes=30)]
            if len(recent_logs) >= 5:
                if not user in server.members:
                    return
                try:
                    seconds = (recent_logs[-1]['logged_at']-recent_logs[0]['logged_at']).seconds
                    dt_obj = datetime.fromtimestamp(datetime.utcnow().timestamp()+seconds)
                    time_str = time.human_timedelta(dt_obj, brief=True, suffix=False)
                    await user.ban(reason=f"Kicked {len(recent_logs)} users in {time_str}.")
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 and nuke_type=$3", server.id, user.id, "member_kick")
                    await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Kicked {len(recent_logs)} members {time_str}.")
                    await self.auto_emergency.add_log(server, "antinuke", "member_kick", None)
                except:
                    print('Tried to ban that user.')
                    await self.bot.db.execute("DELETE FROM nukes WHERE guild_id=$1 AND user_id=$2 AND nuke_type = $3", server.id, user.id, "member_kick")
                    pass

                await server.owner.send(f":warning: Suspicous activity has been seen and I have taken care of it.\n**User:** {user}\n**Action:** Banned\n**Reason:** This user kicked **{len(recent_logs)} users** in under 30 minutes.")
    
    @Cog.listener(name="on_guild_role_update")
    async def role_update(self, before, after):
        server = before.guild
        if before.permissions.administrator != after.permissions.administrator is True or before.permissions.ban_members != after.permissions.ban_members is True or before.permissions.manage_roles != after.permissions.manage_roles is True or before.permissions.manage_channels != after.permissions.manage_channels is True or before.permissions.kick_members != after.permissions.kick_members is True or before.permissions.mention_everyone != after.permissions.mention_everyone is True:
            async for log in before.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                user = log.user
                if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                    continue
                target = log.target
                if target.id != before.id:
                    continue
                    
                overwrite = before.permissions
                overwrite.ban_members = False
                overwrite.manage_channels = False 
                overwrite.manage_roles = False
                overwrite.kick_members = False
                overwrite.administrator = False
                overwrite.manage_guild = False
                overwrite.mention_everyone = False
                await before.edit(permissions=overwrite)
                await log.user.ban(reason="Gave the role, {before}, dangerous permissions.")
                await self.modlog.create_case(before.guild, log.user, self.bot.user, "Ban", f"Gave the role, {before}, dangerous permissions.")
                await self.auto_emergency.add_log(before.guild, "antinuke", "dangerous_perms", None)
                return

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        server = before.guild 
        if len(after.roles) != len(before.roles):
            new_roles = set(after.roles) - set(before.roles)
            for role in new_roles:
                if len(role.members) >= 12:
                    if role.permissions.administrator == True or role.permissions.ban_members == True or role.permissions.kick_members == True or role.permissions.manage_channels == True or role.permissions.manage_roles == True:
                        for x in await server.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update).flatten():
                            user = x.user 
                            if user.top_role.position >= server.get_member(self.bot.user.id).top_role.position or user is server.owner:
                                continue
                            await user.ban(reason=f"Adding too many dangerous roles to 10+ members.")
                            await self.modlog.create_case(server, user, self.bot.user, "Ban", f"Gave multiple users dangerous roles.")
                            await self.auto_emergency.add_log(server, "antinuke", "mass_perms", None)
                        await role.delete(reason="Role with dangerous permissions are being given to too many people.")
def setup(bot):
    bot.add_cog(Antinuke(bot))