# Tomer Heber's coding challenge 20 Oct 2021.

import asyncio
import argparse
import http.client
import json
import logging
import time

from abc import ABC, abstractmethod
from datetime import datetime

import httpx


class FailedToGetSessionCookie(Exception):
    pass


class FailedToPollEventStream(Exception):
    pass


class EventHandler(ABC):
    @abstractmethod
    async def handle_event(self, event: dict) -> None:
        pass


# This is a basic implementation of the event handler: prints the event.
class PrintEventHandler(EventHandler):
    async def handle_event(self, event: dict) -> None:
        print(f"dict {event} received on {datetime.utcnow()} (UTC)")


async def get_session_cookie(username: str, password: str, base_url: str,) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(f"https://data.{base_url}/sessions/", data={
            "username": username,
            "password": password,
        })
        if response.status_code != http.client.CREATED:
            raise FailedToGetSessionCookie(f"{response.status_code} {response.text}")
        session = response.cookies.get("session")
        if session is None:
            raise FailedToGetSessionCookie("session cookie not found in response")
        return session


async def poll_events(base_url: str, session: str, event_handler: EventHandler) -> None:
    cookies = {"session": session}
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", f"https://events.{base_url}/", cookies=cookies, timeout=None) as response:
            if response.status_code != http.client.OK:
                raise FailedToPollEventStream(f"{response.status_code}")
            async for line in response.aiter_lines():
                event = json.loads(line)
                await event_handler.handle_event(event)


async def follow_event_stream(
        username: str,
        password: str,
        base_url: str,
        event_handler: EventHandler
) -> None:
    session = await get_session_cookie(username, password, base_url)

    while True:
        try:
            await poll_events(base_url, session, event_handler)
        except Exception as e:
            logging.exception(e)
        finally:
            time.sleep(5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extracts Authentise events from the stream in an async manner.")
    parser.add_argument("--username", help="your authentise username", required=True)
    parser.add_argument("--password", help="your authentise password", required=True)
    parser.add_argument("--base_url", help="your authentise base url", default="dev-auth2.com")

    return parser.parse_args()


def main(username: str, password: str, base_url: str) -> None:
    asyncio.run(follow_event_stream(username, password, base_url, PrintEventHandler()))


if __name__ == '__main__':
    args = parse_args()
    main(args.username, args.password, args.base_url)
