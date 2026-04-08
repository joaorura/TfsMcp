from tfsmcp.contracts import CommandResult


class TfOutputClassifier:
    def classify(self, result: CommandResult) -> str:
        text = f"{result.stdout}\n{result.stderr}".lower()
        if result.exit_code == 0:
            return "success"
        if "unauthorized" in text or "access is denied" in text or "not authorized" in text:
            return "unauthorized"
        if "workspace" in text:
            return "workspace_error"
        if "mapping" in text:
            return "mapping_error"
        return "unknown_failure"
