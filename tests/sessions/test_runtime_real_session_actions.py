from tfsmcp.runtime import RuntimeSessionActions


class FakeExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        class Result:
            exit_code = 0
            stdout = "ok"
            stderr = ""

        return Result()


def test_runtime_session_actions_creates_real_workspace_mapping_without_get_by_default(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    server_path = actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))

    assert server_path == "$/SPF/Main"
    assert executor.commands == [
        ["workspace", "/new", "agent-auth", "/location:server", "/noprompt"],
        ["workfold", "/map", "$/SPF/Main", str(tmp_path / "agent-auth"), "/workspace:agent-auth", "/noprompt"],
    ]


def test_runtime_session_actions_can_materialize_during_create(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"), perform_get=True)

    assert executor.commands == [
        ["workspace", "/new", "agent-auth", "/location:server", "/noprompt"],
        ["workfold", "/map", "$/SPF/Main", str(tmp_path / "agent-auth"), "/workspace:agent-auth", "/noprompt"],
        ["get", str(tmp_path / "agent-auth"), "/recursive", "/noprompt"],
    ]



def test_runtime_session_actions_resume_restores_workspace_contents(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    actions.resume_workspace("agent-auth", str(tmp_path / "agent-auth"))

    assert executor.commands == [
         ["get", str(tmp_path / "agent-auth"), "/recursive", "/noprompt"],
    ]



def test_runtime_session_actions_promote_uses_checkin_comment_and_workspace_fallback(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    promoted = actions.promote_workspace("agent-auth", None, str(tmp_path / "agent-auth"))

    assert promoted == "agent-auth"
    assert executor.commands == [
        ["checkin", "/comment:agent-auth", "/noprompt"],
    ]



def test_runtime_session_actions_promote_uses_supplied_comment(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    promoted = actions.promote_workspace("agent-auth", "ship it", str(tmp_path / "agent-auth"))

    assert promoted == "ship it"
    assert executor.commands == [
        ["checkin", "/comment:ship it", "/noprompt"],
    ]



def test_runtime_session_actions_resume_and_promote_methods_exist(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    actions.resume_workspace("agent-auth", str(tmp_path / "agent-auth"))
    actions.promote_workspace("agent-auth", "ship it", str(tmp_path / "agent-auth"))

    assert executor.commands == [
        ["get", str(tmp_path / "agent-auth"), "/recursive", "/noprompt"],
        ["checkin", "/comment:ship it", "/noprompt"],
    ]


def test_create_workspace_raises_clear_error_on_mapping_conflict(tmp_path):
    class MappingConflictExecutor:
        def __init__(self):
            self.commands = []
            self._call_count = 0

        def run(self, args):
            self.commands.append(args)
            self._call_count += 1

            class Result:
                pass

            result = Result()
            # workspace /new succeeds; workfold /map fails with a mapping conflict
            if "workfold" in args and "/map" in args:
                result.exit_code = 1
                result.stdout = ""
                result.stderr = "The working folder is already in use by the workspace 'other-ws'"
            else:
                result.exit_code = 0
                result.stdout = "ok"
                result.stderr = ""
            return result

    executor = MappingConflictExecutor()
    actions = RuntimeSessionActions(executor)

    try:
        actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "session_path" in str(exc)
        assert "already mapped" in str(exc) or "existing TFS workspace" in str(exc)
    # The failed workspace must be deleted automatically
    deleted = [cmd for cmd in executor.commands if "workspace" in cmd and "/delete" in cmd]
    assert deleted, "Workspace created before conflict should be deleted"
