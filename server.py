#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Server for BGI / Ethornell Visual Novel Translation.
Exposes tools over JSON-RPC 2.0 stdio:
- bgi_unpack_arc
- bgi_pack_arc
- bgi_decode_script
- bgi_encode_script
- bgi_translate
- bgi_get_info
- bgi_generate_llm_prompt
"""

import sys
import os
import json
import logging
from typing import Any, Dict, List

# Ensure bgi_core is importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from bgi_core.native_bridge import extract_archive, pack_buriko_arc20, list_arc_contents
from bgi_core.script_engine import BGIScriptEngine
from bgi_core.translator import ContextTranslator

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

TOOLS = [
    {
        "name": "bgi_unpack_arc",
        "description": "Unpack BGI / Ethornell .arc archive using native C engine. Automatically decrypts DSC compressed scripts, CBG graphics, and BSE containers.",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "arc_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the .arc archive file."
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory where extracted files will be stored."
                },
                "target_file": {
                    "type": "string",
                    "description": "Optional: extract only a single specific file from the archive."
                }
            },
            "required": ["arc_path", "output_dir"]
        }
    },
    {
        "name": "bgi_pack_arc",
        "description": "Pack a directory of files back into a valid BURIKO ARC20 archive. Can use original .arc as reference to preserve exact file ordering.",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_dir": {
                    "type": "string",
                    "description": "Directory containing files to pack."
                },
                "output_arc_path": {
                    "type": "string",
                    "description": "Destination path for the compiled .arc file."
                },
                "reference_arc_path": {
                    "type": "string",
                    "description": "Optional: original .arc file to match original order and structure."
                }
            },
            "required": ["input_dir", "output_arc_path"]
        }
    },
    {
        "name": "bgi_decode_script",
        "description": "Disassemble and decode a BGI bytecode scenario script into a clean, editable JSON dialogue file with speaker names, choices, and conversation context.",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Path to the extracted BGI bytecode scenario file."
                },
                "output_json_path": {
                    "type": "string",
                    "description": "Path where the dialogue JSON should be saved."
                },
                "include_context": {
                    "type": "boolean",
                    "description": "Whether to include preceding lines context for each dialogue entry (default: true)."
                }
            },
            "required": ["script_path", "output_json_path"]
        }
    },
    {
        "name": "bgi_encode_script",
        "description": "Recompile and inject translated dialogue JSON back into the BGI bytecode scenario script without text truncation or space padding.",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "original_script_path": {
                    "type": "string",
                    "description": "Original scenario bytecode script."
                },
                "translation_json_path": {
                    "type": "string",
                    "description": "JSON file containing translated dialogue items."
                },
                "output_script_path": {
                    "type": "string",
                    "description": "Destination path for the newly compiled script file."
                },
                "encoding": {
                    "type": "string",
                    "description": "Encoding for script strings (default: 'cp932')."
                }
            },
            "required": ["original_script_path", "translation_json_path", "output_script_path"]
        }
    },
    {
        "name": "bgi_translate",
        "description": "Translate visual novel dialogue items in a JSON file to any target language (e.g. 'id' for Indonesian, 'en' for English) with context awareness and glossary preservation.",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_json_path": {
                    "type": "string",
                    "description": "Input dialogue JSON file (produced by bgi_decode_script)."
                },
                "output_json_path": {
                    "type": "string",
                    "description": "Output translated JSON file."
                },
                "target_lang": {
                    "type": "string",
                    "description": "Target language code (e.g. 'id' for Indonesian, 'en', 'es', 'zh', 'ru'). Default is 'id'."
                },
                "source_lang": {
                    "type": "string",
                    "description": "Source language code (default: 'ja')."
                },
                "glossary": {
                    "type": "object",
                    "description": "Custom key-value dictionary for character names and specific terms."
                }
            },
            "required": ["input_json_path", "output_json_path"]
        }
    },
    {
        "name": "bgi_get_info",
        "description": "Inspect an .arc archive or BGI script file to display detailed metadata (contained files, script version, line count, character list).",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the archive (.arc) or script file."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "bgi_generate_llm_prompt",
        "description": "Generate a visual-novel context prompt for LLMs to translate a batch of dialogue lines with high accuracy and persona consistency.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_path": {
                    "type": "string",
                    "description": "Path to dialogue JSON file."
                },
                "target_lang": {
                    "type": "string",
                    "description": "Target language (default: 'id')."
                },
                "start_id": {
                    "type": "integer",
                    "description": "Start dialogue index (default: 1)."
                },
                "count": {
                    "type": "integer",
                    "description": "Number of dialogue lines to include (default: 25)."
                }
            },
            "required": ["json_path"]
        }
    }
]

def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if name == "bgi_unpack_arc":
            arc_path = arguments["arc_path"]
            output_dir = arguments["output_dir"]
            target_file = arguments.get("target_file")
            extracted = extract_archive(arc_path, output_dir, target_file)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Successfully extracted {len(extracted)} files to '{output_dir}'.\nFiles: {', '.join(extracted[:10])}{'...' if len(extracted) > 10 else ''}"
                }]
            }

        elif name == "bgi_pack_arc":
            input_dir = arguments["input_dir"]
            output_arc = arguments["output_arc_path"]
            ref_arc = arguments.get("reference_arc_path")
            count = pack_buriko_arc20(input_dir, output_arc, ref_arc)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Successfully packed {count} files into BURIKO ARC20 archive: '{output_arc}'."
                }]
            }

        elif name == "bgi_decode_script":
            script_path = arguments["script_path"]
            output_json = arguments["output_json_path"]
            include_context = arguments.get("include_context", True)
            engine = BGIScriptEngine.from_file(script_path)
            engine.dump_to_json_file(output_json, include_context=include_context)
            dialogues = [i for i in engine.items if i.type == "dialogue"]
            choices = [i for i in engine.items if i.type == "choice"]
            speakers = sorted(list({i.speaker for i in dialogues if i.speaker}))
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        f"Script decoded successfully: '{output_json}'.\n"
                        f"- Total translatable items: {len(engine.items)}\n"
                        f"- Dialogues: {len(dialogues)}\n"
                        f"- Choices: {len(choices)}\n"
                        f"- Identified Speakers: {', '.join(speakers) if speakers else 'None'}"
                    )
                }]
            }

        elif name == "bgi_encode_script":
            orig_script = arguments["original_script_path"]
            trans_json = arguments["translation_json_path"]
            out_script = arguments["output_script_path"]
            encoding = arguments.get("encoding", "cp932")
            engine = BGIScriptEngine.from_file(orig_script)
            engine.build_to_file(trans_json, out_script, encoding=encoding)
            orig_size = os.path.getsize(orig_script)
            new_size = os.path.getsize(out_script)
            return {
                "content": [{
                    "type": "text",
                    "text": (
                        f"Compiled patched script successfully: '{out_script}'.\n"
                        f"- Original size: {orig_size} bytes\n"
                        f"- Recompiled size: {new_size} bytes"
                    )
                }]
            }

        elif name == "bgi_translate":
            in_json = arguments["input_json_path"]
            out_json = arguments["output_json_path"]
            target_lang = arguments.get("target_lang", "id")
            source_lang = arguments.get("source_lang", "ja")
            glossary = arguments.get("glossary", {})
            with open(in_json, "r", encoding="utf-8") as f:
                items = json.load(f)
            translator = ContextTranslator(source_lang=source_lang, target_lang=target_lang, glossary=glossary)
            translated = translator.translate_items(items, target_lang=target_lang)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(translated, f, ensure_ascii=False, indent=2)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Successfully translated {len(translated)} items to '{target_lang}' -> saved to '{out_json}'."
                }]
            }

        elif name == "bgi_get_info":
            fpath = arguments["file_path"]
            if not os.path.exists(fpath):
                return {"isError": True, "content": [{"type": "text", "text": f"File not found: {fpath}"}]}
            if fpath.endswith(".arc"):
                entries = list_arc_contents(fpath)
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Archive: {os.path.basename(fpath)}\nTotal Files: {len(entries)}\nSamples:\n" +
                                "\n".join([f"  - {e['name']} ({e['size']} B)" for e in entries[:15]])
                    }]
                }
            else:
                engine = BGIScriptEngine.from_file(fpath)
                dialogues = [i for i in engine.items if i.type == "dialogue"]
                choices = [i for i in engine.items if i.type == "choice"]
                speakers = sorted(list({i.speaker for i in dialogues if i.speaker}))
                return {
                    "content": [{
                        "type": "text",
                        "text": (
                            f"BGI Script: {os.path.basename(fpath)}\n"
                            f"Version: {'V1 (BurikoCompiledScriptVer1.00)' if engine.version == 1 else 'V0 (Legacy)'}\n"
                            f"Code Length: {engine.code_length} bytes\n"
                            f"Translatable Items: {len(engine.items)} (Dialogue: {len(dialogues)}, Choices: {len(choices)})\n"
                            f"Characters: {', '.join(speakers)}"
                        )
                    }]
                }

        elif name == "bgi_generate_llm_prompt":
            json_path = arguments["json_path"]
            target_lang = arguments.get("target_lang", "id")
            start_id = arguments.get("start_id", 1)
            count = arguments.get("count", 25)
            with open(json_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            selected = [i for i in items if i.get("id", 0) >= start_id][:count]
            translator = ContextTranslator(target_lang=target_lang)
            prompt = translator.create_llm_prompt(selected, target_lang=target_lang)
            return {
                "content": [{
                    "type": "text",
                    "text": prompt
                }]
            }

        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

    except Exception as e:
        return {"isError": True, "content": [{"type": "text", "text": f"Error executing {name}: {str(e)}"}]}

def run_stdio_server():
    """Main JSON-RPC stdio event loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "bgi-ethornell-translator",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            call_res = handle_call_tool(tool_name, tool_args)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": call_res
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    run_stdio_server()
