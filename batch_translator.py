#!/usr/bin/env python3
"""
High-Performance Batch Translator and DLC Patch Generator for Sugar Style.
- Extracts all scenario files from data01010.arc.
- Decodes bytecode to JSON.
- Context-aware translates dialogues with concurrent workers and cache.
- Recompiles bytecode scripts.
- Builds patched data01010.arc ready as a DLC patch.
"""

import sys
import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Setup path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from bgi_core.native_bridge import extract_archive, pack_buriko_arc20
from bgi_core.script_engine import BGIScriptEngine
from bgi_core.translator import ContextTranslator

def translate_scenario_file(script_path: str, output_script_path: str, translator: ContextTranslator, max_workers: int = 8) -> int:
    """Translates a single scenario bytecode file and saves the patched bytecode."""
    engine = BGIScriptEngine.from_file(script_path)
    if not engine.items:
        # No dialogue items, copy directly
        with open(script_path, "rb") as f_in, open(output_script_path, "wb") as f_out:
            f_out.write(f_in.read())
        return 0

    items = engine.export_json(include_context=True)
    
    # Extract unique texts to avoid redundant requests
    unique_texts = list({it["original"] for it in items if it.get("original")})
    
    trans_cache = {}
    def trans_worker(txt):
        return txt, translator.translate_text_online(txt, source=translator.source_lang, target=translator.target_lang)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for orig, res in pool.map(trans_worker, unique_texts):
            trans_cache[orig] = res

    # Apply to items
    for it in items:
        orig = it.get("original")
        if orig in trans_cache:
            it["translated"] = trans_cache[orig]

    # Compile patched bytecode
    patched_data = engine.compile(items)
    os.makedirs(os.path.dirname(os.path.abspath(output_script_path)), exist_ok=True)
    with open(output_script_path, "wb") as f:
        f.write(patched_data)

    return len(items)

def run_dlc_build(
    game_arc_path: str,
    output_dlc_dir: str,
    file_filter: list = None,
    target_lang: str = "id",
    source_lang: str = "en",
    max_workers: int = 8
):
    print(f"=== Sugar Style Indonesian DLC Patch Generator ===")
    print(f"Target ARC: {game_arc_path}")
    print(f"Output DLC Directory: {output_dlc_dir}")
    print(f"Language: {source_lang} -> {target_lang}")

    os.makedirs(output_dlc_dir, exist_ok=True)
    work_dir = os.path.join(output_dlc_dir, "work_extracted")
    patched_dir = os.path.join(output_dlc_dir, "work_patched")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(patched_dir, exist_ok=True)

    # 1. Extract all original scenario files
    print("\n[1/4] Extracting original scenario files from archive...")
    files = extract_archive(game_arc_path, work_dir)
    print(f"Extracted {len(files)} files.")

    translator = ContextTranslator(source_lang=source_lang, target_lang=target_lang)

    # 2. Determine target files
    if file_filter:
        target_files = [f for f in files if any(k in f for k in file_filter)]
    else:
        target_files = files

    print(f"\n[2/4] Translating {len(target_files)} scenario files...")
    total_translated_lines = 0

    for idx, fname in enumerate(target_files, 1):
        in_p = os.path.join(work_dir, fname)
        out_p = os.path.join(patched_dir, fname)
        
        t0 = time.time()
        lines = translate_scenario_file(in_p, out_p, translator, max_workers=max_workers)
        t1 = time.time()
        total_translated_lines += lines
        print(f"[{idx}/{len(target_files)}] Translated {fname}: {lines} lines ({t1 - t0:.1f}s)")

    # Copy any untouched files to patched_dir
    for fname in files:
        out_p = os.path.join(patched_dir, fname)
        if not os.path.exists(out_p):
            in_p = os.path.join(work_dir, fname)
            with open(in_p, "rb") as f_in, open(out_p, "wb") as f_out:
                f_out.write(f_in.read())

    # 3. Pack patched BURIKO ARC20
    output_arc = os.path.join(output_dlc_dir, "data01010.arc")
    print(f"\n[3/4] Packing translated files into DLC archive: {output_arc}...")
    pack_buriko_arc20(patched_dir, output_arc, reference_arc_path=game_arc_path)

    print(f"\n[4/4] Generating installer and documentation...")
    # Generate install / uninstall scripts
    _generate_dlc_scripts(output_dlc_dir, game_arc_path)

    print(f"\n✅ DLC Patch built successfully!")
    print(f"Location: {output_dlc_dir}")
    print(f"Total Lines Translated: {total_translated_lines}")

def _generate_dlc_scripts(dlc_dir: str, original_arc_path: str):
    # Windows batch installer
    bat_content = """@echo off
echo ========================================================
echo  Sugar Style - Indonesian Translation DLC Patch Installer
echo ========================================================
set GAME_DIR=..
if not exist "%GAME_DIR%\\SugarStyle.exe" (
    echo Error: Jalankan file installer ini dari dalam folder DLC Patch di dalam folder game Sugar Style!
    pause
    exit /b 1
)

if not exist "%GAME_DIR%\\Archive\\data01010.arc.bak" (
    echo [*] Membuat backup original data01010.arc -> data01010.arc.bak ...
    copy "%GAME_DIR%\\Archive\\data01010.arc" "%GAME_DIR%\\Archive\\data01010.arc.bak" >nul
)

echo [*] Memasang file translasi Bahasa Indonesia...
copy /Y "data01010.arc" "%GAME_DIR%\\Archive\\data01010.arc" >nul
echo.
echo ========================================================
echo  Instalasi Selesai! Selamat Bermain Sugar Style (ID)!
echo ========================================================
pause
"""
    with open(os.path.join(dlc_dir, "install_patch.bat"), "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Linux / Android shell installer
    sh_content = """#!/bin/sh
echo "=== Sugar Style Indonesian DLC Installer ==="
TARGET_DIR="../Archive"
if [ ! -d "$TARGET_DIR" ]; then
    TARGET_DIR="../../Sugar Style/Archive"
fi

if [ ! -f "$TARGET_DIR/data01010.arc.bak" ]; then
    echo "[*] Membuat backup data01010.arc.bak..."
    cp "$TARGET_DIR/data01010.arc" "$TARGET_DIR/data01010.arc.bak"
fi

echo "[*] Memasang patch translasi Bahasa Indonesia..."
cp "data01010.arc" "$TARGET_DIR/data01010.arc"
echo "✅ Instalasi Selesai! Game siap dimainkan."
"""
    sh_path = os.path.join(dlc_dir, "install_patch.sh")
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(sh_content)
    try:
        os.chmod(sh_path, 0o755)
    except:
        pass

    # Readme
    readme_content = """# Sugar Style - Indonesian Translation DLC Patch 🌸

Patch / DLC Translasi Bahasa Indonesia untuk Visual Novel **Sugar Style** (SMEE / BGI Engine).

## 🌟 Cara Pemasangan:

### Metode 1: Otomatis (Windows)
1. Letakkan folder `Sugar_Style_Indonesian_DLC_Patch` di dalam direktori instalasi game `Sugar Style`.
2. Buka folder tersebut dan klik dua kali `install_patch.bat`.
3. Jalankan `SugarStyle.exe` dan nikmati permainan dalam Bahasa Indonesia!

### Metode 2: Manual
1. Buka folder `Sugar Style/Archive/`.
2. Backup file `data01010.arc` menjadi `data01010.arc.bak`.
3. Salin file `data01010.arc` dari folder patch ini dan timpa ke `Sugar Style/Archive/data01010.arc`.

---

## 🔄 Cara Menghapus Patch (Uninstall / Restore):
- Hapus `data01010.arc` di folder `Archive/`.
- Ubah nama `data01010.arc.bak` kembali menjadi `data01010.arc`.
"""
    with open(os.path.join(dlc_dir, "README_DLC.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

if __name__ == "__main__":
    game_arc = "/sdcard/game_tl/Sugar Style/Archive/data01010.arc"
    out_dlc = "/sdcard/game_tl/Sugar_Style_Indonesian_DLC_Patch"
    
    # Priority files for initial release (prologue & chapters & selections)
    # If arguments given, can customize
    filter_list = sys.argv[1:] if len(sys.argv) > 1 else ["prologue", "chapter01", "sel01", "setup"]
    run_dlc_build(game_arc, out_dlc, file_filter=filter_list)
