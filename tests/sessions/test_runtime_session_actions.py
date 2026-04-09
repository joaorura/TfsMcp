from tfsmcp.runtime import RuntimeSessionActions


class FakeWorkspaceExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        class Result:
            exit_code = 0
            stderr = ""
            stdout = ""

        return Result()


class FailingWorkspaceExecutor:
    def __init__(self, fail_on_first: bool = True):
        self.commands = []
        self.fail_on_first = fail_on_first

    def run(self, args):
        self.commands.append(args)
        if self.fail_on_first and len(self.commands) == 1:
            class Result:
                exit_code = 1
                stderr = "simulated tf error"
                stdout = ""

            return Result()

        class Result:
            exit_code = 0
            stderr = ""
            stdout = ""

        return Result()


def test_runtime_session_actions_uses_executor_for_create_suspend_discard(tmp_path):
    executor = FakeWorkspaceExecutor()
    actions = RuntimeSessionActions(executor)

    server_path = actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))
    shelveset = actions.create_shelveset("agent-auth")
    actions.remove_workspace("agent-auth")

    assert server_path == "$/SPF/Main"
    assert shelveset == "agent-auth"
    assert executor.commands == [
        ["workspace", "/new", "agent-auth"],
        ["workfold", "/map", "$/SPF/Main", str(tmp_path / "agent-auth"), "/workspace:agent-auth"],
        ["get", "$/SPF/Main", "/recursive", "/workspace:agent-auth"],
        ["shelve", "agent-auth"],
        ["workspace", "/delete", "agent-auth"],
    ]


def test_runtime_session_actions_raises_when_tf_command_fails(tmp_path):
    executor = FailingWorkspaceExecutor()
    actions = RuntimeSessionActions(executor)

    try:
        actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "simulated tf error" in str(exc)
