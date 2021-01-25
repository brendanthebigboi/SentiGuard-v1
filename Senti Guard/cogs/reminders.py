import json
import traceback
import os
import sys
import datetime
import asyncio

import discord
from discord.ext import commands
from discord.ext.commands import command, Cog, group
import asyncpg
from durations_nlp import Duration

# pylint: disable=relative-beyond-top-level
from .utils import time, formats

class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires')

    def __init__(self, *, record):
        self.id = record['id']

        extra = json.loads(record['extra'])
        self.args = extra.get('args', [])
        self.kwargs = extra.get('kwargs', {})
        self.event = record['event']
        self.created_at = record['created']
        self.expires = record['expires']

    @classmethod
    def temporary(cls, *, expires, created, event, args, kwargs):
        pseudo = {
            'id': None,
            'extra': json.dumps({ 'args': args, 'kwargs': kwargs }),
            'event': event,
            'created': created,
            'expires': expires
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return time.human_timedelta(self.created_at)

    def __repr__(self):
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'

class Reminders(Cog):
    def __init__(self, bot):
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())

    def cog_unload(self):
        self._task.cancel()

    async def get_active_timer(self, days=7):
        query = "SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;"

        record = await self.bot.db.fetchrow(query, datetime.timedelta(days=days))
        return Timer(record=record) if record else None

    async def wait_for_active_timers(self, *, days=7):
        timer = await self.get_active_timer(days=days)
        if timer is not None:
            self._have_data.set()
            return timer

        self._have_data.clear()
        self._current_timer = None
        await self._have_data.wait()
        return await self.get_active_timer(days=days)

    async def call_timer(self, timer):
        query = "DELETE FROM reminders WHERE id=$1;"
        await self.bot.db.execute(query, timer.id)

        event = timer.event
        event_name = f'{event}_timer_complete'
        self.bot.dispatch(event_name, timer)

    async def dispatch_timers(self):
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                now = datetime.datetime.utcnow()

                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    async def short_timer_optimistation(self, seconds, timer):
        await self.bot.wait_until_ready()
        await asyncio.sleep(seconds)
        event_name = f"{timer.event}_timer_complete"
        self.bot.dispatch(event_name, timer)

    async def create_timer(self, *args, **kwargs):
        when, event, *args = args
        try:
            now = kwargs.pop('created')
        except KeyError:
            now = datetime.datetime.utcnow()

        timer = Timer.temporary(event=event, args=args, kwargs=kwargs, expires=when, created=now)
        delta = (when - now).total_seconds()
        if delta <= 60:
            self.bot.loop.create_task(self.short_timer_optimistation(delta, timer))
            return timer

        query = """
        INSERT INTO reminders (event, extra, expires, created)
        VALUES ($1, $2::jsonb, $3, $4)
        RETURNING id;
        """

        row = await self.bot.db.fetchrow(query, event, json.dumps({ 'args': args, 'kwargs': kwargs }), when, now)
        timer.id = row[0]

        if delta <= (86400 * 40):
            self._have_data.set()

        if self._current_timer and when < self._current_timer.expires:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @Cog.listener()
    async def on_timer_edit(self, server):
        self._task.cancel()
        self._task = self.bot.loop.create_task(self.dispatch_timers())

def setup(bot):
    bot.add_cog(Reminders(bot))
