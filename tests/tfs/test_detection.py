from tfsmcp.contracts import CommandResult
from tfsmcp.tfs.detector import TfsProjectDetector
from tfsmcp.tfs.onboarding import TfsProjectOnboardingAdvisor


class FakeExecutor:
    def __init__(self, *, exit_code=0, stdout=None, stderr=""):
        self.exit_code = exit_code
        self.stdout = stdout or (
            "Workspace: SPF_Joao\n"
            "Server path: $/SPF/Main\n"
            "Local path: D:/TFS/SPF"
        )
        self.stderr = stderr

    def run(self, args):
        return CommandResult(
            command=["tf", *args],
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
            category="success" if self.exit_code == 0 else "error",
        )


class FallbackExecutor:
    def run(self, args):
        if args[0] == "workfold":
            return CommandResult(
                command=["tf", *args],
                exit_code=1,
                stdout="",
                stderr="TF14061: Unable to connect",
                category="error",
            )
        return CommandResult(
            command=["tf", *args],
            exit_code=0,
            stdout=(
                "Informações locais:\n"
                "  Caminho local         : D:/TFVC_ROOT/SPF/develop/Historico/Changelog.txt\n"
                "  Caminho de servidor   : $/SPF/develop/Historico/Changelog.txt\n"
            ),
            stderr="",
            category="success",
        )


class ParentWorkfoldExecutor:
    def run(self, args):
        command = args[0]
        target = args[1].replace("\\", "/")
        if command == "workfold" and target.endswith("/Fontes"):
            return CommandResult(
                command=["tf", *args],
                exit_code=1,
                stdout="",
                stderr="The path is not mapped in workspace.",
                category="error",
            )
        if command == "workfold" and target.endswith("/develop-pgp-30745"):
            return CommandResult(
                command=["tf", *args],
                exit_code=0,
                stdout=(
                    "Workspace: SPF_Joao\n"
                    " $/SPF/develop-pgp-30745: D:/TFVC_ROOT/SPF/develop-pgp-30745"
                ),
                stderr="",
                category="success",
            )
        return CommandResult(
            command=["tf", *args],
            exit_code=1,
            stdout="",
            stderr="No mapping.",
            category="error",
        )


class InfoItemsExecutor:
    def run(self, args):
        if args[0] == "workfold":
            return CommandResult(
                command=["tf", *args],
                exit_code=1,
                stdout="",
                stderr="The path is not mapped in workspace.",
                category="error",
            )
        return CommandResult(
            command=["tf", *args],
            exit_code=0,
            stdout=(
                "Workspace: SPF_Joao\n"
                "Server item: $/SPF/develop-pgp-30745/Fontes\n"
                "Local item: D:/TFVC_ROOT/SPF/develop-pgp-30745/Fontes"
            ),
            stderr="",
            category="success",
        )


def test_detector_returns_high_confidence_mapping():
    detector = TfsProjectDetector(FakeExecutor())
    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "tfs_mapped"
    assert result.confidence == "high"
    assert result.workspace_name == "SPF_Joao"
    assert result.server_path == "$/SPF/Main"
    assert result.local_path == "D:/TFS/SPF"
    assert result.is_agent_ready is True


def test_detector_returns_not_tfs_when_workfold_command_fails():
    detector = TfsProjectDetector(
        FakeExecutor(exit_code=1, stdout="", stderr="TF14061: Unable to connect")
    )

    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "not_tfs"
    assert result.confidence == "high"
    assert result.workspace_name is None
    assert result.server_path is None
    assert result.local_path == "D:/TFS/SPF"
    assert result.is_agent_ready is False


def test_detector_returns_not_tfs_when_output_lacks_server_mapping():
    detector = TfsProjectDetector(
        FakeExecutor(stdout="Workspace: SPF_Joao\nLocal path: D:/TFS/SPF")
    )

    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "not_tfs"
    assert result.confidence == "high"
    assert result.workspace_name is None
    assert result.server_path is None
    assert result.local_path == "D:/TFS/SPF"
    assert result.is_agent_ready is False


def test_detector_uses_colon_parsed_values_with_input_path_fallback():
    detector = TfsProjectDetector(FakeExecutor(stdout="Server path: $/SPF/Main"))

    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "tfs_mapped"
    assert result.confidence == "high"
    assert result.workspace_name is None
    assert result.server_path == "$/SPF/Main"
    assert result.local_path == "D:/TFS/SPF"
    assert result.is_agent_ready is True


def test_detector_parses_localized_mapping_line():
    localized_output = (
        "===============================================================================\n"
        "Workspace: DEVBOX01 (User Example - ORG)\n"
        "Coleção  : https://dev.azure.com/example-org\n"
        " $/SPF/develop: D:/TFVC_ROOT/SPF/develop\n"
    )
    detector = TfsProjectDetector(FakeExecutor(stdout=localized_output))

    result = detector.detect("D:/TFVC_ROOT/SPF/develop")

    assert result.kind == "tfs_mapped"
    assert result.workspace_name == "DEVBOX01 (User Example - ORG)"
    assert result.server_path == "$/SPF/develop"
    assert result.local_path == "D:/TFVC_ROOT/SPF/develop"


def test_detector_uses_parent_directory_when_path_looks_like_file():
    detector = TfsProjectDetector(FakeExecutor())

    result = detector.detect("D:/TFS/SPF/Historico/Changelog.txt")

    assert result.kind == "tfs_mapped"


def test_detector_falls_back_to_info_when_workfold_fails():
    detector = TfsProjectDetector(FallbackExecutor())

    result = detector.detect("D:/TFVC_ROOT/SPF/develop/Historico/Changelog.txt")

    assert result.kind == "tfs_mapped"
    assert result.server_path == "$/SPF/develop/Historico/Changelog.txt"
    assert result.local_path == "D:/TFVC_ROOT/SPF/develop/Historico/Changelog.txt"


def test_detector_parses_mapping_from_stderr_stream():
    detector = TfsProjectDetector(
        FakeExecutor(
            stdout="",
            stderr="Workspace: SPF_Joao\n $/SPF/Main: D:/TFS/SPF",
        )
    )

    result = detector.detect("D:/TFS/SPF")

    assert result.kind == "tfs_mapped"
    assert result.server_path == "$/SPF/Main"
    assert result.local_path == "D:/TFS/SPF"


def test_detector_tries_parent_directories_for_workfold_mapping():
    detector = TfsProjectDetector(ParentWorkfoldExecutor())

    result = detector.detect("D:/TFVC_ROOT/SPF/develop-pgp-30745/Fontes")

    assert result.kind == "tfs_mapped"
    assert result.workspace_name == "SPF_Joao"
    assert result.server_path == "$/SPF/develop-pgp-30745"
    assert result.local_path == "D:/TFVC_ROOT/SPF/develop-pgp-30745"


def test_detector_parses_info_output_item_labels():
    detector = TfsProjectDetector(InfoItemsExecutor())

    result = detector.detect("D:/TFVC_ROOT/SPF/develop-pgp-30745/Fontes")

    assert result.kind == "tfs_mapped"
    assert result.workspace_name == "SPF_Joao"
    assert result.server_path == "$/SPF/develop-pgp-30745/Fontes"
    assert result.local_path == "D:/TFVC_ROOT/SPF/develop-pgp-30745/Fontes"


def test_onboarding_recommends_session_workflow():
    advisor = TfsProjectOnboardingAdvisor(TfsProjectDetector(FakeExecutor()))
    result = advisor.build("D:/TFS/SPF")

    assert result.recommended_workflow["beforeEdit"] == "checkout"
    assert result.recommended_workflow["forParallelTask"] == "session_create"
    assert result.supports["unauthorizedRecovery"] is True


def test_onboarding_keeps_task4_workflow_for_non_tfs_project():
    advisor = TfsProjectOnboardingAdvisor(
        TfsProjectDetector(FakeExecutor(stdout="The path is not mapped to any workspace."))
    )

    result = advisor.build("D:/Other")

    assert result.project_kind == "not_tfs"
    assert result.recommended_workflow["beforeEdit"] == "checkout"
    assert result.recommended_workflow["forParallelTask"] == "session_create"
    assert result.recommended_workflow["forCheckpoint"] == "shelve"
    assert result.recommended_workflow["forDiscard"] == "undo_or_session_discard"
    assert result.supports["basicTools"] is False
    assert result.supports["hybridSessions"] is False
    assert result.supports["unauthorizedRecovery"] is True
