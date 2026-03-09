"""Tests for script tag escaping and HTML entity escaping."""
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from render_review_pack import _escape_script_closing, esc

# ── _escape_script_closing ────────────────────────────────────────────


class TestEscapeScriptClosing:

    def test_escape_script_closing_tag(self):
        """</script> should be escaped to <\\/script>."""
        text = 'some text </script> more text'
        result = _escape_script_closing(text)
        assert "</script" not in result
        assert r"<\/script" in result

    def test_escape_script_case_insensitive(self):
        """</Script> (capital S) should also be escaped."""
        text = 'some text </Script> more text'
        result = _escape_script_closing(text)
        assert "</Script" not in result
        assert r"<\/Script" in result

    def test_safe_text_unchanged(self):
        """Text without script closing tags passes through unchanged."""
        text = "Hello world, no script tags here."
        result = _escape_script_closing(text)
        assert result == text

    def test_multiple_occurrences(self):
        """Multiple </script> occurrences are all escaped."""
        text = 'a</script>b</script>c</script>d'
        result = _escape_script_closing(text)
        assert "</script" not in result
        assert result.count(r"<\/script") == 3

    def test_script_opening_tag_preserved(self):
        """<script> opening tags should NOT be modified."""
        text = '<script>var x = 1;</script>'
        result = _escape_script_closing(text)
        assert "<script>" in result
        assert result.startswith("<script>")

    def test_mixed_case_variants(self):
        """Both </script and </Script are escaped."""
        text = '</script>and</Script>'
        result = _escape_script_closing(text)
        assert "</script" not in result
        assert "</Script" not in result
        assert r"<\/script" in result
        assert r"<\/Script" in result

    def test_empty_string(self):
        result = _escape_script_closing("")
        assert result == ""

    def test_script_with_attributes(self):
        """</script type='text/javascript'> (unusual but possible) should be escaped."""
        text = "</script type='text/javascript'>"
        result = _escape_script_closing(text)
        assert r"<\/script" in result


# ── esc (HTML entity escaping) ────────────────────────────────────────


class TestEscHtmlEntities:

    def test_escapes_less_than(self):
        assert "&lt;" in esc("<div>")

    def test_escapes_greater_than(self):
        assert "&gt;" in esc("value > 0")

    def test_escapes_ampersand(self):
        assert "&amp;" in esc("a & b")

    def test_escapes_double_quote(self):
        assert "&quot;" in esc('key="value"')

    def test_plain_text_unchanged(self):
        assert esc("Hello World") == "Hello World"

    def test_all_entities_combined(self):
        result = esc('<a href="url">&test</a>')
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
        assert "<" not in result.replace("&lt;", "").replace("&gt;", "")

    def test_non_string_converted(self):
        """Non-string input should be converted via str() first."""
        result = esc(42)
        assert result == "42"

    def test_empty_string(self):
        assert esc("") == ""
