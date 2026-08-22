# Mokasi — a modular personal Telegram bot framework
import asyncio
import logging

from . import main

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

asyncio.run(main.mokasi._main())
