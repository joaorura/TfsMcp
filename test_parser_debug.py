#!/usr/bin/env python3
"""Debug script to test TFS output parsing"""

import re
import unicodedata


def normalize_key(key: str) -> str:
    normalized = unicodedata.normalize("NFKD", key)
    without_diacritics = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(without_diacritics.lower().split())


def parse_detection_output(stdout: str, fallback_local_path: str) -> tuple[str | None, str | None, str]:
    values = {}
    mapping_server_path = None
    mapping_local_path = None

    print("=== Parsing Output ===")
    for line in stdout.splitlines():
        print(f"Line: {repr(line)}")
        
        mapping_match = re.search(r"(\$/[^:]+):\s*(.+)$", line)
        if mapping_match:
            mapping_server_path = mapping_match.group(1).strip()
            mapping_local_path = mapping_match.group(2).strip()
            print(f"  -> Mapping found: {mapping_server_path} -> {mapping_local_path}")
            continue
        
        if ":" in line:
            key, value = line.split(":", 1)
            normalized_key = normalize_key(key)
            values[normalized_key] = value.strip()
            print(f"  -> Key-value: {repr(key)} -> {repr(normalized_key)} = {repr(value.strip())}")

    print("\n=== Extracted Values ===")
    for k, v in values.items():
        print(f"  {repr(k)}: {repr(v)}")

    workspace_name = (
        values.get("workspace")
        or values.get("area de trabalho")
        or values.get("espaco de trabalho")
    )
    server_path = (
        mapping_server_path
        or values.get("server path")
        or values.get("server item")
        or values.get("caminho de servidor")
        or values.get("caminho do servidor")
        or values.get("item do servidor")
    )
    local_path = (
        mapping_local_path
        or values.get("local path")
        or values.get("local item")
        or values.get("caminho local")
        or values.get("item local")
        or fallback_local_path
    )
    
    print("\n=== Final Result ===")
    print(f"Workspace: {workspace_name}")
    print(f"Server Path: {server_path}")
    print(f"Local Path: {local_path}")
    
    return workspace_name, server_path, local_path


# Test with workfold output
workfold_output = """===============================================================================
Workspace: JOAOMESSIASNOTE (João Messias Lima Pereira - UFAL)
Coleção  : https://dev.azure.com/ED-ProjetoSoftware
 $/SPF/develop-pgp-30745: D:\\TFS_DevOps\\SPF\\develop-pgp-30745"""

print("### Testing tf workfold output ###\n")
parse_detection_output(workfold_output, "D:\\TFS_DevOps\\SPF\\develop-pgp-30745")

# Test with info output
info_output = """Informações locais:
  Caminho local         : D:\\TFS_DevOps\\SPF\\develop-pgp-30745
  Caminho de servidor   : $/SPF/develop-pgp-30745
  Conjunto de alterações: 20314
  Alterar               : nenhum
  Tipo                  : pasta
Informações do servidor:
  Caminho de servidor       : $/SPF/develop-pgp-30745
  Conjunto de alterações    : 20314
  ID da Exclusão            : 0
  Bloquear                  : nenhum
  Bloquear proprietário     : 
  Modificado pela última vez: quinta-feira, 19 de março de 2026 12:05:55
  Tipo                      : pasta"""

print("\n\n### Testing tf info output ###\n")
parse_detection_output(info_output, "D:\\TFS_DevOps\\SPF\\develop-pgp-30745")
