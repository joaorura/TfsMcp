import tkinter as tk
from tkinter import ttk, messagebox


def request_auth_credentials(
    current_user: str | None = None,
    current_pat: str | None = None,
    reason: str | None = None
) -> tuple[str | None, str | None]:
    """
    Shows a GUI dialog to request TFS credentials (Username and PAT).
    Returns (user, pat) or (None, None) if cancelled.
    Returns ("SKIP", "SKIP") if the user marks they don't want to use PAT.
    """
    root = tk.Tk()
    root.title("TFS Authentication Required")
    root.attributes("-topmost", True)
    root.geometry("450x320")
    
    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    user_var = tk.StringVar(value=current_user or "PAT")
    pat_var = tk.StringVar(value=current_pat or "")
    skip_pat_var = tk.BooleanVar(value=False)

    label_text = "As credenciais do TFS são necessárias.\nPor favor, insira seu PAT ou marque para não usar."
    if reason:
        # Truncate reason if too long
        display_reason = str(reason)[:200] + "..." if len(str(reason)) > 200 else str(reason)
        label_text = f"Status Atual:\n{display_reason}\n\n{label_text}"

    ttk.Label(root, text=label_text, wraplength=400, justify="center").pack(pady=10)
    
    form_frame = ttk.Frame(root)
    form_frame.pack(pady=5, padx=20, fill="x")

    # User field
    user_label = ttk.Label(form_frame, text="Usuário (use 'PAT' para tokens do Azure DevOps):")
    user_label.pack(anchor="w")
    user_entry = ttk.Entry(form_frame, textvariable=user_var, width=50)
    user_entry.pack(pady=(0, 10), fill="x")

    # PAT field
    pat_label = ttk.Label(form_frame, text="Personal Access Token (PAT):")
    pat_label.pack(anchor="w")
    pat_entry = ttk.Entry(form_frame, textvariable=pat_var, width=50, show="*")
    pat_entry.pack(fill="x")

    def toggle_fields():
        state = "disabled" if skip_pat_var.get() else "normal"
        user_entry.config(state=state)
        pat_entry.config(state=state)
        user_label.config(state=state)
        pat_label.config(state=state)

    # Skip Checkbox
    ttk.Checkbutton(
        root, 
        text="Não usar PAT (usar apenas login via Scripts/Windows)", 
        variable=skip_pat_var,
        command=toggle_fields
    ).pack(pady=10)
    
    if not current_pat:
        pat_entry.focus_set()
    else:
        user_entry.focus_set()

    result = {"user": None, "pat": None}

    def on_ok():
        if skip_pat_var.get():
            result["user"] = "SKIP"
            result["pat"] = "SKIP"
            root.destroy()
            return

        user = user_var.get().strip()
        pat = pat_var.get().strip()
        if not user:
            messagebox.showwarning("Aviso", "O usuário não pode estar vazio.")
            return
        if not pat:
            messagebox.showwarning("Aviso", "O PAT não pode estar vazio.")
            return
        result["user"] = user
        result["pat"] = pat
        root.destroy()

    def on_cancel():
        root.destroy()

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side="left", padx=5)

    root.mainloop()
    return result["user"], result["pat"]


def request_new_pat(current_pat: str | None = None, reason: str | None = None) -> str | None:
    """
    Backward compatibility for requesting only PAT.
    """
    _, pat = request_auth_credentials(current_user=None, current_pat=current_pat, reason=reason)
    return pat


def is_pat_valid(runner) -> bool:
    """
    Checks if the current PAT in the runner is valid.
    In mandatory mode, if no PAT is present, it's considered invalid to force the dialog.
    """
    current_pat = getattr(runner, "_tfs_pat", None)
    if not current_pat:
        return False
        
    # Try a very lightweight command that requires authentication
    result = runner.run(["workspaces", "/noprompt", "/owner:*"])
    
    from tfsmcp.tfs.classifier import TfOutputClassifier
    classifier = TfOutputClassifier()
    category = classifier.classify(result)
    return category != "unauthorized"
