import discord 
from discord.ext import commands 
import datetime 
import traceback 

class Error_Handler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.author.send(f"{self.bot.x} **This command cannot be used in private messages.**")
        
        elif isinstance(error, commands.CommandNotFound):
            return 
        
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = "<"
            param = list(ctx.command.params.values())[min(len(ctx.args) + len(ctx.kwargs), len(ctx.command.params))]
            await ctx.send(f"{self.bot.x} **You are missing the required argument: `{param._name}`.\n:wrench: Usage: `{prefix}{ctx.command} {ctx.command.usage}`**")
        
        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join([f"`{perm.replace('_', ' ')}`" for perm in error.missing_perms])
            await ctx.send(f"\n{self.bot.x} **You are missing the permissions: {perms}.**") 
        elif isinstance(error, commands.MissingAnyRole):
            roles = ", ".join(error.missing_roles)
            await ctx.send(f"{self.bot.x} **You are missing the roles: {roles}.**")
        else:
            exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
            cmd = ctx.command 
            author = ctx.author 
            channel = self.bot.get_channel(self.bot.config['error_logs']) 
            time_executed = datetime.datetime.utcnow().strftime("%A, %B %d, %I:%M %p")
            await channel.send(f"""
An error occured in the **{cmd.name}** command.
**Executed by:** {author} (ID: {author.id}) 
**Executed in:** {ctx.guild.name} (ID: {ctx.guild.id}) 
**Time Errored:** {time_executed}
**Traceback:**\n```py\n{exc}\n```
            """)

def setup(bot):
    bot.add_cog(Error_Handler(bot))