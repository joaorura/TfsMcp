from mcp.server.fastmcp import FastMCP
import subprocess
import os

def encontrar_tf_exe() -> str:
    """
    Tenta localizar dinamicamente o executável tf.exe do Team Foundation Server.
    Cobre o utilitário vswhere e busca manual nas versões internas e comerciais.
    """
    # Método 1: Usar o utilitário oficial vswhere.exe
    caminho_vswhere = os.path.join(
        os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
        "Microsoft Visual Studio\\Installer\\vswhere.exe"
    )
    
    if os.path.exists(caminho_vswhere):
        try:
            result = subprocess.run(
                [caminho_vswhere, "-latest", "-property", "installationPath"],
                capture_output=True, text=True, check=True
            )
            base_path = result.stdout.strip()
            if base_path:
                tf_path = os.path.join(
                    base_path, 
                    "Common7", "IDE", "CommonExtensions", "Microsoft", "TeamFoundation", "Team Explorer", "tf.exe"
                )
                if os.path.exists(tf_path):
                    return tf_path
        except subprocess.CalledProcessError:
            pass 

    # Método 2: Varredura manual inteligente
    versoes_vs = ["2026", "18", "2022", "17", "2019", "16", "2017", "15"]
    edicoes_vs = ["Community", "Professional", "Enterprise", "BuildTools"]
    arquivos_de_programas = [
        os.environ.get('ProgramFiles', 'C:\\Program Files'), 
        os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
    ]

    for pf in arquivos_de_programas:
        for versao in versoes_vs:
            for edicao in edicoes_vs:
                caminho_tentativa = os.path.join(
                    pf, "Microsoft Visual Studio", versao, edicao,
                    "Common7", "IDE", "CommonExtensions", "Microsoft", "TeamFoundation", "Team Explorer", "tf.exe"
                )
                if os.path.exists(caminho_tentativa):
                    return caminho_tentativa

    # Fallback global caso esteja no PATH
    return "tf"

# Localiza o executável antes de subir o servidor
TF_CMD = encontrar_tf_exe()
print(f"Iniciando MCP com TFS localizado em: {TF_CMD}")

# Inicializa o servidor MCP
mcp = FastMCP("TFS_Tools")

def executar_tf(args: list) -> str:
    """Função auxiliar para executar comandos do TFS e capturar a saída."""
    comando = [TF_CMD] + args
    try:
        # A flag creationflags=subprocess.CREATE_NO_WINDOW pode ser útil no Windows 
        # para evitar popups rápidos de terminal, dependendo de como o Gemini chama o script.
        result = subprocess.run(
            comando, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return f"Sucesso!\nSaída: {result.stdout}"
    except subprocess.CalledProcessError as e:
        return f"Erro ao executar o TFS.\nCódigo: {e.returncode}\nErro: {e.stderr}\nSaída: {e.stdout}"

@mcp.tool()
def tfs_checkout(filepath: str) -> str:
    """
    Faz o checkout de um arquivo no TFS para permitir edição.
    Use ANTES de modificar arquivos de código (ex: D:\\TFS_DevOps\\SPF\\Controllers\\HomeController.cs).
    """
    if not os.path.exists(filepath):
        return f"Erro: O arquivo {filepath} não foi encontrado no disco."
    
    return executar_tf(["checkout", filepath])

@mcp.tool()
def tfs_undo(filepath: str) -> str:
    """
    Desfaz o checkout de um arquivo no TFS (Undo Pending Changes).
    Reverte o arquivo local para a versão do servidor, descartando edições feitas pela IA ou pelo usuário.
    """
    if not os.path.exists(filepath):
        return f"Erro: O arquivo {filepath} não foi encontrado."
        
    return executar_tf(["undo", filepath])

@mcp.tool()
def tfs_private_checkin(filepath: str, shelveset_name: str, preserve_local: bool = True) -> str:
    """
    Realiza um 'check-in privado' (Shelveset) no TFS.
    
    Args:
        filepath: Caminho do arquivo ou diretório.
        shelveset_name: Nome da 'prateleira' no servidor.
        preserve_local: Se True (padrão), mantém as edições no PC. 
                        Se False, move para o servidor e limpa o arquivo local (Undo).
    """
    args = ["shelve", "/replace", "/noprompt", shelveset_name, filepath]
    
    # Se o usuário NÃO quiser preservar localmente, adicionamos o /move
    if not preserve_local:
        args.append("/move")
        
    return executar_tf(args)

@mcp.tool()
def tfs_checkin(filepath: str, comment: str) -> str:
    """
    Realiza o Check-in definitivo de um arquivo no TFS.
    Envia as alterações para o repositório principal, tornando-as visíveis para a equipe.
    """
    return executar_tf(["checkin", filepath, f"/comment:{comment}", "/noprompt"])

if __name__ == "__main__":
    mcp.run()