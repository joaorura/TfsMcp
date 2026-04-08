import subprocess


class ServiceInstaller:
    def __init__(self, run_command, service_name: str, display_name: str) -> None:
        self._run_command = run_command
        self._service_name = service_name
        self._display_name = display_name

    def install(self, executable: str, arguments: str) -> int:
        return self._run_command([
            "sc",
            "create",
            self._service_name,
            "binPath=",
            f"{executable} {arguments}",
            "DisplayName=",
            self._display_name,
            "start=",
            "auto",
        ])

    def uninstall(self) -> int:
        return self._run_command(["sc", "delete", self._service_name])

    def start(self) -> int:
        return self._run_command(["sc", "start", self._service_name])

    def stop(self) -> int:
        return self._run_command(["sc", "stop", self._service_name])

    def restart(self) -> int:
        self.stop()
        return self.start()

    def status(self) -> int:
        return self._run_command(["sc", "query", self._service_name])


def default_runner(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode
