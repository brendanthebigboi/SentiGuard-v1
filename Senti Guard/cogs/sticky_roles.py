import discord
from discord.ext.commands import Cog
import asyncio

class StickyRoles(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener(name="on_member_remove")
    async def member_remove(self, member: discord.Member):

        guild = member.guild
        roles = [role.id for role in member.roles]
        await self.bot.db.execute("""
        INSERT INTO sticky_roles (
            guild_id,
            user_id,
            roles,
            nick
        ) VALUES (
            $1, $2, $3, $4
        )
        """, guild.id, member.id, roles, member.display_name)

    @Cog.listener(name="on_member_join")
    async def member_join(self, member: discord.Member):
        await asyncio.sleep(.1)
        guild = member.guild
        sticky_roles = await self.bot.db.fetchrow("SELECT * FROM sticky_roles WHERE guild_id=$1 AND user_id=$2", guild.id, member.id)
        if not sticky_roles: return

        for role in sticky_roles['roles']:
            try:
                await member.add_roles(guild.get_role(role))
            except:
                continue
        await self.bot.db.execute("DELETE FROM sticky_roles WHERE guild_id=$1 AND user_id=$2", guild.id, member.id)
        await member.edit(nick=sticky_roles['nick'])

def setup(bot):
    bot.add_cog(StickyRoles(bot))