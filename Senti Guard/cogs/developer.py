import contextlib
import inspect
import logging
import pprint
import re
import textwrap
import traceback
from io import StringIO, BytesIO
import os
import psutil
import time
import sys, threading
from datetime import datetime, timedelta
import asyncio
import requests
import json

import discord
from discord.ext import commands
from discord.ext.commands import command, is_owner

# from .utils import time, arg # pylint: disable=relative-beyond-top-level

class Development(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.env = {}
        self.ln = 0
        self.stdout = StringIO()

    def _format(self, inp, out):  # (str, Any) -> (str, discord.Embed)
        self._ = out

        res = ""

        # Erase temp input we made
        if inp.startswith("_ = "):
            inp = inp[4:]

        # Get all non-empty lines
        lines = [line for line in inp.split("\n") if line.strip()]
        if len(lines) != 1:
            lines += [""]

        # Create the input dialog
        for i, line in enumerate(lines):
            if i == 0:
                # Start dialog
                start = f"In [{self.ln}]: "

            else:
                # Indent the 3 dots correctly;
                # Normally, it's something like
                # In [X]:
                #    ...:
                #
                # But if it's
                # In [XX]:
                #    ...:
                #
                # You can see it doesn't look right.
                # This code simply indents the dots
                # far enough to align them.
                # we first `str()` the line number
                # then we get the length
                # and use `str.rjust()`
                # to indent it.
                start = "...: ".rjust(len(str(self.ln)) + 7)

            if i == len(lines) - 2:
                if line.startswith("return"):
                    line = line[6:].strip()

            # Combine everything
            res += (start + line + "\n")

        self.stdout.seek(0)
        text = self.stdout.read()
        self.stdout.close()
        self.stdout = StringIO()

        if text:
            res += (text + "\n")

        if out is None:
            # No output, return the input statement
            return (res, None)

        res += f"Out[{self.ln}]: "

        if isinstance(out, discord.Embed):
            # We made an embed? Send that as embed
            res += "<Embed>"
            res = (res, out)

        else:
            if (isinstance(out, str) and out.startswith("Traceback (most recent call last):\n")):
                # Leave out the traceback message
                out = "\n" + "\n".join(out.split("\n")[1:])

            if isinstance(out, str):
                pretty = out
            else:
                pretty = pprint.pformat(out, compact=True, width=60)

            if pretty != str(out):
                # We're using the pretty version, start on the next line
                res += "\n"

            if pretty.count("\n") > 20:
                # Text too long, shorten
                li = pretty.split("\n")

                pretty = ("\n".join(li[:3])  # First 3 lines
                          + "\n ...\n"  # Ellipsis to indicate removed lines
                          + "\n".join(li[-3:]))  # last 3 lines

            # Add the output
            res += pretty
            res = (res, None)

        return res  # Return (text, embed)

    async def _eval(self, ctx, code):  # (discord.Context, str) -> None

        self.ln += 1

        if code.startswith("exit"):
            self.ln = 0
            self.env = {}
            return await ctx.send("```Reset history!```")

        env = {
            "message": ctx.message,
            "author": ctx.message.author,
            "channel": ctx.channel,
            "server": ctx.guild,
            "ctx": ctx,
            "self": self,
            "bot": self.bot,
            "inspect": inspect,
            "discord": discord,
            "contextlib": contextlib,
            "datetime": datetime,
            "timedelta": timedelta
        }

        self.env.update(env)

        # Ignore this code, it works
        _code = """
async def func():  # (None,) -> Any
    try:
        with contextlib.redirect_stdout(self.stdout):
{0}
        if '_' in locals():
            if inspect.isawaitable(_):
                _ = await _
            return _
    finally:
        self.env.update(locals())
""".format(textwrap.indent(code, '            '))

        try:
            exec(_code, self.env)  # noqa: B102,S102
            func = self.env['func']
            res = await func()

        except Exception:
            res = traceback.format_exc()

        out, embed = self._format(code, res) # pylint: disable=unused-variable
        await ctx.send(f"```py\n{out}```")

    @commands.command(aliases=['e'])
    @commands.is_owner()
    async def eval(self, ctx, *, code: str):
        """ Run eval in a REPL-like format. """
        code = code.strip("`")
        if re.match('py(thon)?\n', code):
            code = "\n".join(code.split("\n")[1:])

        if not re.search(  # Check if it's an expression
                r"^(return|import|for|while|def|class|"
                r"from|exit|[a-zA-Z0-9]+\s*=)", code, re.M) and len(
                    code.split("\n")) == 1:
            code = "_ = " + code
            
        await self._eval(ctx, code)

    @command(name="reload", aliases=['r'], hidden=True)
    @is_owner()
    async def reload(self, ctx, cog: str = None):

        cog_formatter = ""
        if cog is None:

            for cog in self.bot.unloaded_cogs:
                try:
                    self.bot.reload_extension(cog)
                    cog_formatter += f":repeat: `{cog}`\n\n"
                except Exception as e:
                    exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                    cog_formatter += f":repeat: :warning: `{cog}`\n```py\n{exc}\n```\n\n"

        else:

            try:
                self.bot.reload_extension(cog)
                cog_formatter += f":repeat: `{cog}`\n\n"
            except Exception as e:
                exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                cog_formatter += f":repeat: :warning: `{cog}`\n```py\n{exc}\n```\n\n" 

        await ctx.send(cog_formatter)

    @command(name="restart", hidden=True)
    @is_owner()
    async def restart(self, ctx):

        confirm = await ctx.prompt(f":octagonal_sign: Hold up! Are you sure you want to logout?")
        if confirm is False:
            await ctx.send(f":call_me: Restart aborted...")
        else:
            await ctx.send(":outbox_tray: Logging out now...")
            await self.bot.close()             

    @command(name="read", hidden=True)
    @is_owner()
    async def read(self, ctx, link):

        try:
            response = requests.get(link)
            image = BytesIO(response.content)

            await ctx.send(file=discord.File(image, "read.png"))
        except Exception as e:
            await ctx.send(f"{self.bot.x} Something happened: `{e}`.")

    @command(name="migrate", hidden=True)
    @is_owner()
    async def migrate(self, ctx, table_name):
        """Migrate a certain table to a JSON file."""

        starting_time = time.time()
        column_names = await ctx.fetch("SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE table_name=$1", table_name)
        if not column_names:
            return await ctx.send(f"{self.bot.x} I could not find a table with more than 1 column.")

        table = await ctx.fetch(f"SELECT * FROM {table_name}")
        migration_list = []

        for column in table:
            current_column_dict = {}
            for column_name in column_names:
                datetime_type = "datetime.datetime" in str(type(column[column_name['column_name']]))
                if datetime_type:
                    current_column_dict.update({column_name['column_name']: column[column_name['column_name']].timestamp()})
                else:
                    current_column_dict.update({column_name['column_name']: column[column_name['column_name']]})
            migration_list.append(current_column_dict)

        with open(f"{table_name}_migration.json", "w+") as file:
            json.dump(migration_list, file, indent=4)

        await ctx.send(content="\n".join([
        f":alarm_clock: Initial mirgration took around **{round((time.time()-starting_time))} seconds**.",
        f":file_folder: There were **{len(migration_list)} items** transfered to a JSON file."
        ]),
        file=discord.File(f"{table_name}_migration.json"))


def setup(bot):                                                                                                     
    bot.add_cog(Development(bot))