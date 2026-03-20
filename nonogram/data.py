"""
Precomputed lookup table for nonogram constraint satisfiability.

This module provides a lookup table ``possible_d`` that maps nonogram clues
to all valid bitstring configurations. It is used by the SAT encoding in
``nonogram.core.puzzle_to_boolean`` to quickly enumerate the valid patterns
for each row and column constraint.

**Data format:**
  - Key: ``"length/clue_1;clue_2;...;"`` (e.g., ``"4/1;2;"`` for a 4-cell line with clues 1 and 2)
  - Value: List of valid bitstring configurations as integers (bit index 0 = leftmost cell)

**Coverage:** Line lengths 1–6 (supports up to 6×6 nonogram puzzles)

**Example:**

    >>> from nonogram.data import possible_d
    >>> possible_d["3/1;1;"]  # 3-cell line with blocks of 1, 1
    [0b101]  # only one valid pattern: filled, empty, filled

The lookup table is precomputed at module load time for O(1) constraint lookup
during SAT formula generation, avoiding expensive runtime pattern generation.
"""

possible_d: dict[str, list[int]] = {
    # l = 1
    "1/0;": [0b0],
    "1/1;": [0b1],

    # l = 2
    "2/0;": [0b00],
    "2/1;": [0b01, 0b10],
    "2/2;": [0b11],

    # l = 3
    "3/0;": [0b000],
    "3/1;": [0b100, 0b010, 0b001],
    "3/2;": [0b110, 0b011],
    "3/3;": [0b111],
    "3/1;1;": [0b101],

    # l = 4
    "4/0;": [0b0000],
    "4/1;": [0b1000, 0b0100, 0b0010, 0b0001],
    "4/2;": [0b1100, 0b0110, 0b0011],
    "4/3;": [0b1110, 0b0111],
    "4/4;": [0b1111],
    "4/1;1;": [0b1010, 0b0101, 0b1001],
    "4/2;1;": [0b1101],
    "4/1;2;": [0b1011],

    # l = 5
    "5/0;": [0b00000],
    "5/1;": [0b10000, 0b01000, 0b00100, 0b00010, 0b00001],
    "5/2;": [0b11000, 0b01100, 0b00110, 0b00011],
    "5/3;": [0b11100, 0b01110, 0b00111],
    "5/4;": [0b11110, 0b01111],
    "5/5;": [0b11111],
    "5/1;1;": [0b10100, 0b10010, 0b10001, 0b01010, 0b01001, 0b00101],
    "5/1;2;": [0b10011, 0b10110, 0b01011],
    "5/1;3;": [0b10111],
    "5/2;1;": [0b11001, 0b11010, 0b01101],
    "5/2;2;": [0b11011],
    "5/3;1;": [0b11101],
    "5/1;1;1;": [0b10101],

    # l = 6
    "6/0;": [0b000000],
    "6/1;": [0b100000, 0b010000, 0b001000, 0b000100, 0b000010, 0b000001],
    "6/2;": [0b110000, 0b011000, 0b001100, 0b000110, 0b000011],
    "6/3;": [0b111000, 0b011100, 0b001110, 0b000111],
    "6/4;": [0b111100, 0b011110, 0b001111],
    "6/5;": [0b111110, 0b011111],
    "6/6;": [0b111111],
    "6/1;1;": [
        0b101000, 0b100100, 0b100010, 0b100001,
        0b010100, 0b010010, 0b010001, 0b001010,
        0b001001, 0b000101,
    ],
    "6/1;2;": [0b101100, 0b100110, 0b100011, 0b010110, 0b010011, 0b001011],
    "6/1;3;": [0b101110, 0b100111, 0b010111],
    "6/1;4;": [0b101111],
    "6/2;1;": [0b110100, 0b110010, 0b110001, 0b011010, 0b011001, 0b001101],
    "6/2;2;": [0b110110, 0b110011, 0b011011],
    "6/2;3;": [0b110111],
    "6/3;1;": [0b111010, 0b111001, 0b011101],
    "6/3;2;": [0b111011],
    "6/4;1;": [0b111101],
    "6/1;1;1;": [0b101010, 0b101001, 0b100101, 0b010101],
    "6/1;1;2;": [0b101011],
    "6/1;2;1;": [0b101101],
    "6/2;1;1;": [0b110101],
}
