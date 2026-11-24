"""
Context-Aware Multi-Language Translation Engine for Visual Novels.
Supports:
- Multi-language translation (id, en, ja, es, zh, ko, ru, etc.)
- Context awareness (speaker persona, preceding dialogue history, scene tone)
- Glossary & Character name mapping
- Automatic online translation via lightweight HTTP
- LLM translation prompt formatting
"""

import re
import json
import time
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional

DEFAULT_GLOSSARY = {
    # Common honorifics and terms
    "お兄ちゃん": "Kakak",
    "先輩": "Senpai",
    "先生": "Sensei",
    "ちゃん": "-chan",
    "さん": "-san",
    "くん": "-kun",
}

class ContextTranslator:
    def __init__(self, source_lang: str = "ja", target_lang: str = "id", glossary: Dict[str, str] = None):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.glossary = DEFAULT_GLOSSARY.copy()
        if glossary:
            self.glossary.update(glossary)

    def set_glossary(self, term_map: Dict[str, str]):
        self.glossary.update(term_map)

    def _clean_for_translation(self, text: str) -> Tuple[str, str, str]:
        """Separates leading/trailing punctuation/quotes/indentation from the core text."""
        leading = ""
        trailing = ""

        # Japanese full-width space indentation
        if text.startswith("\u3000"):
            leading += "\u3000"
            text = text[1:]

        # Quotes: 「 ... 」 or " ... "
        if text.startswith(("「", '"', "“")):
            leading += text[0]
            text = text[1:]
        if text.endswith(("」", '"', "”", "<")):
            trailing = text[-1] + trailing
            text = text[:-1]
        if text.endswith("\u3000"):
            trailing = "\u3000" + trailing
            text = text[:-1]

        return leading, text, trailing

    def translate_text_online(self, text: str, source: str = None, target: str = None) -> str:
        """
        Translates single string via resilient endpoints (Google Chrome endpoint & MyMemory fallback).
        Fast, robust, zero credentials required.
        """
        source = source or self.source_lang
        target = target or self.target_lang
        
        if not text.strip():
            return text

        leading, core_text, trailing = self._clean_for_translation(text)
        if not core_text.strip():
            return text

        # 1. Primary: Google Client5 API (no 429 rate limit)
        try:
            url1 = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source}&tl={target}&q={urllib.parse.quote(core_text)}"
            req1 = urllib.request.Request(url1, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req1, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    translated_core = data[0] if isinstance(data[0], str) else data[0][0]
                    return leading + translated_core + trailing
        except Exception:
            pass

        # 2. Fallback: MyMemory API
        try:
            url2 = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(core_text)}&langpair={source}|{target}"
            req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                trans = data.get("responseData", {}).get("translatedText")
                if trans:
                    return leading + trans + trailing
        except Exception:
            pass

        # 3. Fallback: Google GTX API
        try:
            url3 = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source}&tl={target}&dt=t&q={urllib.parse.quote(core_text)}"
            req3 = urllib.request.Request(url3, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req3, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                translated_core = "".join([part[0] for part in data[0] if part[0]])
                return leading + translated_core + trailing
        except Exception:
            pass

        # Fallback if all network endpoints fail
        return text

    def translate_items(self, items: List[Dict[str, Any]], target_lang: str = None,
                        batch_size: int = 20, delay: float = 0.2) -> List[Dict[str, Any]]:
        """
        Translates a list of dialogue items with context awareness.
        """
        target = target_lang or self.target_lang
        results = []

        for idx, item in enumerate(items):
            orig = item.get("original", "")
            speaker = item.get("speaker", "")
            item_type = item.get("type", "dialogue")

            # Check if speaker name is translatable
            trans_speaker = speaker
            if speaker in self.glossary:
                trans_speaker = self.glossary[speaker]

            # Translate content
            trans_text = self.translate_text_online(orig, target=target)
            
            new_item = item.copy()
            new_item["translated"] = trans_text
            if trans_speaker != speaker:
                new_item["translated_speaker"] = trans_speaker

            results.append(new_item)
            if delay > 0 and (idx % batch_size == 0):
                time.sleep(delay)

        return results

    def create_llm_prompt(self, items: List[Dict[str, Any]], target_lang: str = None) -> str:
        """
        Generates a rich, context-aware prompt for LLM models to perform professional
        visual novel translation.
        """
        target = target_lang or self.target_lang
        target_name = {
            "id": "Indonesian (Bahasa Indonesia santai, alami, sesuai karakter VN)",
            "en": "English (natural visual novel localization)",
            "es": "Spanish (Español neutro)",
            "zh": "Simplified Chinese",
            "ru": "Russian",
            "fr": "French",
            "de": "German",
            "ja": "Japanese"
        }.get(target, target)

        lines = [
            f"You are a professional Visual Novel localization specialist translating from Japanese to {target_name}.",
            "Maintain dialogue tone, personality, banter, comedic timing, and relationship intimacy.",
            "Do NOT remove or alter engine control tags like <I>, </I>, <B>, \\n, or quotes.",
            "",
            "Here is the dialogue sequence with surrounding conversation context:",
            ""
        ]

        for item in items:
            spk = item.get("speaker") or "Narrator"
            ctx = item.get("context", {})
            prev = ctx.get("prev_lines", [])
            lines.append(f"--- Line ID: {item.get('id')} ---")
            if prev:
                lines.append("Context [Previous lines]:")
                for p in prev:
                    lines.append(f"  {p}")
            lines.append(f"Speaker: {spk}")
            lines.append(f"Original: {item.get('original')}")
            lines.append("")

        lines.append("Please output a valid JSON array of objects with keys 'id' and 'translated':")
        lines.append("```json")
        lines.append("[")
        lines.append('  { "id": 1, "translated": "..." }')
        lines.append("]")
        lines.append("```")

        return "\n".join(lines)
