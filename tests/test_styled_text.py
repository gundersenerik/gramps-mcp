"""
Regression tests for Gramps StyledText handling.

Covers upstream issues #29 and #30: the Gramps Web API returns a note's
``text`` and ``type`` as a StyledText mapping rather than a plain string.
Callers slice and measure those values, and slicing a mapping raises
"unhashable type: 'slice'", which crashed get_type for every person or
family that had a note attached.
"""

from src.gramps_mcp.utils import styled_text_to_string


class TestStyledTextToString:
    """Unwrapping the StyledText shape the API actually returns."""

    def test_styled_text_mapping_yields_inner_string(self):
        note_text = {
            "_class": "StyledText",
            "string": "Husforhorslangd 1855, Ryssby",
            "tags": [],
        }
        assert styled_text_to_string(note_text) == "Husforhorslangd 1855, Ryssby"

    def test_plain_string_passes_through_unchanged(self):
        assert styled_text_to_string("already a string") == "already a string"

    def test_mapping_without_string_key_yields_empty_string(self):
        assert styled_text_to_string({"_class": "StyledText", "tags": []}) == ""

    def test_empty_string_is_preserved(self):
        assert styled_text_to_string("") == ""

    def test_result_is_sliceable(self):
        # The actual defect: the crash was a slice against the mapping.
        note_text = {"_class": "StyledText", "string": "x" * 120, "tags": []}
        unwrapped = styled_text_to_string(note_text)
        assert unwrapped[:50] == "x" * 50
        assert len(unwrapped) == 120

    def test_raw_mapping_is_not_sliceable(self):
        # Guards the premise: without unwrapping, this is the reported error.
        note_text = {"_class": "StyledText", "string": "text", "tags": []}
        try:
            note_text[:50]
        except TypeError as error:
            assert "unhashable type" in str(error)
        else:
            raise AssertionError("slicing a mapping should raise TypeError")
