"""Progress tracking logic for CEFR curriculum.

Pure logic module — no database imports. Computes curriculum positions,
completion status, and index advancement for the CEFR A1-B1 levels.
"""

from __future__ import annotations

from dataclasses import dataclass

# A1 curriculum constants (from curriculum/a1.md)
A1_THEMES = 15
A1_GRAMMAR_TOPICS = 15
A1_PHASES = 5  # Foundation, Core, Communication, Expansion, Consolidation

CURRICULUM: dict[str, dict[str, int]] = {
    "A1": {"themes": A1_THEMES, "grammar": A1_GRAMMAR_TOPICS, "phases": A1_PHASES},
    # A2 and B1 will be added when their curriculum files are created
}


@dataclass
class CurriculumPosition:
    """Snapshot of a student's position within a CEFR level."""

    cefr_level: str
    theme_index: int
    grammar_index: int
    phase: int
    week_number: int
    is_level_complete: bool


def get_position(
    cefr_level: str,
    theme_index: int,
    grammar_index: int,
    phase: int,
    week_number: int,
) -> CurriculumPosition:
    """Get current curriculum position with completion status.

    Args:
        cefr_level: CEFR level string (e.g. ``"A1"``).
        theme_index: Current vocabulary theme index (0-based).
        grammar_index: Current grammar topic index (0-based).
        phase: Current phase number (1-based).
        week_number: Current week number (1-based).

    Returns:
        A :class:`CurriculumPosition` with clamped indices and completion flag.
    """
    level_info = CURRICULUM.get(cefr_level, CURRICULUM["A1"])
    is_complete = (
        theme_index >= level_info["themes"]
        and grammar_index >= level_info["grammar"]
    )
    return CurriculumPosition(
        cefr_level=cefr_level,
        theme_index=min(theme_index, level_info["themes"]),
        grammar_index=min(grammar_index, level_info["grammar"]),
        phase=phase,
        week_number=week_number,
        is_level_complete=is_complete,
    )


def compute_advance(
    current_theme: int,
    current_grammar: int,
    advance_what: str,
    cefr_level: str = "A1",
) -> tuple[int, int]:
    """Compute new indices after advancing one step.

    Args:
        current_theme: Current vocabulary theme index (0-based).
        current_grammar: Current grammar topic index (0-based).
        advance_what: ``"theme"`` or ``"grammar"``.
        cefr_level: CEFR level string (e.g. ``"A1"``).

    Returns:
        A ``(new_theme, new_grammar)`` tuple with the advanced index
        capped at the level maximum.
    """
    level_info = CURRICULUM.get(cefr_level, CURRICULUM["A1"])
    if advance_what == "theme":
        return min(current_theme + 1, level_info["themes"]), current_grammar
    elif advance_what == "grammar":
        return current_theme, min(current_grammar + 1, level_info["grammar"])
    return current_theme, current_grammar
