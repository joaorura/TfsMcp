"""Monitor TF.exe windows to detect interactive authentication dialogs"""
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True)
class WindowMonitorResult:
    """Result of window monitoring operation"""

    had_interactive_window: bool
    window_closed: bool
    timeout_reached: bool


class TfWindowMonitor:
    """Monitor TF.exe process windows to detect authentication dialogs"""

    def __init__(self, check_interval_seconds: float = 0.5) -> None:
        self._check_interval = check_interval_seconds
        self._win32_available = False
        try:
            import win32gui  # noqa: F401
            import win32process  # noqa: F401

            self._win32_available = True
        except ImportError:
            pass

    def monitor_process_windows(
        self,
        pid: int,
        timeout_seconds: float,
        on_window_detected: Callable[[str], None] | None = None,
    ) -> WindowMonitorResult:
        """
        Monitor windows owned by the given process ID.

        If an interactive window is detected (e.g., login dialog), waits for it to close
        or until timeout is reached.

        Args:
            pid: Process ID to monitor
            timeout_seconds: Maximum time to wait
            on_window_detected: Optional callback when window is first detected

        Returns:
            WindowMonitorResult with monitoring outcome
        """
        if not self._win32_available:
            return WindowMonitorResult(
                had_interactive_window=False,
                window_closed=False,
                timeout_reached=False,
            )

        import win32gui
        import win32process

        start_time = time.monotonic()
        window_detected = False
        window_closed = False

        while (time.monotonic() - start_time) < timeout_seconds:
            windows = self._find_windows_by_pid(pid, win32gui, win32process)

            if windows and not window_detected:
                window_detected = True
                if on_window_detected:
                    titles = [title for _, title in windows]
                    on_window_detected(", ".join(titles))

            if window_detected and not windows:
                window_closed = True
                break

            time.sleep(self._check_interval)

        return WindowMonitorResult(
            had_interactive_window=window_detected,
            window_closed=window_closed,
            timeout_reached=(time.monotonic() - start_time) >= timeout_seconds,
        )

    @staticmethod
    def _find_windows_by_pid(pid: int, win32gui, win32process) -> list[tuple[int, str]]:
        """Find all visible windows owned by the given PID"""
        windows = []

        def enum_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if window_pid == pid:
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only track windows with titles
                    windows.append((hwnd, title))

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        return windows
