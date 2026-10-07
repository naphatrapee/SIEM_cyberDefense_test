"""Syslog listener (UDP + TCP) on 5514 inside the container (host maps 514 -> 5514).
Pipeline: receive -> queue -> batch (200 events or 1s) -> normalize -> enrich -> INSERT."""
import asyncio
import os

from app.db import insert_events
from ingest.enrich import enrich
from ingest.normalizers import normalize_syslog

PORT = 5514
TENANT = os.getenv("DEFAULT_TENANT", "demoA")
BATCH_SIZE, BATCH_SECONDS = 200, 1.0
queue: asyncio.Queue = asyncio.Queue()


class UDPHandler(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        queue.put_nowait(data.decode(errors="ignore").strip())


async def tcp_handler(reader, writer):
    while line := await reader.readline():
        queue.put_nowait(line.decode(errors="ignore").strip())
    writer.close()


def _process(lines: list[str]) -> int:
    events = [enrich(normalize_syslog(line, TENANT)) for line in lines if line]
    return insert_events(events)


async def batch_writer():
    while True:
        batch = [await queue.get()]
        deadline = asyncio.get_running_loop().time() + BATCH_SECONDS
        while len(batch) < BATCH_SIZE:
            timeout = deadline - asyncio.get_running_loop().time()
            if timeout <= 0:
                break
            try:
                batch.append(await asyncio.wait_for(queue.get(), timeout))
            except asyncio.TimeoutError:
                break
        try:
            n = await asyncio.to_thread(_process, batch)   # DB + DNS are blocking: keep the loop free
            print(f"stored {n} syslog events", flush=True)
        except Exception as exc:
            print(f"insert failed, {len(batch)} events dropped: {exc}", flush=True)


async def main():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(UDPHandler, local_addr=("0.0.0.0", PORT))
    await asyncio.start_server(tcp_handler, "0.0.0.0", PORT)
    print(f"syslog listening on {PORT} (udp+tcp)", flush=True)
    await batch_writer()


if __name__ == "__main__":
    asyncio.run(main())
