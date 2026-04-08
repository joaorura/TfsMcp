from tfsmcp.runtime import RuntimeSessionActions


class FakeWorkspaceExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        return {"command": args}


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
        ["get", str(tmp_path / "agent-auth"), "/recursive"],
        ["shelve", "agent-auth"],
        ["workspace", "/delete", "agent-auth"],
    ]
