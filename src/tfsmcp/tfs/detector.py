from tfsmcp.contracts import ProjectDetection


class TfsProjectDetector:
    def __init__(self, executor) -> None:
        self._executor = executor

    def detect(self, path: str) -> ProjectDetection:
        result = self._executor.run(["workfold", path])
        stdout = result.stdout or ""

        if result.exit_code != 0 or "$/" not in stdout:
            return ProjectDetection("not_tfs", "high", None, None, path, False)

        values = {}
        for line in stdout.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip().lower()] = value.strip()

        return ProjectDetection(
            kind="tfs_mapped",
            confidence="high",
            workspace_name=values.get("workspace"),
            server_path=values.get("server path"),
            local_path=values.get("local path", path),
            is_agent_ready=True,
        )
