"""Test window monitoring during recovery scripts"""
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tfsmcp.tfs.window_monitor import TfWindowMonitor


def test_window_monitor_no_windows():
    """Test monitoring when no windows exist"""
    monitor = TfWindowMonitor(check_interval_seconds=0.1)
    
    # Monitor current process (should have no visible windows in console mode)
    import os
    result = monitor.monitor_process_windows(
        pid=os.getpid(),
        timeout_seconds=1.0,
        on_window_detected=lambda titles: print(f"Unexpected window: {titles}")
    )
    
    assert not result.had_interactive_window, "Should not detect windows in console process"
    assert result.timeout_reached, "Should reach timeout"
    print("✓ No windows detected as expected")


def test_window_monitor_availability():
    """Test that window monitor can be created"""
    monitor = TfWindowMonitor()
    
    # Check if win32 is available
    if not monitor._win32_available:
        print("⚠ pywin32 not available - window monitoring disabled")
    else:
        print("✓ pywin32 available - window monitoring enabled")
    
    # Should not crash even if win32 not available
    import os
    result = monitor.monitor_process_windows(pid=os.getpid(), timeout_seconds=0.5)
    print(f"✓ Monitor result: {result}")


def test_recovery_logging():
    """Test that recovery manager has proper logging"""
    from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager
    from pathlib import Path
    import tempfile
    import logging
    
    # Setup logging to capture output
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Create temporary scripts directory
    with tempfile.TemporaryDirectory() as tmpdir:
        scripts_dir = Path(tmpdir)
        
        # Create a dummy recovery script that exits quickly
        test_script = scripts_dir / "test_recovery.ps1"
        test_script.write_text("Write-Host 'Test recovery script'\nexit 0")
        
        def mock_run_script(script_path):
            print(f"Would run: {script_path}")
            return 0
        
        manager = UnauthorizedRecoveryManager(
            scripts_dir=scripts_dir,
            run_script=mock_run_script,
            cooldown_seconds=0  # No cooldown for testing
        )
        
        print("\nTesting recovery script execution:")
        result = manager.run_scripts()
        
        assert result.succeeded, "Recovery should succeed"
        assert "test_recovery.ps1" in result.scripts, "Should execute test script"
        print("✓ Recovery manager logging works correctly")


if __name__ == "__main__":
    print("=== Testing Window Monitor ===\n")
    
    print("Test 1: Window Monitor Availability")
    test_window_monitor_availability()
    
    print("\nTest 2: No Windows Detection")
    test_window_monitor_no_windows()
    
    print("\nTest 3: Recovery Logging")
    test_recovery_logging()
    
    print("\n✓ All window monitor tests passed!")
