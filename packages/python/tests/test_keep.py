from __future__ import annotations

import pickle
import re

import pytest

from commentless.keep import (
    DEFAULT_KEEP_RULES,
    KEEP_RULE_DESCRIPTIONS,
    KEEP_RULE_NAMES,
    UnknownKeepRuleError,
    apply_keep_next_line,
    deserialize_keep_rules,
    has_ignore_file_marker,
    match_keep_rule,
    resolve_keep_rules,
    serialize_keep_rules,
    signature_of_keep_rules,
)
from commentless.types import Comment


def comment(text: str, *, line: int = 1, kind: str = "comment") -> Comment:
    return Comment(start=0, end=len(text), line=line, column=1, kind=kind, text=text)  # type: ignore[arg-type]


class TestRuleTable:
    def test_every_rule_name_is_unique(self) -> None:
        assert len(set(KEEP_RULE_NAMES)) == len(KEEP_RULE_NAMES)

    def test_every_rule_has_a_description(self) -> None:
        assert set(KEEP_RULE_DESCRIPTIONS) == set(KEEP_RULE_NAMES)

    def test_every_rule_compiles(self) -> None:
        for rule in DEFAULT_KEEP_RULES:
            assert isinstance(rule.test, re.Pattern)


class TestResolveKeepRules:
    def test_returns_the_defaults(self) -> None:
        assert [rule.name for rule in resolve_keep_rules()] == list(KEEP_RULE_NAMES)

    def test_no_defaults_returns_nothing(self) -> None:
        assert resolve_keep_rules(defaults=False) == ()

    def test_only_narrows_to_the_named_rules(self) -> None:
        rules = resolve_keep_rules(only=("noqa", "type-ignore"))
        assert [rule.name for rule in rules] == ["noqa", "type-ignore"]

    def test_disable_removes_a_rule(self) -> None:
        names = [rule.name for rule in resolve_keep_rules(disable=("noqa",))]
        assert "noqa" not in names
        assert "type-ignore" in names

    def test_user_patterns_are_appended(self) -> None:
        rules = resolve_keep_rules(defaults=False, user_patterns=("LEGAL",))
        assert [rule.name for rule in rules] == ["config:LEGAL"]

    def test_an_unknown_rule_raises(self) -> None:
        with pytest.raises(UnknownKeepRuleError, match="nope"):
            resolve_keep_rules(disable=("nope",))

    def test_an_unknown_only_rule_raises(self) -> None:
        with pytest.raises(UnknownKeepRuleError):
            resolve_keep_rules(only=("nope", "also-nope"))


class TestMatchKeepRule:
    def test_matches_the_first_rule_that_applies(self) -> None:
        assert match_keep_rule(comment("# noqa"), DEFAULT_KEEP_RULES) == "noqa"

    def test_returns_none_for_prose(self) -> None:
        assert match_keep_rule(comment("# just prose"), DEFAULT_KEEP_RULES) is None

    def test_respects_the_kind_restriction(self) -> None:
        doctest = comment('""">>> 1\n1\n"""', kind="docstring")
        assert match_keep_rule(doctest, DEFAULT_KEEP_RULES) == "doctest"

        as_comment = comment("# >>> 1")
        assert match_keep_rule(as_comment, DEFAULT_KEEP_RULES) is None

    def test_respects_the_max_line_restriction(self) -> None:
        cookie = "# -*- coding: utf-8 -*-"
        assert match_keep_rule(comment(cookie, line=2), DEFAULT_KEEP_RULES) == "coding"
        assert match_keep_rule(comment(cookie, line=3), DEFAULT_KEEP_RULES) is None


class TestSerialization:
    def test_round_trips_every_default_rule(self) -> None:
        restored = deserialize_keep_rules(serialize_keep_rules(DEFAULT_KEEP_RULES))
        assert [rule.name for rule in restored] == list(KEEP_RULE_NAMES)
        for original, copy in zip(DEFAULT_KEEP_RULES, restored, strict=True):
            assert copy.test.pattern == original.test.pattern
            assert copy.test.flags == original.test.flags
            assert copy.kinds == original.kinds
            assert copy.max_line == original.max_line

    def test_the_signature_is_stable_and_json_safe(self) -> None:
        import json

        first = signature_of_keep_rules(DEFAULT_KEEP_RULES)
        assert json.dumps(first) == json.dumps(signature_of_keep_rules(DEFAULT_KEEP_RULES))

    def test_rules_survive_a_pickle_round_trip(self) -> None:
        restored = pickle.loads(pickle.dumps(DEFAULT_KEEP_RULES))
        assert [rule.name for rule in restored] == list(KEEP_RULE_NAMES)

    def test_comments_survive_a_pickle_round_trip(self) -> None:
        original = comment("# a note")
        assert pickle.loads(pickle.dumps(original)) == original


class TestMarkers:
    def test_finds_the_ignore_file_marker_near_the_top(self) -> None:
        assert has_ignore_file_marker("# commentless-ignore-file\n") is True

    def test_ignores_the_marker_far_into_the_file(self) -> None:
        assert has_ignore_file_marker("x\n" * 5000 + "# commentless-ignore-file") is False

    def test_keep_next_line_marks_the_following_comment(self) -> None:
        comments = [
            comment("# commentless-keep-next-line"),
            Comment(start=10, end=20, line=2, column=1, kind="comment", text="# next"),
            Comment(start=30, end=40, line=3, column=1, kind="comment", text="# other"),
        ]
        assert apply_keep_next_line(comments) == {10}

    def test_keep_next_line_at_the_end_marks_nothing(self) -> None:
        assert apply_keep_next_line([comment("# commentless-keep-next-line")]) == set()
