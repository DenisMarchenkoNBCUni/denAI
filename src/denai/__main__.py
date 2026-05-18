"""Allow running with `python -m denai`."""

from denai.app import main
import asyncio

asyncio.run(main())
