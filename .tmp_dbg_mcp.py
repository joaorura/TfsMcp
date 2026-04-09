import anyio
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL='http://localhost:39393/mcp'

async def main():
    name='dbg-iso-' + __import__('uuid').uuid4().hex[:8]
    p=Path(r'D:/TFS/.tfs-sessions')/name
    async with streamablehttp_client(MCP_URL) as (r,w,_):
        async with ClientSession(r,w) as s:
            await s.initialize()
            for source in ['$/SPF/develop/Historico', '$/SPF/develop']:
                try:
                    res=await s.call_tool('tfs_session_create', {'name':name, 'source_path':source, 'session_path':str(p)})
                    print('create source',source,'=>',res)
                    print('exists',p.exists(),'txt',len(list(p.rglob('*.txt'))) if p.exists() else -1)
                except Exception as e:
                    print('create source',source,'error',e)
                try:
                    lr=await s.call_tool('tfs_session_list', {})
                    print('list',lr)
                except Exception as e:
                    print('list error',e)
                try:
                    dr=await s.call_tool('tfs_session_discard', {'name':name})
                    print('discard',dr)
                except Exception as e:
                    print('discard error',e)

anyio.run(main)
