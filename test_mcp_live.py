"""Smoke test: lista tools e chama tfs_detect_project via MCP live."""
import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://localhost:39393/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()

            # 1. Listar tools
            resp = await s.list_tools()
            print(f"\n=== {len(resp.tools)} ferramentas registradas ===")
            for t in resp.tools:
                print(f"  - {t.name}")

            # 2. tfs_detect_project em diretório real
            result = await s.call_tool("tfs_detect_project", {"path": "D:/TFS_DevOps/SPF/develop/Fontes"})
            print(f"\n=== tfs_detect_project ===")
            for c in result.content:
                print(c.text if hasattr(c, "text") else c)

            # 3. tfs_status em diretório real
            result2 = await s.call_tool("tfs_status", {"path": "D:/TFS_DevOps/SPF/develop/Fontes"})
            print(f"\n=== tfs_status ===")
            for c in result2.content:
                print(c.text[:500] if hasattr(c, "text") else c)


anyio.run(main)
