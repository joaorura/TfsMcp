import tkinter as tk
from tkinter import ttk, messagebox


def request_new_pat(current_pat: str | None = None, reason: str | None = None) -> str | None:
    """
    Shows a GUI dialog to request a new Personal Access Token (PAT).
    Returns the new PAT or None if cancelled.
    """
    root = tk.Tk()
    root.title("TFS PAT Required")
    root.attributes("-topmost", True)
    root.geometry("400x200")
    
    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    new_pat = tk.StringVar()
    if current_pat:
        new_pat.set(current_pat)

    label_text = "Seu PAT do TFS expirou ou é inválido.\nPor favor, insira um novo PAT para continuar."
    if reason:
        label_text = f"Erro de Autenticação: {reason}\n\n{label_text}"

    ttk.Label(root, text=label_text, wraplength=350, justify="center").pack(pady=10)
    
    entry = ttk.Entry(root, textvariable=new_pat, width=50, show="*")
    entry.pack(pady=5, padx=20)
    entry.focus_set()

    result = {"pat": None}

    def on_ok():
        pat = new_pat.get().strip()
        if not pat:
            messagebox.showwarning("Aviso", "O PAT não pode estar vazio.")
            return
        result["pat"] = pat
        root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side="left", padx=5)

    root.mainloop()
    return result["pat"]


def is_pat_valid(runner) -> bool:
    """
    Checks if the current PAT in the runner is valid by executing a simple command.
    """
    # Try a very lightweight command that requires authentication
    result = runner.run(["workspaces", "/noprompt", "/owner:*"])
    return result.exit_code == 0
