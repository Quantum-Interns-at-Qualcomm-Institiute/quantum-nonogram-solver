"""Tests for nonogram.data — validate the precomputed lookup table possible_d."""

import re

import pytest

from nonogram.core import rle
from nonogram.data import possible_d

# The key format regex: "length/clue;clue;...;" where length and clues are ints.
KEY_PATTERN = re.compile(r"^(\d+)/((?:\d+;)+)$")


def _bitstring_to_bits(bitstring: int, length: int) -> list[bool]:
    """Convert an integer bitstring to a list of bools, LSB = leftmost cell.

    The data table uses the convention that bit position 0 (LSB)
    corresponds to the leftmost cell, matching core.py's encoding
    where ``1 << pos`` and pos=0 is the first cell in a line.
    """
    return [bool(bitstring & (1 << i)) for i in range(length)]


def _rle_from_int(bitstring: int, length: int) -> tuple[int, ...]:
    """Run-length encode an integer bitstring into clue tuple."""
    bits = _bitstring_to_bits(bitstring, length)
    groups: list[int] = []
    count = 0
    for b in bits:
        if b:
            count += 1
        elif count:
            groups.append(count)
            count = 0
    if count:
        groups.append(count)
    return tuple(groups) if groups else (0,)


def _parse_key(key: str) -> tuple[int, tuple[int, ...]]:
    """Parse a possible_d key into (length, clue_tuple)."""
    m = KEY_PATTERN.match(key)
    assert m, f"Key does not match expected format: {key!r}"
    length = int(m.group(1))
    clue = tuple(int(c) for c in m.group(2).rstrip(";").split(";"))
    return length, clue


# ---------------------------------------------------------------------------
# 1. Key format validation
# ---------------------------------------------------------------------------


class TestKeyFormat:
    def test_all_keys_match_format(self):
        for key in possible_d:
            m = KEY_PATTERN.match(key)
            assert m is not None, f"Key does not match expected format: {key!r}"

    def test_all_keys_have_positive_length(self):
        for key in possible_d:
            length, _ = _parse_key(key)
            assert length >= 1, f"Key has non-positive length: {key!r}"

    def test_all_clue_values_are_non_negative(self):
        for key in possible_d:
            _, clue = _parse_key(key)
            for c in clue:
                assert c >= 0, f"Key has negative clue value: {key!r}"


# ---------------------------------------------------------------------------
# 2. Coverage of lengths 1-6
# ---------------------------------------------------------------------------


class TestLengthCoverage:
    @pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 6])
    def test_length_present(self, length):
        keys_for_length = [k for k in possible_d if k.startswith(f"{length}/")]
        assert len(keys_for_length) > 0, (
            f"No keys found for length {length}"
        )


# ---------------------------------------------------------------------------
# 3. Every bitstring satisfies its clue
# ---------------------------------------------------------------------------


class TestBitstringSatisfiesClue:
    @pytest.mark.parametrize("key", list(possible_d.keys()))
    def test_all_patterns_match_clue(self, key):
        length, clue = _parse_key(key)
        for pattern in possible_d[key]:
            computed_clue = _rle_from_int(pattern, length)
            assert computed_clue == clue, (
                f"Key {key!r}: pattern {pattern:#0{length + 2}b} "
                f"has RLE {computed_clue}, expected {clue}"
            )


# ---------------------------------------------------------------------------
# 4. No duplicate patterns within a key
# ---------------------------------------------------------------------------


class TestNoDuplicatePatterns:
    @pytest.mark.parametrize("key", list(possible_d.keys()))
    def test_no_duplicates(self, key):
        patterns = possible_d[key]
        assert len(patterns) == len(set(patterns)), (
            f"Key {key!r} contains duplicate patterns"
        )


# ---------------------------------------------------------------------------
# 5. Empty clue (0,) for each length has exactly one pattern (all zeros)
# ---------------------------------------------------------------------------


class TestEmptyClue:
    @pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 6])
    def test_empty_clue_single_zero_pattern(self, length):
        key = f"{length}/0;"
        assert key in possible_d, f"Missing empty clue key: {key!r}"
        patterns = possible_d[key]
        assert len(patterns) == 1, (
            f"Empty clue {key!r} should have exactly 1 pattern, got {len(patterns)}"
        )
        assert patterns[0] == 0, (
            f"Empty clue {key!r} pattern should be 0, got {patterns[0]}"
        )


# ---------------------------------------------------------------------------
# 6. Full clue (length,) for each length has exactly one pattern (all ones)
# ---------------------------------------------------------------------------


class TestFullClue:
    @pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 6])
    def test_full_clue_single_all_ones_pattern(self, length):
        key = f"{length}/{length};"
        assert key in possible_d, f"Missing full clue key: {key!r}"
        patterns = possible_d[key]
        assert len(patterns) == 1, (
            f"Full clue {key!r} should have exactly 1 pattern, got {len(patterns)}"
        )
        expected = (1 << length) - 1
        assert patterns[0] == expected, (
            f"Full clue {key!r} pattern should be {expected:#0{length + 2}b}, "
            f"got {patterns[0]:#0{length + 2}b}"
        )


# ---------------------------------------------------------------------------
# 7. Pattern completeness - no valid pattern is missing
# ---------------------------------------------------------------------------


class TestPatternCompleteness:
    @pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 6])
    def test_exhaustive_completeness(self, length):
        """For each length, exhaustively check all 2^length bitstrings.

        Every bitstring's RLE must correspond to a key in possible_d, and
        the bitstring must appear in the pattern list for that key.
        """
        for bitstring in range(1 << length):
            clue = _rle_from_int(bitstring, length)
            key = f"{length}/{';'.join(map(str, clue))};"
            assert key in possible_d, (
                f"Missing key {key!r} for bitstring {bitstring:#0{length + 2}b}"
            )
            assert bitstring in possible_d[key], (
                f"Pattern {bitstring:#0{length + 2}b} missing from {key!r}"
            )

    @pytest.mark.parametrize("length", [1, 2, 3, 4, 5, 6])
    def test_no_extra_patterns(self, length):
        """Verify the table has no patterns beyond what exhaustive enumeration produces."""
        # Build expected mapping from exhaustive enumeration
        expected: dict[str, set[int]] = {}
        for bitstring in range(1 << length):
            clue = _rle_from_int(bitstring, length)
            key = f"{length}/{';'.join(map(str, clue))};"
            expected.setdefault(key, set()).add(bitstring)

        # Check every key for this length in possible_d
        for key in possible_d:
            parsed_length, _ = _parse_key(key)
            if parsed_length != length:
                continue
            actual = set(possible_d[key])
            assert key in expected, (
                f"Unexpected key {key!r} in possible_d"
            )
            extra = actual - expected[key]
            assert not extra, (
                f"Key {key!r} has extra patterns: "
                f"{[f'{p:#0{length + 2}b}' for p in extra]}"
            )


# ---------------------------------------------------------------------------
# 8. Cross-reference: core.rle() agrees with the data table
# ---------------------------------------------------------------------------


class TestCrossReferenceRle:
    @pytest.mark.parametrize("key", list(possible_d.keys()))
    def test_core_rle_matches_table(self, key):
        """For every pattern, verify core.rle() produces the clue in the key."""
        length, clue = _parse_key(key)
        for pattern in possible_d[key]:
            bits = _bitstring_to_bits(pattern, length)
            assert rle(bits) == clue, (
                f"Key {key!r}: core.rle({bits}) returned {rle(bits)}, "
                f"expected {clue}"
            )
