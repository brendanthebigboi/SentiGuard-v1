import datetime

import discord
from discord.ext.commands import Cog, command, Context

from config import *

class Verification(Cog):
    def __init__(self, bot):
        self.bot = bot

def setup(bot):
    bot.add_cog(Verification(bot))