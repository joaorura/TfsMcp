import os
import re

from tfsmcp.contracts import ProjectDetection


class TfsProjectDetector:
    def __init__(self, executor) -> None:
        self._executor = executor

    def detect(self, path: str) -> ProjectDetection:
        candidate_path = os.path.dirname(path) if os.path.splitext(path)[1] else path
        result = self._executor.run(["workfold", candidate_path])
        workspace_name, server_path, local_path = self._parse_detection_output(
            self._combined_output(result),
            fallback_local_path=candidate_path,
        )

        if result.exit_code == 0 and server_path:
            return ProjectDetection("tfs_mapped", "high", workspace_name, server_path, local_path, True)

        info_result = self._executor.run(["info", path])
        _, info_server_path, info_local_path = self._parse_detection_output(
            self._combined_output(info_result),
            fallback_local_path=path,
        )
        if info_result.exit_code == 0 and info_server_path:
            return ProjectDetection(
                "tfs_mapped",
                "high",
                workspace_name,
                info_server_path,
                info_local_path,
                True,
            )

        return ProjectDetection("not_tfs", "high", None, None, path, False)

    @staticmethod
    def _parse_detection_output(stdout: str, fallback_local_path: str) -> tuple[str | None, str | None, str]:
        values = {}
        mapping_server_path = None
        mapping_local_path = None

        for line in stdout.splitlines():
            mapping_match = re.match(r"^\s*(\$/[^:]+):\s*(.+)$", line.strip())
            if mapping_match:
                mapping_server_path = mapping_match.group(1).strip()
                mapping_local_path = mapping_match.group(2).strip()
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip().lower()] = value.strip()

        workspace_name = values.get("workspace")
        server_path = mapping_server_path or values.get("server path") or values.get("caminho de servidor") or values.get("caminho do servidor")
        local_path = mapping_local_path or values.get("local path") or values.get("caminho local") or fallback_local_path
        return workspace_name, server_path, local_path

    @staticmethod
    def _combined_output(result) -> str:
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return f"{stdout}\n{stderr}".strip()
