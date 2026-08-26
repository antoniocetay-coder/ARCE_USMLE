import os
import zipfile

source_dir = r"C:\Users\UFMG\Downloads\ARCE"
target_zip = r"C:\Users\UFMG\Documents\ARCE.zip"

excluded_dirs = {".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".vscode"}
excluded_exts = {".pyc", ".pyo"}

count = 0
with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as ziph:
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            if any(file.endswith(ext) for ext in excluded_exts):
                continue
            if file == "ARCE.zip":
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, source_dir)
            ziph.write(file_path, arcname)
            count += 1

size_mb = os.path.getsize(target_zip) / (1024 * 1024)
print(f"ZIP criado com sucesso! {count} arquivos compactados ({size_mb:.2f} MB) em: {target_zip}")

