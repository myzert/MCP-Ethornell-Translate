#!/usr/bin/env python3
"""
CLI entry point for BGI / Ethornell Visual Novel Translation Toolkit.
Usage:
  python cli.py unpack <archive.arc> <output_dir>
  python cli.py pack <input_dir> <output.arc> [--ref <ref.arc>]
  python cli.py decode <script_file> <output.json>
  python cli.py encode <original_script> <translation.json> <output_script>
  python cli.py translate <input.json> <output.json> [--to id] [--from ja]
  python cli.py info <file>
  python cli.py mcp
"""

import sys
import os
import argparse
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from bgi_core.native_bridge import extract_archive, pack_buriko_arc20, list_arc_contents
from bgi_core.script_engine import BGIScriptEngine
from bgi_core.translator import ContextTranslator
from server import run_stdio_server

def main():
    parser = argparse.ArgumentParser(
        prog="bgi-tl",
        description="BGI / Ethornell Visual Novel Translation Toolkit (MCP & CLI)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # unpack
    p_unpack = subparsers.add_parser("unpack", help="Unpack .arc archive (auto decrypts DSC/CBG/BSE)")
    p_unpack.add_argument("arc", help="Path to .arc file")
    p_unpack.add_argument("out", help="Output directory")
    p_unpack.add_argument("--target", help="Single target file inside arc", default=None)

    # pack
    p_pack = subparsers.add_parser("pack", help="Pack directory into BURIKO ARC20 archive")
    p_pack.add_argument("dir", help="Directory of files to pack")
    p_pack.add_argument("out", help="Output .arc file path")
    p_pack.add_argument("--ref", help="Reference original .arc file for ordering", default=None)

    # decode
    p_decode = subparsers.add_parser("decode", help="Disassemble BGI script into JSON dialogue")
    p_decode.add_argument("script", help="Path to BGI script file")
    p_decode.add_argument("out", help="Output JSON path")
    p_decode.add_argument("--no-context", action="store_true", help="Omit conversation context")

    # encode
    p_encode = subparsers.add_parser("encode", help="Compile translated JSON back into BGI bytecode")
    p_encode.add_argument("orig", help="Original script file")
    p_encode.add_argument("json", help="Translated JSON file")
    p_encode.add_argument("out", help="Output compiled script file")
    p_encode.add_argument("--enc", default="cp932", help="Encoding (default: cp932)")

    # translate
    p_trans = subparsers.add_parser("translate", help="Auto translate dialogue JSON with context")
    p_trans.add_argument("input", help="Input dialogue JSON")
    p_trans.add_argument("out", help="Output translated JSON")
    p_trans.add_argument("--to", default="id", help="Target language (default: id for Indonesian)")
    p_trans.add_argument("--from-lang", default="ja", help="Source language (default: ja)")

    # info
    p_info = subparsers.add_parser("info", help="Inspect .arc or script file")
    p_info.add_argument("file", help="Path to file")

    # mcp
    subparsers.add_parser("mcp", help="Run MCP JSON-RPC Server over stdio")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "unpack":
        print(f"[*] Unpacking '{args.arc}' -> '{args.out}'...")
        files = extract_archive(args.arc, args.out, args.target)
        print(f"[+] Successfully extracted {len(files)} files.")

    elif args.command == "pack":
        print(f"[*] Packing '{args.dir}' -> '{args.out}'...")
        count = pack_buriko_arc20(args.dir, args.out, args.ref)
        print(f"[+] Successfully packed {count} files.")

    elif args.command == "decode":
        print(f"[*] Decoding script '{args.script}' -> '{args.out}'...")
        engine = BGIScriptEngine.from_file(args.script)
        engine.dump_to_json_file(args.out, include_context=not args.no_context)
        print(f"[+] Successfully extracted {len(engine.items)} translatable items.")

    elif args.command == "encode":
        print(f"[*] Compiling patched script '{args.orig}' + '{args.json}' -> '{args.out}'...")
        engine = BGIScriptEngine.from_file(args.orig)
        engine.build_to_file(args.json, args.out, encoding=args.enc)
        print(f"[+] Successfully built: {args.out} ({os.path.getsize(args.out)} bytes)")

    elif args.command == "translate":
        print(f"[*] Translating '{args.input}' to '{args.to}'...")
        with open(args.input, "r", encoding="utf-8") as f:
            items = json.load(f)
        t = ContextTranslator(source_lang=args.from_lang, target_lang=args.to)
        res = t.translate_items(items, target_lang=args.to)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(f"[+] Translation complete: '{args.out}' ({len(res)} items)")

    elif args.command == "info":
        if args.file.endswith(".arc"):
            entries = list_arc_contents(args.file)
            print(f"Archive: {args.file}")
            print(f"File count: {len(entries)}")
            for e in entries[:20]:
                print(f"  {e['name']}: {e['size']} bytes")
        else:
            engine = BGIScriptEngine.from_file(args.file)
            dialogues = [i for i in engine.items if i.type == "dialogue"]
            choices = [i for i in engine.items if i.type == "choice"]
            speakers = sorted(list({i.speaker for i in dialogues if i.speaker}))
            print(f"BGI Script: {args.file}")
            print(f"Version: {'V1' if engine.version == 1 else 'V0'}")
            print(f"Translatable lines: {len(engine.items)} (Dialogue: {len(dialogues)}, Choices: {len(choices)})")
            print(f"Characters: {', '.join(speakers)}")

    elif args.command == "mcp":
        run_stdio_server()

if __name__ == "__main__":
    main()
