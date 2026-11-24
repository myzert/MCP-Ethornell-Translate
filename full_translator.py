#!/usr/bin/env python3
"""
Full Automated Visual Novel Translator and Game Patcher for Sugar Style.
Translates all 153 scenario files and directly installs the translated data01010.arc
into the game's Archive directory so the user can play immediately!
"""

import sys
import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from bgi_core.native_bridge import extract_archive, pack_buriko_arc20
from bgi_core.script_engine import BGIScriptEngine
from bgi_core.translator import ContextTranslator

CACHE_FILE = "/sdcard/game_tl/translation_cache.json"

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except:
        pass

def hash_file(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def main():
    print("=" * 60)
    print("🌸 SUGAR STYLE FULL TRANSLATION TO INDONESIAN 🌸")
    print("=" * 60)

    game_dir = "/sdcard/game_tl/Sugar Style"
    archive_path = os.path.join(game_dir, "Archive", "data01010.arc")
    backup_path = os.path.join(game_dir, "Archive", "data01010.arc.bak")
    dlc_arc_path = "/sdcard/game_tl/Sugar_Style_Indonesian_DLC_Patch/data01010.arc"
    
    work_dir = "/sdcard/game_tl/sugar_style_extracted"
    patched_dir = "/sdcard/game_tl/sugar_style_full_patched"
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(patched_dir, exist_ok=True)

    # 1. Ensure backup exists
    if not os.path.exists(backup_path) and os.path.exists(archive_path):
        import shutil
        shutil.copy2(archive_path, backup_path)
        print(f"[*] Backup created: {backup_path}")

    # 2. Extract original files
    print("\n[*] Checking/Extracting original files...")
    orig_files = extract_archive(backup_path if os.path.exists(backup_path) else archive_path, work_dir)
    print(f"[+] Total scenario files: {len(orig_files)}")

    # 3. Load global cache
    global_cache = load_cache()
    print(f"[+] Loaded {len(global_cache)} pre-translated phrases from cache.")

    translator = ContextTranslator(source_lang="en", target_lang="id")
    
    # 4. Process all scenario files
    total_files = len(orig_files)
    total_lines_translated = 0
    start_time = time.time()

    for idx, fname in enumerate(sorted(orig_files), 1):
        in_path = os.path.join(work_dir, fname)
        out_path = os.path.join(patched_dir, fname)

        # Check if already translated (different hash from original)
        if os.path.exists(out_path) and hash_file(in_path) != hash_file(out_path):
            print(f"[{idx}/{total_files}] {fname} already translated. Skipping.")
            continue

        try:
            engine = BGIScriptEngine.from_file(in_path)
        except Exception as e:
            # Copy as is if not a script
            with open(in_path, "rb") as sf, open(out_path, "wb") as df:
                df.write(sf.read())
            continue

        if not engine.items:
            with open(in_path, "rb") as sf, open(out_path, "wb") as df:
                df.write(sf.read())
            continue

        items = engine.export_json(include_context=True)
        unique_missing = list({it["original"] for it in items if it.get("original") and it["original"] not in global_cache})

        if unique_missing:
            # Ultra-fast bulk chunk translation
            bulk_res = translator.translate_batch_bulk(unique_missing, source="en", target="id")
            global_cache.update(bulk_res)

        # Apply translations
        for it in items:
            orig = it.get("original")
            if orig in global_cache:
                it["translated"] = global_cache[orig]

        # Compile patched bytecode
        patched_data = engine.compile(items)
        with open(out_path, "wb") as f:
            f.write(patched_data)

        total_lines_translated += len(items)
        print(f"[{idx}/{total_files}] Translated {fname} ({len(items)} lines) - Cache: {len(global_cache)}")

        # Save cache and update game arc periodically
        if idx % 10 == 0:
            save_cache(global_cache)
            ref_arc = backup_path if os.path.exists(backup_path) else archive_path
            pack_buriko_arc20(patched_dir, archive_path, reference_arc_path=ref_arc)

    save_cache(global_cache)
    elapsed = time.time() - start_time
    print(f"\n[+] Translation completed in {elapsed:.1f}s!")

    # 5. Pack directly to Sugar Style game folder & DLC folder
    print("\n[*] Packing BURIKO ARC20 archive directly into game directory...")
    ref_arc = backup_path if os.path.exists(backup_path) else archive_path
    pack_buriko_arc20(patched_dir, archive_path, reference_arc_path=ref_arc)
    print(f"[✅] Installed to: {archive_path} ({os.path.getsize(archive_path)} bytes)")

    # Also update DLC folder
    os.makedirs(os.path.dirname(dlc_arc_path), exist_ok=True)
    pack_buriko_arc20(patched_dir, dlc_arc_path, reference_arc_path=ref_arc)
    print(f"[✅] Updated DLC patch: {dlc_arc_path}")

    print("\n" + "=" * 60)
    print("🎉 FULL TRANSLATION INSTALLED! SIAP DIMAINKAN!")
    print("=" * 60)

if __name__ == "__main__":
    main()
