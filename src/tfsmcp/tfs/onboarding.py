from tfsmcp.contracts import OnboardingAdvice


class TfsProjectOnboardingAdvisor:
    def __init__(self, detector) -> None:
        self._detector = detector

    def build(self, path: str) -> OnboardingAdvice:
        detection = self._detector.detect(path)
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
                "forParallelTask": "session_create",
                "forCheckpoint": "shelve",
                "forDiscard": "undo_or_session_discard",
            },
            supports={
                "basicTools": detection.kind == "tfs_mapped",
                "hybridSessions": detection.kind == "tfs_mapped",
                "unauthorizedRecovery": True,
            },
            notes=[
                "Always checkout before editing controlled files.",
                "If unauthorized occurs, recovery scripts are executed automatically.",
                "Use hybrid sessions for agent isolation.",
            ],
        )
