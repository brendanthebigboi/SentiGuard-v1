import discord
from discord.ext import commands

ratelimited_dup_burst = commands.CooldownMapping.from_cooldown(1, 6, commands.BucketType.member)

def ratelimit_dup(message, current):
    bucket = ratelimited_dup_burst.get_bucket(message)
    if bucket.update_rate_limit(current):
        return True
    else:
        return False