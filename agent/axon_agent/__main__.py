"""Entry point: `python -m axon_agent`."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from .client import Agent, AgentConfig


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        cfg = AgentConfig.from_env()
    except RuntimeError as e:
        print(f"axon-agent: {e}", file=sys.stderr)
        return 2

    agent = Agent(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(*_a):
        agent.stop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _shutdown)
    else:
        signal.signal(signal.SIGINT, lambda *_: _shutdown())
        signal.signal(signal.SIGTERM, lambda *_: _shutdown())

    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
