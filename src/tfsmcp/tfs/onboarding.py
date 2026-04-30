from tfsmcp.contracts import OnboardingAdvice


class TfsProjectOnboardingAdvisor:
    def __init__(self, detector) -> None:
        self._detector = detector

    def build(self, path: str, detection=None) -> OnboardingAdvice:
        if detection is None:
            detection = self._detector.detect(path)
        notes = [
                "Always checkout before editing controlled files.",
                "If unauthorized occurs, recovery scripts are executed automatically.",
                "Use hybrid sessions for agent isolation.",
                "Session creation maps workspace first; use perform_get=true only when you need immediate file materialization.",
                "Prefer tfs_session_materialize (or tfs_get_latest) as an explicit second step for large trees.",
                "For long-running setup, use tfs_session_create_async and poll with tfs_session_create_job_status.",
                "Simulated worktree uses TFVC workspace mapping and optional tf get, not a Git clone.",
                "Resume currently refreshes workspace files and does not perform full unshelve/conflict flow.",
                "Promote currently runs checkin scoped by workspace; advanced promotion policy flow is not implemented.",
            ]
        if detection.kind == "tfs_mapped" and detection.confidence == "medium":
            notes.insert(0, "TF30063 authorization error detected. The path appears to be TFS-mapped but server_path could not be retrieved. Ensure credentials are configured (PAT or recovery scripts) and retry tfs_detect_project / tfs_onboard_project.")
        return OnboardingAdvice(
            project_kind=detection.kind,
            confidence=detection.confidence,
            workspace={
                "name": detection.workspace_name,
                "serverPath": detection.server_path,
                "localPath": detection.local_path,
            },
            recommended_workflow={
                "beforeEdit": "checkout",
                "forParallelTask": "session_create_async",
                "forCheckpoint": "shelve",
                "forDiscard": "undo_or_session_discard",
                "forSessionMaterialization": "session_materialize",
            },
            supports={
                "basicTools": detection.kind == "tfs_mapped",
                "hybridSessions": detection.kind == "tfs_mapped",
                "unauthorizedRecovery": True,
            },
            notes=notes,
        )
