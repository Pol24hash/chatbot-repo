import os

EXCLUDED_DIRS = {"node_modules", ".git", ".vscode", ".venv"}

def list_dir_tree(root_dir, file_object, prefix=""):
    """Recursively writes the directory tree into a file."""
    try:
        entries = sorted(os.listdir(root_dir))
    except PermissionError:
        return  # skip directories that can't be accessed

    # Filter out excluded directories
    entries = [e for e in entries if e not in EXCLUDED_DIRS]
    entries_count = len(entries)

    for index, entry in enumerate(entries):
        path = os.path.join(root_dir, entry)
        is_last = index == entries_count - 1
        connector = "└── " if is_last else "├── "

        file_object.write(f"{prefix}{connector}{entry}\n")

        if os.path.isdir(path):
            new_prefix = prefix + ("    " if is_last else "│   ")
            list_dir_tree(path, file_object, new_prefix)

def save_directory_structure(root_dir, output_file="directory_structure.txt"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(os.path.basename(root_dir) + "\n")
        list_dir_tree(root_dir, f)
    print(f"✅ Directory structure saved to: {os.path.abspath(output_file)}")

# === Usage ===
root_directory = r"C:\Users\cdebe\Desktop\library-bot"
save_directory_structure(root_directory)