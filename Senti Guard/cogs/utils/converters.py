import re

import discord 
from discord.ext import commands 

ID_MATCHER = re.compile("<@!?([0-9]+)>")

class DiscordUser(commands.UserConverter):
  async def convert(self, ctx, argument):
    user = None
    match = ID_MATCHER.match(argument)
    if match is not None:
      argument = match.group(1)
    try:
      user = await commands.MemberConverter().convert(ctx, argument)
    except:
      user = await ctx.bot.fetch_user(argument)
      if not user:
        user = None
    return user

class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.isdigit():
            member_id = int(argument, base=10)
            try:
                return await ctx.guild.fetch_ban(discord.Object(id=member_id))
            except discord.NotFound:
                raise commands.BadArgument('This member has not been banned before.') from None

        ban_list = await ctx.guild.bans()
        entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

        if entity is None:
            raise commands.BadArgument('This member has not been banned before.')
        return entity