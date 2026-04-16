"""
Teste de integração completo do fluxo TFS com recovery
Simula: detecção TFS → erro de autorização → recovery scripts → retry
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from tfsmcp.contracts import CommandResult
from tfsmcp.runtime import Runtime, RuntimeSessionActions
from tfsmcp.sessions.manager import SessionManager
from tfsmcp.sessions.store import SessionStore
from tfsmcp.tfs.classifier import TfOutputClassifier
from tfsmcp.tfs.detector import TfsProjectDetector
from tfsmcp.tfs.executor import RetryingTfsExecutor
from tfsmcp.tfs.recovery import UnauthorizedRecoveryManager


class SimulatedTfRunner:
    """Simula tf.exe com comportamento de autenticação"""
    
    def __init__(self):
        self.call_count = {}
        self.authenticated = False
        
    def run(self, args):
        """Simula execução de comandos TFS"""
        cmd = args[0] if args else "unknown"
        self.call_count[cmd] = self.call_count.get(cmd, 0) + 1
        
        # Simula que primeiro workfold/info falha sem autenticação
        if cmd in ["workfold", "info"]:
            if not self.authenticated:
                return CommandResult(
                    command=["tf.exe", *args],
                    exit_code=1,
                    stdout="",
                    stderr="TF30063: You are not authorized to access https://dev.azure.com/ED-ProjetoSoftware.",
                    category="raw",
                )
            else:
                # Após autenticação, retorna dados corretos
                if cmd == "workfold":
                    return CommandResult(
                        command=["tf.exe", *args],
                        exit_code=0,
                        stdout=(
                            "Workspace: TEST_WORKSPACE (Test User)\n"
                            "Collection: https://dev.azure.com/ED-ProjetoSoftware\n"
                            " $/SPF/develop-pgp-30745: D:\\TFS_DevOps\\SPF\\develop-pgp-30745"
                        ),
                        stderr="",
                        category="raw",
                    )
                else:  # info
                    return CommandResult(
                        command=["tf.exe", *args],
                        exit_code=0,
                        stdout=(
                            "Caminho local: D:\\TFS_DevOps\\SPF\\develop-pgp-30745\n"
                            "Caminho de servidor: $/SPF/develop-pgp-30745"
                        ),
                        stderr="",
                        category="raw",
                    )
        
        return CommandResult(
            command=["tf.exe", *args],
            exit_code=0,
            stdout="ok",
            stderr="",
            category="raw",
        )


def simulate_recovery_script(runner: SimulatedTfRunner):
    """Simula script de recovery que autentica o usuário"""
    def run_script(script_path):
        print(f"  → Executing recovery script: {script_path.name}")
        print("  → Opening authentication dialog... (simulated)")
        print("  → User authenticated successfully (simulated)")
        
        # Marca como autenticado após recovery
        runner.authenticated = True
        return 0
    
    return run_script


def test_full_recovery_flow():
    """Teste completo: TFS path → erro auth → recovery → sucesso"""
    
    print("=" * 70)
    print("TESTE: Fluxo completo de detecção TFS com recovery")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        
        # Setup: criar scripts de recovery
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "permissao_edengenharia.ps1").write_text(
            "# Simulated auth script\nWrite-Host 'Authenticating...'"
        )
        
        # Criar runner simulado
        runner = SimulatedTfRunner()
        
        # Criar recovery manager
        recovery = UnauthorizedRecoveryManager(
            scripts_dir=scripts_dir,
            run_script=simulate_recovery_script(runner),
            cooldown_seconds=0,  # Sem cooldown para teste
        )
        
        # Criar executor com retry
        classifier = TfOutputClassifier()
        executor = RetryingTfsExecutor(runner, classifier, recovery, max_retries=1)
        
        # Criar detector
        detector = TfsProjectDetector(executor)
        
        print("\n[STEP 1] Tentando detectar path TFS (sem autenticação)")
        print(f"Path: D:\\TFS_DevOps\\SPF\\develop-pgp-30745")
        
        result = detector.detect("D:\\TFS_DevOps\\SPF\\develop-pgp-30745")
        
        print(f"\n[RESULTADO]")
        print(f"  Kind: {result.kind}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Workspace: {result.workspace_name}")
        print(f"  Server Path: {result.server_path}")
        print(f"  Local Path: {result.local_path}")
        print(f"  Agent Ready: {result.is_agent_ready}")
        
        print(f"\n[ESTATÍSTICAS]")
        print(f"  Comandos executados: {runner.call_count}")
        print(f"  Autenticado: {runner.authenticated}")
        
        # Validações
        assert result.kind == "tfs_mapped", f"Expected tfs_mapped, got {result.kind}"
        assert result.server_path == "$/SPF/develop-pgp-30745", f"Wrong server path: {result.server_path}"
        assert runner.authenticated, "User should be authenticated after recovery"
        assert runner.call_count.get("workfold", 0) >= 2, "Should retry workfold after recovery"
        
        print("\n✓ Teste passou! Fluxo de recovery funcionou corretamente.")
        print("  1. Primeira tentativa falhou (TF30063)")
        print("  2. Recovery scripts executados")
        print("  3. Usuário autenticado")
        print("  4. Retry bem-sucedido")
        print("  5. Path TFS detectado corretamente")
        
        return True


if __name__ == "__main__":
    try:
        test_full_recovery_flow()
        print("\n" + "=" * 70)
        print("✓ SUCESSO: Todas as validações passaram!")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ FALHA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
