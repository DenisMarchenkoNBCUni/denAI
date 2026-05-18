"""Allow running with `python -m denai`."""

import asyncio

from denai.app import main

asyncio.run(main())
