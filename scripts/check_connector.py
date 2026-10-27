"""Read-only protocol smoke test against a running local TrendForge server."""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "trendforge.mcp_server"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"create_project", "save_brief", "save_edit_plan", "start_prepare", "get_job", "start_export"}.issubset(names)
            assert not any("approve" in n for n in names)
            response = await session.call_tool("trendforge_health", {})
            assert not response.isError
            print(f"MCP handshake passed; {len(names)} tools discovered; human approvals are not exposed.")
            print(response.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())

