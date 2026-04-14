import os
import subprocess
from pathlib import Path


class TfExeLocator:
    def locate(self) -> str:
        vswhere = Path(
            os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
        ) / "Microsoft Visual Studio/Installer/vswhere.exe"
        if vswhere.exists():
            result = subprocess.run(
                [str(vswhere), "-latest", "-property", "installationPath"],
                capture_output=True,
                text=True,
                check=False,
            )
            installation_path = result.stdout.strip()
            if installation_path:
                tf_path = (
                    Path(installation_path)
                    / "Common7/IDE/CommonExtensions/Microsoft/TeamFoundation/Team Explorer/tf.exe"
                )
                if tf_path.exists():
                    return str(tf_path)
        return "tf"
