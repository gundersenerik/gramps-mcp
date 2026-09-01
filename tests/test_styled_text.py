"""
Regression tests for Gramps StyledText handling.

Covers upstream issues #29 and #30: the Gramps Web API returns a note's
``text`` and ``type`` as a StyledText mapping rather than a plain string.
Callers slice and measure those values, and slicing a mapping raises
"unhashable type: 'slice'", which crashed get_type for every person or
family that had a note attached.
"""

from src.gramps_mcp.utils import format_attribute_lines, styled_text_to_string


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


class TestFormatAttributeLines:
    """Rendering the attribute list that no read path used to show."""

    def test_attribute_is_rendered(self):
        lines = format_attribute_lines(
            [{"type": "Occupation", "value": "Husforhorslangd 1855"}]
        )
        assert lines == "- Occupation: Husforhorslangd 1855\n"

    def test_styled_text_type_is_unwrapped(self):
        lines = format_attribute_lines(
            [
                {
                    "type": {"_class": "AttributeType", "string": "Occupation"},
                    "value": "Bonde",
                }
            ]
        )
        assert lines == "- Occupation: Bonde\n"

    def test_empty_list_says_none_rather_than_nothing(self):
        # A failed write must not look like a record that never had one.
        assert format_attribute_lines([]) == "- none\n"

    def test_missing_list_says_none(self):
        assert format_attribute_lines(None) == "- none\n"

    def test_every_attribute_is_listed(self):
        lines = format_attribute_lines(
            [
                {"type": "Occupation", "value": "Bonde"},
                {"type": "Occupation", "value": "Bonde"},
            ]
        )
        # Duplicates are shown as duplicates: the merge behaviour is visible.
        assert lines.count("- Occupation: Bonde\n") == 2

    def test_missing_value_renders_empty(self):
        assert format_attribute_lines([{"type": "Occupation"}]) == "- Occupation: \n"
