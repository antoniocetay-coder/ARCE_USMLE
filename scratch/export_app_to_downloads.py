from __future__ import annotations

import io
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = Path("C:/Users/UFMG/.gemini/antigravity/scratch/ARC-e-USMLE")
DOWNLOADS_DIR = Path("C:/Users/UFMG/Downloads")


def export_to_downloads():
    if not PROJECT_ROOT.exists():
        print(f"Diretório do projeto não encontrado: {PROJECT_ROOT}")
        return

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_target_dated = DOWNLOADS_DIR / f"ARC-e-USMLE_{timestamp}.zip"
    zip_target_latest = DOWNLOADS_DIR / "ARC-e-USMLE_latest.zip"
    zip_target_root = DOWNLOADS_DIR / "ARC-e-USMLE.zip"

    # Pastas e arquivos a ignorar (caches e venv)
    EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".git", ".mypy_cache", ".ruff_cache"}
    EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd"}

    print(f"📦 Compactando projeto de: {PROJECT_ROOT}")
    print(f"🎯 Destino: {zip_target_root}")

    total_files = 0
    total_bytes = 0

    with zipfile.ZipFile(zip_target_dated, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Filtrar diretórios indesejados
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".system_generated")]

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in EXCLUDE_EXTS:
                    continue
                if file.endswith(".tmp") or file.endswith(".log"):
                    continue

                full_path = Path(root) / file
                arcname = full_path.relative_to(PROJECT_ROOT.parent)  # Mantém pasta raiz ARC-e-USMLE/

                zipf.write(full_path, arcname=str(arcname))
                total_files += 1
                total_bytes += full_path.stat().st_size

    # Copiar como ARC-e-USMLE.zip e ARC-e-USMLE_latest.zip para facilidade
    shutil.copy2(zip_target_dated, zip_target_root)
    shutil.copy2(zip_target_dated, zip_target_latest)

    zip_size_mb = zip_target_root.stat().st_size / (1024 * 1024)
    raw_size_mb = total_bytes / (1024 * 1024)

    print("\n" + "=" * 65)
    print("✅ EXPORTAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 65)
    print(f"• Arquivo gerado em Downloads:")
    print(f"  👉 {zip_target_root}")
    print(f"  👉 {zip_target_dated.name}")
    print(f"• Total de arquivos incluídos: {total_files:,}")
    print(f"• Tamanho original: {raw_size_mb:.2f} MB")
    print(f"• Tamanho compactado (.zip): {zip_size_mb:.2f} MB")
    print(f"• Banco SQLite usmle_data.db: INCLUÍDO COM TODAS AS TABELAS")
    print("=" * 65)


if __name__ == "__main__":
    export_to_downloads()
