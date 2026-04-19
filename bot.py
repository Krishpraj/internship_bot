import asyncio
import logging
from datetime import date

import aiohttp
import discord

import readme
from config import CHANNEL_ID, DISCORD_TOKEN, SOURCES
from db import apply_url_exists, get_unsent, init_db, is_seen, mark_seen
from fetcher import fetch_readme
from parsers import get_parser
from parsers.base import Internship
from poster import post_internships

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def poll_cycle(channel: discord.abc.Messageable) -> list[Internship]:
    today = date.today()
    all_open: list[Internship] = []
    async with aiohttp.ClientSession() as session:
        for source in SOURCES:
            raw = await fetch_readme(session, source)
            if raw is None:
                continue

            parser = get_parser(source.parser)
            try:
                internships = parser.parse(raw, today)
            except Exception:
                log.exception("Parser error for %s", source.name)
                continue

            new_ones: list = []
            for item in internships:
                if item.is_closed:
                    continue
                all_open.append(item)
                if item.date_posted < today:
                    continue
                if is_seen(item.uid):
                    continue
                if apply_url_exists(item.apply_url):
                    mark_seen(item)
                    continue
                mark_seen(item)
                new_ones.append(item)

            if new_ones:
                await post_internships(channel, new_ones)
                log.info(
                    "%s: posted %d new internships", source.name, len(new_ones)
                )
            else:
                log.info("%s: no new internships", source.name)
    return all_open


async def backfill(channel: discord.abc.Messageable) -> None:
    today = date.today()
    unsent = get_unsent(today)
    if not unsent:
        log.info("Backfill: nothing to catch up on")
        return
    log.info("Backfill: posting %d missed internships", len(unsent))
    await post_internships(channel, unsent)


async def run_once() -> None:
    init_db()

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    ready = asyncio.Event()

    @client.event
    async def on_ready() -> None:
        log.info("Logged in as %s", client.user)
        ready.set()

    login_task = asyncio.create_task(client.start(DISCORD_TOKEN))
    try:
        await asyncio.wait_for(ready.wait(), timeout=30)
        channel = client.get_channel(CHANNEL_ID) or await client.fetch_channel(
            CHANNEL_ID
        )
        await backfill(channel)
        all_open = await poll_cycle(channel)
        if readme.write(all_open):
            log.info("README updated with %d open roles", len(all_open))
        else:
            log.info("README unchanged")
    finally:
        await client.close()
        try:
            await login_task
        except Exception:
            log.exception("Discord client shutdown error")


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
