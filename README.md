# TfsMcp

Local TFS MCP service for Windows development machines.

## Install dependencies

```bash
pip install -e .[dev]
```

## Run tests

```bash
python -m pytest -q
```

## Install the Windows Service

```bash
python -m tfsmcp.service install
python -m tfsmcp.service start
python -m tfsmcp.service status
```

## Remove the Windows Service

```bash
python -m tfsmcp.service stop
python -m tfsmcp.service uninstall
```

## Unauthorized recovery

If a TFS command returns an unauthorized error, the service runs every `*.ps1` script inside `C:\tfs_scripts` in alphabetical order and retries the original command once.

## Agent workflow

1. Detect the project with `tfs_detect_project`.
2. Get guidance with `tfs_onboard_project`.
3. Create isolated work with `tfs_session_create`.
4. Checkout files before editing.
5. Use shelvesets for checkpoints.

## Session APIs

MCP tools:
- `tfs_session_create(name, source_path, session_path)` creates a TFS-backed session workspace and stores an active session record.
- `tfs_session_list()` returns the stored session records.
- `tfs_session_suspend(name)` stores a suspended state and checkpoint name.
- `tfs_session_discard(name)` discards a session and deletes its workspace.
- `tfs_session_resume(name)` restores an existing session to active state.
- `tfs_session_promote(name, comment)` records a promoted state and stores the promote/checkpoint result.

HTTP endpoints:
- `POST /sessions`
- `GET /sessions`
- `POST /sessions/{name}/suspend`
- `DELETE /sessions/{name}`
- `POST /sessions/{name}/resume`
- `POST /sessions/{name}/promote`

Current real-workspace behavior:
- session creation runs `tf workspace /new`
- maps with `tf workfold /map`
- populates files with `tf get`

Still not implemented:
- full resume via real unshelve
- formal checkin-based promote flow
- advanced mapping validation and conflict recovery
