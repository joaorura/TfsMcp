# TfsMcp

Local TFS MCP service for Windows development machines.

[![CI](https://github.com/joaorura/TfsMcp/actions/workflows/ci.yml/badge.svg)](https://github.com/joaorura/TfsMcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Public Repository Setup

This repository is prepared for public collaboration with:

- CI workflow (`.github/workflows/ci.yml`)
- Dependabot updates (`.github/dependabot.yml`)
- Issue templates (`.github/ISSUE_TEMPLATE/*`)
- Pull request template (`.github/PULL_REQUEST_TEMPLATE.md`)
- Governance docs (`LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`)

GitHub About recommendations:

- Description: `Local TFVC MCP server for Windows automation workflows`
- Website: repository URL or project docs URL
- Topics: `mcp`, `tfvc`, `tfs`, `windows`, `python`, `automation`

## Scope

- Target platform: Windows (TFVC + `tf.exe` + PowerShell scripts).
- Transport: MCP Streamable HTTP (`/mcp`).
- This project is designed for TFVC-style agent workflows (sessions, shelvesets, check-in flow).

## Install dependencies

```bash
pip install -e .[dev]
```

## PowerShell setup (Conda)

Default scripts are in `scripts/` and use the Conda env `mcp_tfs_env`.

Create/update env and install all dependencies:

```powershell
.\scripts\Install-TfsMcp.ps1
```

Create/update env, install dependencies, install service and start it:

```powershell
.\scripts\Install-TfsMcp.ps1 -InstallWindowsService -StartWindowsService
```

Run MCP in console/script mode:

```powershell
.\scripts\Manage-TfsMcp.ps1 -Command run
```

Manage Windows service:

```powershell
.\scripts\Manage-TfsMcp.ps1 -Command service-install
.\scripts\Manage-TfsMcp.ps1 -Command service-start
.\scripts\Manage-TfsMcp.ps1 -Command service-status
.\scripts\Manage-TfsMcp.ps1 -Command service-stop
.\scripts\Manage-TfsMcp.ps1 -Command service-uninstall
```

Run in user background mode (no Windows service):

```powershell
.\scripts\Manage-TfsMcp.ps1 -Command background-start
.\scripts\Manage-TfsMcp.ps1 -Command background-status
.\scripts\Manage-TfsMcp.ps1 -Command background-stop
```

Enable auto-start at user logon (Startup folder shortcut):

```powershell
.\scripts\Manage-TfsMcp.ps1 -Command startup-enable
.\scripts\Manage-TfsMcp.ps1 -Command startup-status
.\scripts\Manage-TfsMcp.ps1 -Command startup-disable
```

One-shot setup for Conda + Startup shortcut:

```powershell
.\scripts\Setup-TfsMcpStartup.ps1
```

One-shot setup and start MCP in background now:

```powershell
.\scripts\Setup-TfsMcpStartup.ps1 -StartBackgroundNow
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

## Unauthorized recovery and PAT Management

If a TFS command returns an unauthorized error, the service follows two recovery paths:

1. **GUI Dialog (PAT/User)**: If the runner has a PAT configured (via `TFSMCP_TFS_PAT`), the service shows an interactive GUI dialog asking for both **Username** and **PAT**. 
   - Use `PAT` as the username for Azure DevOps Services tokens.
   - For on-premise TFS, enter your actual username and token.
   - The original command is retried once with the new credentials.
2. **Legacy Scripts**: If the above is skipped or fails, the service runs every `*.ps1` script inside `C:\tfs_scripts` in alphabetical order and retries the original command once.

*Note: GUI dialogs and interactive scripts only work when running in user background mode, not as a Windows Service.*

## Agent workflow

1. Detect the project with `tfs_detect_project`.
2. Get guidance with `tfs_onboard_project`.
3. Create isolated work with `tfs_session_create`.
4. Materialize files when needed with `tfs_session_materialize` (or set `perform_get=true` on create).
5. Checkout files before editing.
6. Use shelvesets for checkpoints.

## Onboarding and simulated worktree

This MCP does not clone a Git worktree. It creates a TFVC workspace/session pair that behaves like an isolated worktree for agents.

Direct onboarding flow:

1. Call `tfs_detect_project(path)`.
2. If `kind == tfs_mapped`, call `tfs_onboard_project(path)` and follow `recommended_workflow`.
3. Create an isolated session with `tfs_session_create(name, source_path, session_path)`.
4. For long-running setups, prefer `tfs_session_create_async(...)` and poll `tfs_session_create_job_status(job_id)`.
5. Materialize session content explicitly with `tfs_session_materialize(name=...)` when needed.
6. Perform edits only after `tfs_checkout(file)`.
7. Use `tfs_session_suspend(name)` to checkpoint using shelveset.
8. Use `tfs_session_resume(name)` to reactivate suspended session.
9. Use `tfs_session_promote(name, comment)` when ready to promote.
10. Use `tfs_session_discard(name)` to remove workspace and mark session discarded.

How TFVC is used under the hood in simulated worktree mode:

1. `tfs_session_create` runs `tf workspace /new <name>`.
2. It maps server path to local session path using `tf workfold /map`.
3. It optionally materializes files with `tf get <session_path> /recursive` when `perform_get=true` or when env `TFSMCP_SESSION_CREATE_AUTO_GET=true`.
4. `tfs_session_materialize` can run `tf get` later as a separate step.
5. `tfs_session_suspend` creates a shelveset (currently named with workspace/session name).
6. `tfs_session_resume` currently runs a `tf get` refresh in that workspace.
7. `tfs_session_promote` currently performs `tf checkin` scoped by workspace.
8. `tfs_session_discard` deletes workspace via `tf workspace /delete`.

Unauthorized recovery behavior:

1. On unauthorized failures, scripts in `C:\tfs_scripts` are executed in alphabetical order.
2. After scripts complete successfully, the original TF command is retried once.
3. This retry path is intended for interactive re-auth scripts when running in user/background mode.

Current limitations of simulated worktree mode:

1. Resume does not perform real unshelve conflict resolution yet; it is currently a workspace refresh (`tf get`).
2. Promote uses direct workspace checkin and not a full policy-rich promotion flow.
3. Mapping validation/conflict recovery is basic and not yet exhaustive.
4. Session state is local JSON state and not a distributed lock/coordination mechanism.
5. Windows Service mode cannot open interactive auth UI; for interactive auth use background/user mode.

## Session APIs

MCP transport:
- Streamable HTTP endpoint: `http://127.0.0.1:39393/mcp`

This service is MCP-only now. Legacy REST endpoints (`/health`, `/checkout`, `/sessions`, etc.) are intentionally not exposed.

MCP tools:
- `tfs_detect_project(path)` detects if path is TFVC-mapped and returns mapping metadata.
- `tfs_onboard_project(path)` returns recommended TFVC workflow guidance.
- `tfs_checkout(filepath)` checks out an existing file in TFVC.
- `tfs_add(filepath, recursive=false)` adds a new file/folder to source control.
- `tfs_undo(filepath)` undoes pending changes for a file/path.
- `tfs_status(path, recursive=true, workspace=null)` returns pending changes/status.
- `tfs_get_latest(path, recursive=true, workspace=null)` runs `tf get` to sync latest.
- `tfs_shelveset_list(owner=null, name_pattern=null)` lists available shelvesets.
- `tfs_unshelve(name, workspace=null)` applies a shelveset into a workspace.
- `tfs_session_create(name, source_path, session_path, perform_get=false)` creates a TFS-backed session workspace and stores an active session record.
- `tfs_session_create_from_path(name, source_path, session_path, perform_get=false)` auto-resolves local path to server path before creating session.
- `tfs_session_create_async(name, source_path, session_path, perform_get=false)` starts session creation in background and returns a `job_id`.
- `tfs_session_create_from_path_async(name, source_path, session_path, perform_get=false)` async version with auto server-path resolution.
- `tfs_session_create_job_status(job_id)` returns queued/running/completed/failed status for session creation job.
- `tfs_session_materialize(name=null, session_path=null, recursive=true)` runs explicit `tf get` for a session path.
- `tfs_session_list()` returns the stored session records.
- `tfs_session_validate(name=null, path=null)` diagnoses mapping/status for a session or path.
- `tfs_session_suspend(name)` stores a suspended state and checkpoint name.
- `tfs_session_discard(name)` discards a session and deletes its workspace.
- `tfs_session_resume(name)` restores an existing session to active state.
- `tfs_session_promote(name, comment)` records a promoted state and stores the promote/checkpoint result.
- `tfs_checkin_preview(path=null, workspace=null, recursive=true)` previews pending check-in items.
- `tfs_history(path, stop_after=null, recursive=false)` returns TFVC history output.
- `tfs_diff(path, recursive=false, workspace=null)` returns TFVC diff output.

Current real-workspace behavior:
- session creation runs `tf workspace /new`
- maps with `tf workfold /map`
- skips `tf get` by default (fast path)
- can populate files with `tfs_session_materialize(...)` or `perform_get=true`

Still not implemented:
- full resume via real unshelve
- formal checkin-based promote flow
- advanced mapping validation and conflict recovery
