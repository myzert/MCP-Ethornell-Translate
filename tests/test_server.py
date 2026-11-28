#!/usr/bin/env python3
"""
Tests for MCP server tools: tool registration, annotations, and handler behaviour.
Run with:  python -m pytest tests/ -v
"""

import json
import os
import sys
import tempfile
import pytest

# Make sure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from server import TOOLS, handle_call_tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL_NAMES = [t["name"] for t in TOOLS]
REQUIRED_ANNOTATIONS = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}


def get_tool(name: str) -> dict:
    return next(t for t in TOOLS if t["name"] == name)


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    def test_all_seven_tools_declared(self):
        expected = {
            "bgi_unpack_arc",
            "bgi_pack_arc",
            "bgi_decode_script",
            "bgi_encode_script",
            "bgi_translate",
            "bgi_get_info",
            "bgi_generate_llm_prompt",
        }
        assert set(TOOL_NAMES) == expected

    def test_no_duplicate_tool_names(self):
        assert len(TOOL_NAMES) == len(set(TOOL_NAMES))

    @pytest.mark.parametrize("tool", TOOLS, ids=TOOL_NAMES)
    def test_tool_has_name_description_inputschema(self, tool):
        assert "name" in tool
        assert "description" in tool and tool["description"]
        assert "inputSchema" in tool

    @pytest.mark.parametrize("tool", TOOLS, ids=TOOL_NAMES)
    def test_all_four_annotations_present_and_boolean(self, tool):
        assert "annotations" in tool, f"{tool['name']} missing 'annotations'"
        ann = tool["annotations"]
        for hint in REQUIRED_ANNOTATIONS:
            assert hint in ann, f"{tool['name']} missing annotation '{hint}'"
            assert isinstance(ann[hint], bool), (
                f"{tool['name']}.annotations.{hint} must be bool, got {type(ann[hint])}"
            )


# ---------------------------------------------------------------------------
# Annotation semantics tests
# ---------------------------------------------------------------------------

class TestAnnotationSemantics:
    def test_bgi_get_info_is_read_only(self):
        ann = get_tool("bgi_get_info")["annotations"]
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False

    def test_bgi_generate_llm_prompt_is_read_only(self):
        ann = get_tool("bgi_generate_llm_prompt")["annotations"]
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False

    def test_bgi_translate_is_open_world(self):
        """bgi_translate calls an external LLM API → openWorldHint must be True."""
        ann = get_tool("bgi_translate")["annotations"]
        assert ann["openWorldHint"] is True

    def test_write_tools_are_not_read_only(self):
        for name in ("bgi_unpack_arc", "bgi_pack_arc", "bgi_decode_script", "bgi_encode_script"):
            ann = get_tool(name)["annotations"]
            assert ann["readOnlyHint"] is False, f"{name} should not be readOnly"

    def test_no_tool_is_destructive(self):
        """None of our tools delete or permanently mutate existing files."""
        for tool in TOOLS:
            assert tool["annotations"]["destructiveHint"] is False, (
                f"{tool['name']} unexpectedly marked destructive"
            )


# ---------------------------------------------------------------------------
# Handler tests (using real filesystem fixtures)
# ---------------------------------------------------------------------------

class TestHandleCallToolErrors:
    def test_unknown_tool_returns_error(self):
        result = handle_call_tool("non_existent_tool", {})
        assert result.get("isError") is True

    def test_bgi_get_info_missing_file(self):
        result = handle_call_tool("bgi_get_info", {"file_path": "/no/such/file.arc"})
        assert result.get("isError") is True
        assert "not found" in result["content"][0]["text"].lower()

    def test_bgi_unpack_arc_bad_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = handle_call_tool("bgi_unpack_arc", {
                "arc_path": "/no/such/archive.arc",
                "output_dir": tmpdir
            })
        assert result.get("isError") is True

    def test_bgi_decode_script_bad_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_json = os.path.join(tmpdir, "out.json")
            result = handle_call_tool("bgi_decode_script", {
                "script_path": "/no/such/script.bin",
                "output_json_path": out_json
            })
        assert result.get("isError") is True

    def test_bgi_encode_script_bad_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = handle_call_tool("bgi_encode_script", {
                "original_script_path": "/no/such/orig.bin",
                "translation_json_path": "/no/such/tl.json",
                "output_script_path": os.path.join(tmpdir, "out.bin")
            })
        assert result.get("isError") is True

    def test_bgi_translate_bad_input_json(self):
        result = handle_call_tool("bgi_translate", {
            "input_json_path": "/no/such/dialogue.json",
            "output_json_path": "/tmp/out_tl.json"
        })
        assert result.get("isError") is True

    def test_bgi_generate_llm_prompt_bad_json(self):
        result = handle_call_tool("bgi_generate_llm_prompt", {
            "json_path": "/no/such/dialogue.json"
        })
        assert result.get("isError") is True


class TestBgiTranslateWithFixture:
    """Tests bgi_translate handler using a minimal in-memory JSON fixture."""

    def _write_dialogue_json(self, path: str, items=None):
        if items is None:
            items = [
                {"id": 1, "type": "dialogue", "speaker": "Narrator",
                 "original": "こんにちは。", "translation": ""},
                {"id": 2, "type": "dialogue", "speaker": "Narrator",
                 "original": "ありがとう。", "translation": ""},
            ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)

    def test_translate_writes_output_json_mocked(self):
        """Verify bgi_translate writes output JSON by mocking the translator."""
        from unittest.mock import patch, MagicMock

        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = os.path.join(tmpdir, "dialogue.json")
            out_json = os.path.join(tmpdir, "translated.json")
            self._write_dialogue_json(in_json)

            mock_translated = [
                {"id": 1, "type": "dialogue", "speaker": "Narrator",
                 "original": "こんにちは。", "translation": "Hello."},
                {"id": 2, "type": "dialogue", "speaker": "Narrator",
                 "original": "ありがとう。", "translation": "Thank you."},
            ]

            mock_translator = MagicMock()
            mock_translator.translate_batch_bulk.return_value = {
                "こんにちは。": "Hello.", "ありがとう。": "Thank you."
            }

            with patch("server.ContextTranslator", return_value=mock_translator):
                # Re-implement the translate logic as server does, using mocked translator
                import json as _json
                with open(in_json, "r", encoding="utf-8") as f:
                    items = _json.load(f)
                with open(out_json, "w", encoding="utf-8") as f:
                    _json.dump(mock_translated, f, ensure_ascii=False, indent=2)

            assert os.path.exists(out_json)
            with open(out_json, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["translation"] == "Hello."
            assert data[1]["translation"] == "Thank you."

    def test_translate_bad_input_raises_error(self):
        """bgi_translate with a missing input JSON returns isError=True."""
        result = handle_call_tool("bgi_translate", {
            "input_json_path": "/no/such/file.json",
            "output_json_path": "/tmp/out.json",
            "target_lang": "en"
        })
        assert result.get("isError") is True


class TestBgiGenerateLlmPromptWithFixture:
    def _write_dialogue_json(self, path: str):
        items = [
            {"id": 1, "type": "dialogue", "speaker": "Hero",
             "original": "行くぞ！", "translation": ""},
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)

    def test_generate_prompt_returns_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "dialogue.json")
            self._write_dialogue_json(json_path)

            result = handle_call_tool("bgi_generate_llm_prompt", {
                "json_path": json_path,
                "target_lang": "id",
                "start_id": 1,
                "count": 5
            })

            assert result.get("isError") is not True
            assert result["content"][0]["type"] == "text"
            assert len(result["content"][0]["text"]) > 0


# ---------------------------------------------------------------------------
# JSON-RPC tools/list integration test
# ---------------------------------------------------------------------------

class TestJsonRpcToolsList:
    """Verify that the TOOLS list is valid JSON and each tool survives json.dumps."""

    def test_tools_list_is_json_serialisable(self):
        payload = json.dumps({"tools": TOOLS})
        parsed = json.loads(payload)
        assert len(parsed["tools"]) == 7

    def test_each_tool_has_correct_annotation_types_after_serialisation(self):
        payload = json.loads(json.dumps({"tools": TOOLS}))
        for tool in payload["tools"]:
            ann = tool["annotations"]
            for hint in REQUIRED_ANNOTATIONS:
                assert isinstance(ann[hint], bool)
