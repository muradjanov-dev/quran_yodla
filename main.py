"""Entry point — delegates to src/index.py."""
import asyncio
from src.index import main

if __name__ == "__main__":
    asyncio.run(main())
