from tfsmcp.contracts import CommandResult


class TfOutputClassifier:
    def classify(self, result: CommandResult) -> str:
        text = f"{result.stdout}\n{result.stderr}".lower()
        if result.exit_code == 0:
            return "success"
        unauthorized_tokens = [
            "tf30063",
            "not authorized to access",
            "você não está autorizado a acessar",
            "voce nao esta autorizado a acessar",
        ]
        if any(token in text for token in unauthorized_tokens):
            return "unauthorized"
        if "workspace" in text:
            return "workspace_error"
        if "mapping" in text:
            return "mapping_error"
        return "unknown_failure"
