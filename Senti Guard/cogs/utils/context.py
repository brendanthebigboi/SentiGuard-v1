import asyncio
import json

import discord
from discord.ext import commands

class Context(commands.Context):
    async def fetch(self, query: str, *params: tuple):
        """
        shortcut for `self.bot.db.fetch` -> `ctx.fetch`
        """
        return await self.bot.db.fetch(query, *params)

    async def fetchrow(self, query: str, *params: type):
        """
        shortcut for `self.bot.db.fetchrow` -> `ctx.fetchrow`
        """
        return await self.bot.db.fetchrow(query, *params)

    async def execute(self, query: str, *params: type):
        """
        shortcut for `self.bot.db.execute` -> `ctx.execute`
        """
        return await self.bot.db.execute(query, *params)

    async def prompt(self, message, *, timeout=60.0, delete_after=True, author_id=None):

        msg = await self.send(f"{message}\n\nReact with :white_check_mark: to confirm.\nReact with :x: to abort.")

        author_id = author_id or self.author.id
        confirm = None

        def check(payload):
            nonlocal confirm

            if payload.message_id != msg.id or payload.user_id != author_id:
                return False

            codepoint = str(payload.emoji)

            if codepoint == '\N{WHITE HEAVY CHECK MARK}':
                confirm = True
                return True
            elif codepoint == '\N{CROSS MARK}':
                confirm = False
                return True

            return False

        for emoji in ('\N{WHITE HEAVY CHECK MARK}', '\N{CROSS MARK}'):
            await msg.add_reaction(emoji)

        try:
            await self.bot.wait_for('raw_reaction_add', check=check, timeout=timeout)
        except asyncio.TimeoutError:
            confirm = None

        try:
            if delete_after:
                await msg.delete()
        finally:
            return confirm
