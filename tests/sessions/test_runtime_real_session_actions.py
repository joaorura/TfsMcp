from tfsmcp.runtime import RuntimeSessionActions


class FakeExecutor:
    def __init__(self):
        self.commands = []

    def run(self, args):
        self.commands.append(args)
        return {"command": args, "stdout": "ok", "stderr": "", "exit_code": 0}


def test_runtime_session_actions_creates_real_workspace_mapping_and_get(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    server_path = actions.create_workspace("agent-auth", "$/SPF/Main", str(tmp_path / "agent-auth"))

    assert server_path == "$/SPF/Main"
    assert executor.commands == [
        ["workspace", "/new", "agent-auth"],
        ["workfold", "/map", "$/SPF/Main", str(tmp_path / "agent-auth"), "/workspace:agent-auth"],
        ["get", "$/SPF/Main", "/recursive", "/workspace:agent-auth"],
    ]



def test_runtime_session_actions_resume_restores_workspace_contents(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    actions.resume_workspace("agent-auth", str(tmp_path / "agent-auth"))

    assert executor.commands == [
        ["get", str(tmp_path / "agent-auth"), "/recursive", "/workspace:agent-auth"],
    ]



def test_runtime_session_actions_promote_uses_checkin_comment_and_workspace_fallback():
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    promoted = actions.promote_workspace("agent-auth", None)

    assert promoted == "agent-auth"
    assert executor.commands == [
        ["checkin", "/comment:agent-auth", "/workspace:agent-auth"],
    ]



def test_runtime_session_actions_promote_uses_supplied_comment():
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    promoted = actions.promote_workspace("agent-auth", "ship it")

    assert promoted == "ship it"
    assert executor.commands == [
        ["checkin", "/comment:ship it", "/workspace:agent-auth"],
    ]



def test_runtime_session_actions_resume_and_promote_methods_exist(tmp_path):
    executor = FakeExecutor()
    actions = RuntimeSessionActions(executor)

    actions.resume_workspace("agent-auth", str(tmp_path / "agent-auth"))
    actions.promote_workspace("agent-auth", "ship it")

    assert executor.commands == [
        ["get", str(tmp_path / "agent-auth"), "/recursive", "/workspace:agent-auth"],
        ["checkin", "/comment:ship it", "/workspace:agent-auth"],
    ]
