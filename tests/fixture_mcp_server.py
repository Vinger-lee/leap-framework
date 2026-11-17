"""Run the real MCP stdio server inside a synthetic integration fixture."""
from functools import partial

from leap import server


if __name__ == "__main__":
    server.build_service = partial(server.build_service, strict_grounding=False)
    server.main()
