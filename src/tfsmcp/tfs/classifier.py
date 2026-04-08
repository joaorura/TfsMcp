from tfsmcp.contracts import CommandResult


class TfOutputClassifier:
    def classify(self, result: CommandResult) -> str:
        text = f"{result.stdout}\n{result.stderr}".lower()
        if result.exit_code == 0:
            return "success"
        unauthorized_tokens = [
            "unauthorized",
            "access is denied",
            "not authorized",
            "nao autorizado",
            "não autorizado",
            "acesso negado",
            "tf30063",
        ]
        if any(token in text for token in unauthorized_tokens):
            return "unauthorized"
        if "workspace" in text:
            return "workspace_error"
        if "mapping" in text:
            return "mapping_error"
        return "unknown_failure"
