"""
Native bridge for BGIextractor C core.
Handles running the native ethornell binary to decompress and extract DSC, CBG, BSE,
and BURIKO ARC archives.
"""

import os
import sys
import shutil
import subprocess
import struct
from pathlib import Path

# Base directories
PROJECT_DIR = Path(__file__).resolve().parent.parent
NATIVE_DIR = PROJECT_DIR / "native"

def get_native_binary_path() -> str:
    """
    Finds or automatically compiles the native ethornell binary.
    On Android/Termux, ensures the binary is placed in an executable filesystem (~/.local/bin or $TMPDIR).
    """
    # 1. Check system PATH
    system_bin = shutil.which("ethornell")
    if system_bin and os.access(system_bin, os.X_OK):
        return system_bin

    # 2. Check ~/.local/bin/ethornell
    home_dir = os.environ.get("HOME", "")
    if home_dir:
        user_bin = os.path.join(home_dir, ".local", "bin", "ethornell")
        if os.path.isfile(user_bin) and os.access(user_bin, os.X_OK):
            return user_bin

    # 3. Check project native folder (if executable filesystem)
    exe_name = "ethornell.exe" if os.name == "nt" else "ethornell"
    local_exe = NATIVE_DIR / exe_name
    if local_exe.is_file() and os.access(str(local_exe), os.X_OK):
        return str(local_exe)

    # 4. Check TMPDIR / /tmp
    tmp_dir = os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp" if os.path.exists("/data/data/com.termux/files/usr/tmp") else "/tmp")
    tmp_bin = os.path.join(tmp_dir, exe_name)
    if os.path.isfile(tmp_bin) and os.access(tmp_bin, os.X_OK):
        return tmp_bin

    # If not found or not executable, compile it now!
    return compile_native_binary()

def compile_native_binary() -> str:
    """Compiles the C source files in native/ to an executable binary."""
    c_files = ["main.c", "arc.c", "dsc.c", "cbg.c", "bse.c", "decrypt.c", "write.c"]
    src_paths = [str(NATIVE_DIR / f) for f in c_files]
    
    # Verify all C files exist
    for p in src_paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Missing native source file: {p}")

    # Determine executable destination
    home_dir = os.environ.get("HOME", "")
    target_dir = os.path.join(home_dir, ".local", "bin") if home_dir else str(NATIVE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    
    out_bin = os.path.join(target_dir, "ethornell.exe" if os.name == "nt" else "ethornell")
    
    # Try compiling with gcc or clang
    compiler = "gcc" if shutil.which("gcc") else ("clang" if shutil.which("clang") else None)
    if not compiler:
        raise RuntimeError("No C compiler (gcc or clang) found to build native code.")

    cmd = [compiler, "-o", out_bin, "-O2", "-Wall", "-Wno-unused-result"] + src_paths
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Compilation of native ethornell failed:\n{res.stderr}")

    os.chmod(out_bin, 0o755)
    return out_bin

def extract_archive(arc_path: str, output_dir: str, target_file: str = None) -> list[str]:
    """
    Extracts all files (or a specific file) from a BGI .arc archive,
    automatically decompressing DSC/CBG/BSE files using native code.
    """
    arc_path = os.path.abspath(arc_path)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(arc_path):
        raise FileNotFoundError(f"ARC archive not found: {arc_path}")

    bin_path = get_native_binary_path()
    cmd = [bin_path, arc_path, output_dir]
    if target_file:
        cmd.append(target_file)

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to extract ARC:\n{res.stderr or res.stdout}")

    # List extracted files
    extracted = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
    return extracted

def list_arc_contents(arc_path: str) -> list[dict]:
    """Lists metadata for all files in a BGI ARC (BURIKO ARC20 or PackFile) archive."""
    with open(arc_path, "rb") as f:
        magic = f.read(12)
        if magic not in (b"BURIKO ARC20", b"PackFile    "):
            raise ValueError(f"Unrecognized ARC header: {magic}")

        file_count = struct.unpack("<I", f.read(4))[0]
        entries = []
        is_v2 = (magic == b"BURIKO ARC20")

        for _ in range(file_count):
            name_bytes = f.read(16)
            name = name_bytes.split(b"\x00")[0].decode("shift_jis", errors="ignore")
            if is_v2:
                f.read(80)  # padding
            offset, size = struct.unpack("<II", f.read(8))
            if is_v2:
                f.read(24)  # v2 extra metadata
            else:
                f.read(8)

            entries.append({
                "name": name,
                "offset": offset,
                "size": size
            })
    return entries

def pack_buriko_arc20(input_dir: str, output_arc_path: str, reference_arc_path: str = None) -> int:
    """
    Packs all files in input_dir into a valid BURIKO ARC20 archive.
    If reference_arc_path is provided, matches the exact file ordering of the original archive.
    """
    input_dir = os.path.abspath(input_dir)
    output_arc_path = os.path.abspath(output_arc_path)
    os.makedirs(os.path.dirname(output_arc_path), exist_ok=True)

    available_files = {f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))}
    ordered_files = []

    if reference_arc_path and os.path.isfile(reference_arc_path):
        ref_entries = list_arc_contents(reference_arc_path)
        for entry in ref_entries:
            if entry["name"] in available_files:
                ordered_files.append(entry["name"])
                available_files.remove(entry["name"])

    # Append any remaining files
    ordered_files.extend(sorted(list(available_files)))

    file_paths = [os.path.join(input_dir, name) for name in ordered_files]
    count = len(file_paths)

    with open(output_arc_path, "wb") as arc_file:
        # 12 bytes magic + 4 bytes count
        arc_file.write(b"BURIKO ARC20")
        arc_file.write(struct.pack("<I", count))

        # File table: each entry is 128 bytes (96 bytes name, 4 bytes offset, 4 bytes size, 24 bytes null)
        data_offset = 16 + (count * 128)
        for fp in file_paths:
            size = os.path.getsize(fp)
            name_bytes = os.path.basename(fp).encode("shift_jis", errors="replace")[:96]
            name_padded = name_bytes.ljust(96, b"\x00")
            arc_file.write(name_padded)
            arc_file.write(struct.pack("<II", data_offset, size))
            arc_file.write(b"\x00" * 24)
            data_offset += size

        # File data blocks
        for fp in file_paths:
            with open(fp, "rb") as in_f:
                shutil.copyfileobj(in_f, arc_file)

    return count
