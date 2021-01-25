import json
import datetime

import discord
from discord.ext.commands import Cog, command, Context
import asyncio

from .utils import time
from config import *

class InviteTracking(Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_trust_factor(self, created_at):

        if round(datetime.datetime.utcnow().timestamp() - created_at.timestamp() <= 604800):
            return 0
        else:
            return 1

    async def get_cases(self, server, member, case_type):

        if case_type == "mod":
            cases = await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND moderator_id!=$3", server.id, member.id, self.bot.user.id)
            return len(cases)
        else:
            cases = await self.bot.db.fetch("SELECT * FROM cases WHERE guild_id=$1 AND user_id=$2 AND moderator_id=$3", server.id, member.id, self.bot.user.id)
            return len(cases)

    @Cog.listener(name="on_invite_create")
    async def invite_crate(self, invite):

        await self.bot.db.execute("""
        INSERT INTO invites (
            guild_id,
            code,
            uses,
            max_uses,
            users,
            inviter
        ) VALUES (
            $1, $2, $3, $4, $5, $6
        )
        """, invite.guild.id, invite.code, invite.uses, invite.max_uses, json.dumps({}), invite.inviter.id)
        print(f"Created invite: {invite.code}")

    @Cog.listener(name="on_invite_delete")
    async def invite_delete(self, invite):
        await asyncio.sleep(.1)
        invite_db = await self.bot.db.fetchrow("SELECT * FROM invites WHERE code=$1", invite.code)
        if invite_db and invite_db['max_uses'] - invite_db['uses'] == 1:

            server = invite.guild
            member = sorted(server.members, key=lambda m: datetime.datetime.utcnow() - m.joined_at <= datetime.timedelta(seconds=1), reverse=True)[:1][0]

            users = json.loads(invite_db['users'])
            users.update({member.id: round(datetime.datetime.utcnow().timestamp())})

            await self.bot.db.execute("""
            UPDATE invites SET uses=$2, users=$3, code=$4 WHERE guild_id=$1 AND code=$4
            """, server.id, invite_db['uses'] + 1, json.dumps(users), invite.code)

            uses = invite.uses
            code = invite.code
            channel = server.get_channel(altlogs[server.id])
            trust_factor = self.get_trust_factor(member.created_at)
            determined_color = discord.Color.red() if trust_factor == 0 else discord.Color.green()
            created_at = time.human_timedelta(member.created_at, brief=True, suffix=False)
            mod_cases = await self.get_cases(server, member, "mod")
            automod_cases = await self.get_cases(server, member, "automod")

            embed = discord.Embed(color=determined_color, timestamp=datetime.datetime.utcnow())
            embed.set_author(name=f"{member} has joined the server", icon_url=member.avatar_url)
            embed.description = "\n".join([
                f":ticket: **{member}** ({member.id}) has joined the server using the invite `{code}` which is owned by **{invite.inviter}** ({invite.inviter.id}) with `{uses:,} uses` attached.",
                "",
                f":alarm_clock: I have given ***{member}** a {'high' if trust_factor > 0 else 'low'} trust factor because **{member}**'s account is {created_at} old.",
                "",
                f":hammer: **{member}** has `{mod_cases:,}` previous moderation cases and `{automod_cases:,}` previous automod cases.",
                ""
            ])
            await channel.send(embed=embed)

            return
        
        await self.bot.db.execute("""
        DELETE FROM invites WHERE code=$1
        """, invite.code)


    async def filter_invites(self, server):

        server_invites = await server.invites()
        for invite in server_invites:
            try:
                await self.bot.db.execute("""
                INSERT INTO invites (
                    guild_id,
                    code,
                    uses,
                    users,
                    inviter
                ) VALUES ($1, $2, $3, $4, $5)
                """, server.id, invite.code, invite.uses, json.dumps({}), invite.inviter.id)

            except:
                continue

    @Cog.listener()
    async def on_member_join(self, member):
        server = member.guild

        invites = await server.invites()
        saved_invites = await self.bot.db.fetch("SELECT * FROM invites WHERE guild_id=$1", server.id)
        for invite in saved_invites:
            for server_invite in invites:
                if server_invite.code == invite['code']:
                    if server_invite.uses != invite['uses']:
                        users = json.loads(invite['users'])
                        users.update({member.id: round(datetime.datetime.utcnow().timestamp())})
                        await self.bot.db.execute("""
                        UPDATE invites
                        SET uses=$2, users=$3
                        WHERE code=$1
                        """, invite['code'], server_invite.uses, json.dumps(users))

                        uses = server_invite.uses
                        code = server_invite.code
                        channel = server.get_channel(altlogs[server.id])
                        trust_factor = self.get_trust_factor(member.created_at)
                        determined_color = discord.Color.red() if trust_factor == 0 else discord.Color.green()
                        created_at = time.human_timedelta(member.created_at, brief=True)
                        mod_cases = await self.get_cases(server, member, "mod")
                        automod_cases = await self.get_cases(server, member, "automod")

                        embed = discord.Embed(color=determined_color, timestamp=datetime.datetime.utcnow())
                        embed.set_author(name=f"{member} has joined the server", icon_url=member.avatar_url)
                        embed.description = "\n".join([
                            f":ticket: **{member}** ({member.id}) has joined the server using the invite `{code}` which is owned by **{server_invite.inviter}** ({server_invite.inviter.id}) with `{uses:,} uses` attached.",
                            "",
                            f":alarm_clock: I have given **{member}** a {'high' if trust_factor > 0 else 'low'} trust factor because **{member}**'s account is {created_at} old.",
                            "",
                            f":hammer: **{member}** has `{mod_cases:,}` previous moderation cases and `{automod_cases:,}` previous automod cases.",
                            ""
                        ])
                        await channel.send(embed=embed)
                    else:
                        continue
                else:
                    continue

    async def track_user(self, server, user):

        invites = await self.bot.db.fetch("""
        SELECT guild_id, code, inviter, uses, users FROM invites WHERE guild_id=$1
        """, server.id)
        user_invites = [invite for invite in invites if str(user.id) in json.loads(invite['users'])]
        sorted_invites = sorted([(json.loads(invite['users']).get(str(user.id)), invite['code'], invite['inviter'], invite['uses']) for invite in user_invites], reverse=True)

        if len(sorted_invites) == 0:

            return False

        else:

            invite = sorted_invites[0]
            return invite

    @command(name="track", aliases=['inviter'], usage="<user>", brief="See who invited a certain user.")
    async def track(self, ctx, member: discord.Member = None):
        """
See who invited a certain user.

This will show the invite code and the owner of the invite.
        """
        server = ctx.guild

        if member is None:
            member = ctx.author

        if member.bot:
            who_ = 0
            when_ = None
            async for entry in server.audit_logs(action=discord.AuditLogAction.bot_add):
                if entry.target == member:
                    who_ = entry.user
                    when_ = entry.created_at.strftime("%A, %B %d, %Y at %I:%M %p")
                    break
            await ctx.send(f"**{member}** was added to the server by `{who_}` (ID: {who_.id}) on **{when_}**.")
            return

        invite = await self.track_user(server, member)

        if not invite:
            return await ctx.send(f"{self.bot.x} I could not find the invite that this user used to enter the server.")

        code = invite[1]
        inviter = server.get_member(invite[2])
        if not inviter:
            inviter = "Unknown"
        else:
            inviter = f"**{inviter}** (ID: {inviter.id})"

        await ctx.send(f":inbox_tray: **{member}** entered the server with the invite code `{code}`, which is owned by {inviter}. There are currently **{invite[3]} uses** on this invite.")



def setup(bot):
    bot.add_cog(InviteTracking(bot))