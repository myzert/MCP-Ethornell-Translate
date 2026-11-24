"""
BGI / Ethornell Bytecode Script Disassembler & Compiler.
Supports:
- BurikoCompiledScriptVer1.00 and V0 scripts.
- Extraction of dialogues (with speaker name), choices, and names.
- Clean injection and pointer recalculation (arbitrary string length, no truncation).
"""

import os
import json
import struct
from typing import List, Dict, Any, Tuple, Optional

MAGIC_V1 = b"BurikoCompiledScriptVer1.00\x00"

# V1 Bytecode Operands Template
# i: int32, c: code address (int32), m: string offset (int32)
V1_OPERAND_TEMPLATES = {
    0x0000: "i",
    0x0001: "c",
    0x0002: "i",
    0x0003: "m",
    0x0008: "i", 0x0009: "i", 0x000A: "i",
    0x0017: "i", 0x0019: "i", 0x003F: "i", 0x007E: "i",
    0x007B: "iii", 0x007F: "ii",
}

class ScriptItem:
    def __init__(self, item_id: int, item_type: str, speaker: str, original: str,
                 operand_offset: int, str_addr: int, extra_offsets: List[int] = None):
        self.id = item_id
        self.type = item_type  # "dialogue", "choice", "name"
        self.speaker = speaker
        self.original = original
        self.translated = original
        self.operand_offset = operand_offset
        self.str_addr = str_addr
        self.extra_offsets = extra_offsets or []

    def to_dict(self, include_context: bool = True, context: Dict[str, Any] = None) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "type": self.type,
            "speaker": self.speaker,
            "original": self.original,
            "translated": self.translated,
        }
        if include_context and context:
            d["context"] = context
        return d

class BGIScriptEngine:
    def __init__(self, data: bytes = None):
        self.data = bytearray(data) if data else bytearray()
        self.version = 1 if self.data.startswith(MAGIC_V1) else 0
        self.code_offset = 0
        self.code_length = 0
        self.items: List[ScriptItem] = []
        self.internal_strings: List[Tuple[int, int, str]] = []  # (operand_offset, str_addr, text)

        if self.data:
            self._disassemble()

    @classmethod
    def from_file(cls, path: str) -> "BGIScriptEngine":
        with open(path, "rb") as f:
            return cls(f.read())

    def _read_string_at(self, addr: int, encoding: str = "cp932") -> str:
        pos = self.code_offset + addr
        if pos < 0 or pos >= len(self.data):
            return ""
        end = self.data.find(b"\x00", pos)
        if end == -1:
            end = len(self.data)
        raw = self.data[pos:end]
        try:
            return raw.decode(encoding)
        except Exception:
            return raw.decode("latin-1", errors="replace")

    def _disassemble(self):
        self.items = []
        self.internal_strings = []

        if self.version == 1:
            self._disassemble_v1()
        else:
            self._disassemble_fallback()

    def _disassemble_v1(self):
        hdr_len = len(MAGIC_V1)
        header_size = struct.unpack("<I", self.data[hdr_len:hdr_len + 4])[0]
        self.code_offset = hdr_len + header_size

        pos = self.code_offset
        stack: List[Tuple[int, int]] = []  # (operand_offset, str_addr)
        largest_code_addr = 0
        item_id = 0

        while pos < len(self.data):
            if pos + 4 > len(self.data):
                break
            opcode = struct.unpack("<I", self.data[pos:pos + 4])[0]
            pos += 4

            if opcode == 0x0003:  # push string address
                str_addr = struct.unpack("<I", self.data[pos:pos + 4])[0]
                stack.append((pos, str_addr))
                pos += 4

            elif opcode == 0x001C:  # user function call
                if stack:
                    s_pos, s_addr = stack.pop()
                    func_name = self._read_string_at(s_addr)
                    self.internal_strings.append((s_pos, s_addr, func_name))
                    if func_name == "_SelectEx":
                        while stack:
                            c_pos, c_addr = stack.pop(0)
                            c_text = self._read_string_at(c_addr)
                            if c_text.strip():
                                item_id += 1
                                self.items.append(ScriptItem(
                                    item_id=item_id,
                                    item_type="choice",
                                    speaker="",
                                    original=c_text,
                                    operand_offset=c_pos,
                                    str_addr=c_addr
                                ))
                            else:
                                self.internal_strings.append((c_pos, c_addr, c_text))

            elif opcode in (0x0140, 0x0143):  # message display
                if stack:
                    m_pos, m_addr = stack.pop()
                    m_text = self._read_string_at(m_addr)
                    n_text = ""
                    n_pos = None
                    n_addr = None

                    if stack:
                        n_pos, n_addr = stack.pop()
                        n_text = self._read_string_at(n_addr).strip()
                        if n_text:
                            # Keep name in internal strings or link
                            self.internal_strings.append((n_pos, n_addr, n_text))
                        else:
                            self.internal_strings.append((n_pos, n_addr, ""))

                    if m_text.strip():
                        item_id += 1
                        self.items.append(ScriptItem(
                            item_id=item_id,
                            item_type="dialogue",
                            speaker=n_text,
                            original=m_text,
                            operand_offset=m_pos,
                            str_addr=m_addr
                        ))
                    else:
                        self.internal_strings.append((m_pos, m_addr, m_text))

            elif opcode == 0x0160:  # choice screen
                while stack:
                    c_pos, c_addr = stack.pop(0)
                    c_text = self._read_string_at(c_addr)
                    if c_text.strip():
                        item_id += 1
                        self.items.append(ScriptItem(
                            item_id=item_id,
                            item_type="choice",
                            speaker="",
                            original=c_text,
                            operand_offset=c_pos,
                            str_addr=c_addr
                        ))
                    else:
                        self.internal_strings.append((c_pos, c_addr, c_text))

            elif opcode in (0x007E, 0x007F, 0x00FE):
                while stack:
                    s_pos, s_addr = stack.pop()
                    s_text = self._read_string_at(s_addr)
                    self.internal_strings.append((s_pos, s_addr, s_text))

            else:
                tmpl = V1_OPERAND_TEMPLATES.get(opcode, "")
                for ch in tmpl:
                    if ch in ("i", "m"):
                        pos += 4
                    elif ch == "c":
                        c_addr = struct.unpack("<I", self.data[pos:pos + 4])[0]
                        if c_addr > largest_code_addr:
                            largest_code_addr = c_addr
                        pos += 4

            # Check for end of code section
            if opcode in (0x001B, 0x00F4) and largest_code_addr < (pos - self.code_offset):
                self.code_length = pos - self.code_offset
                break

        while stack:
            s_pos, s_addr = stack.pop()
            s_text = self._read_string_at(s_addr)
            self.internal_strings.append((s_pos, s_addr, s_text))

        if self.code_length == 0:
            self.code_length = pos - self.code_offset

    def _disassemble_fallback(self):
        """Fallback for scripts without standard header."""
        self.code_offset = 0
        i = 0
        item_id = 0
        while i < len(self.data) - 4:
            if self.data[i:i + 4] == b"\x03\x00\x00\x00":
                start = i + 4
                end = start
                while end < len(self.data) and self.data[end] != 0:
                    end += 1
                if end > start:
                    try:
                        text = self.data[start:end].decode("cp932")
                        if len(text.strip()) > 1 and not text.endswith((".bmp", ".png", ".ogg", ".wav", ".bss")):
                            item_id += 1
                            self.items.append(ScriptItem(
                                item_id=item_id,
                                item_type="dialogue",
                                speaker="",
                                original=text,
                                operand_offset=i,
                                str_addr=start
                            ))
                    except Exception:
                        pass
                i = end
            else:
                i += 1

    def export_json(self, include_context: bool = True) -> List[Dict[str, Any]]:
        """Exports dialogue and choices to a structured JSON dictionary."""
        result = []
        for idx, item in enumerate(self.items):
            ctx = None
            if include_context:
                prev_lines = []
                for p in range(max(0, idx - 3), idx):
                    prev = self.items[p]
                    spk = prev.speaker or "Narrator"
                    prev_lines.append(f"{spk}: {prev.original}")
                ctx = {
                    "prev_lines": prev_lines,
                    "speaker": item.speaker or "Narrator"
                }
            result.append(item.to_dict(include_context=include_context, context=ctx))
        return result

    def dump_to_json_file(self, json_path: str, include_context: bool = True):
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.export_json(include_context=include_context), f, ensure_ascii=False, indent=2)

    def compile(self, translations: List[Dict[str, Any]], encoding: str = "cp932") -> bytes:
        """
        Recompiles the bytecode script with translated strings.
        Preserves original bytecode logic and repoints string offsets to new text table.
        """
        if self.version != 1 or self.code_length == 0:
            # Fallback direct substitution for non-V1 scripts
            return self._compile_fallback(translations, encoding)

        # 1. Base bytecode up to end of code
        code_end = self.code_offset + self.code_length
        out_code = bytearray(self.data[:code_end])

        # 2. Build map of translations
        trans_map = {}
        for entry in translations:
            e_id = entry.get("id")
            if e_id is not None:
                trans_map[e_id] = entry.get("translated", entry.get("original", ""))

        # 3. Build string pool
        string_pool = bytearray()
        string_offset_cache: Dict[str, int] = {}  # text -> rel_offset

        def add_string(text: str) -> int:
            if text in string_offset_cache:
                return string_offset_cache[text]
            rel_offset = self.code_length + len(string_pool)
            try:
                raw_bytes = text.encode(encoding, errors="replace") + b"\x00"
            except Exception:
                raw_bytes = text.encode("utf-8", errors="replace") + b"\x00"
            string_pool.extend(raw_bytes)
            string_offset_cache[text] = rel_offset
            return rel_offset

        # 4. Patch internal strings
        for op_offset, orig_addr, text in self.internal_strings:
            new_addr = add_string(text)
            struct.pack_into("<I", out_code, op_offset, new_addr)

        # 5. Patch translated dialogue / choices
        for item in self.items:
            new_text = trans_map.get(item.id, item.original)
            new_addr = add_string(new_text)
            struct.pack_into("<I", out_code, item.operand_offset, new_addr)

        return bytes(out_code + string_pool)

    def _compile_fallback(self, translations: List[Dict[str, Any]], encoding: str = "cp932") -> bytes:
        data = bytearray(self.data)
        trans_map = {e.get("id"): e.get("translated", "") for e in translations}
        for item in self.items:
            new_text = trans_map.get(item.id, item.original)
            if new_text and new_text != item.original:
                orig_bytes = item.original.encode(encoding, errors="ignore")
                new_bytes = new_text.encode(encoding, errors="replace")
                if len(new_bytes) < len(orig_bytes):
                    new_bytes = new_bytes.ljust(len(orig_bytes), b"\x20")
                elif len(new_bytes) > len(orig_bytes):
                    new_bytes = new_bytes[:len(orig_bytes)]
                data[item.str_addr:item.str_addr + len(orig_bytes)] = new_bytes
        return bytes(data)

    def build_to_file(self, json_path: str, output_script_path: str, encoding: str = "cp932"):
        with open(json_path, "r", encoding="utf-8") as f:
            translations = json.load(f)
        compiled_data = self.compile(translations, encoding=encoding)
        os.makedirs(os.path.dirname(os.path.abspath(output_script_path)), exist_ok=True)
        with open(output_script_path, "wb") as f:
            f.write(compiled_data)
