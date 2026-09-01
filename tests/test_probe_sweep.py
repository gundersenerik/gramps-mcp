"""
Tests for deciding what the sweep may delete.

The sweep removes records from a live tree, so what it selects is the part
worth pinning down. Both functions are pure, so no client is involved.
"""

from scripts.probe_sweep import MARKER, family_is_ours, is_marked


class TestIsMarked:
    """Only records carrying the marker are ours."""

    def test_marker_in_a_name_is_found(self):
        person = {"primary_name": {"surname_list": [{"surname": MARKER}]}}
        assert is_marked(person) is True

    def test_marker_in_a_nested_value_is_found(self):
        assert is_marked({"attribute_list": [{"value": f"{MARKER}-A"}]}) is True

    def test_a_real_record_is_not_touched(self):
        person = {"primary_name": {"surname_list": [{"surname": "Andersson"}]}}
        assert is_marked(person) is False

    def test_empty_record_is_not_ours(self):
        assert is_marked({}) is False


class TestFamilyIsOurs:
    """A family has no marker of its own, so membership decides."""

    def test_family_of_only_test_children_is_ours(self):
        family = {"child_ref_list": [{"ref": "a"}, {"ref": "b"}]}
        assert family_is_ours(family, {"a", "b"}) is True

    def test_family_with_one_real_member_is_left_alone(self):
        # The safety rule: one unmarked person protects the whole family.
        family = {"child_ref_list": [{"ref": "a"}, {"ref": "real"}]}
        assert family_is_ours(family, {"a", "b"}) is False

    def test_real_parent_protects_the_family(self):
        family = {"father_handle": "real", "child_ref_list": [{"ref": "a"}]}
        assert family_is_ours(family, {"a"}) is False

    def test_test_parents_count_as_members(self):
        family = {"father_handle": "a", "mother_handle": "b"}
        assert family_is_ours(family, {"a", "b"}) is True

    def test_family_referencing_nobody_is_not_ours(self):
        # Without members there is no evidence, so it is left alone.
        assert family_is_ours({}, {"a"}) is False

    def test_malformed_child_ref_is_ignored(self):
        family = {"child_ref_list": [{"ref": "a"}, "not-a-mapping"]}
        assert family_is_ours(family, {"a"}) is True
