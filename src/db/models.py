"""Dataclass models for the DeutschMeister database layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    """A DeutschMeister learner."""

    id: int
    telegram_id: str
    display_name: str | None
    cefr_level: str
    timezone: str
    native_language: str
    daily_goal_minutes: int
    preferred_lesson_time: str
    interests: str | None
    onboarding_complete: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> User:
        """Construct a User from a database row dict."""
        return cls(
            id=row["id"],
            telegram_id=row["telegram_id"],
            display_name=row["display_name"],
            cefr_level=row["cefr_level"],
            timezone=row["timezone"],
            native_language=row["native_language"],
            daily_goal_minutes=row["daily_goal_minutes"],
            preferred_lesson_time=row["preferred_lesson_time"],
            interests=row["interests"],
            onboarding_complete=bool(row["onboarding_complete"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class VocabCard:
    """A spaced-repetition vocabulary card."""

    id: int
    user_id: int
    word_de: str
    word_en: str
    gender: str | None
    plural: str | None
    part_of_speech: str | None
    example_sentence: str | None
    interval_days: int
    ease_factor: float
    next_review: str | None
    review_count: int
    correct_count: int
    audio_cached: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> VocabCard:
        """Construct a VocabCard from a database row dict."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            word_de=row["word_de"],
            word_en=row["word_en"],
            gender=row["gender"],
            plural=row["plural"],
            part_of_speech=row["part_of_speech"],
            example_sentence=row["example_sentence"],
            interval_days=row["interval_days"],
            ease_factor=row["ease_factor"],
            next_review=row["next_review"],
            review_count=row["review_count"],
            correct_count=row["correct_count"],
            audio_cached=bool(row["audio_cached"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class LessonRecord:
    """A record of a completed (or in-progress) lesson."""

    id: int
    user_id: int
    lesson_date: str
    block: int | None
    story_type: str | None
    theme: str | None
    grammar_topic: str | None
    duration_minutes: int | None
    completed: bool
    notes: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> LessonRecord:
        """Construct a LessonRecord from a database row dict."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            lesson_date=row["lesson_date"],
            block=row["block"],
            story_type=row["story_type"],
            theme=row["theme"],
            grammar_topic=row["grammar_topic"],
            duration_minutes=row["duration_minutes"],
            completed=bool(row["completed"]),
            notes=row["notes"],
            created_at=row["created_at"],
        )


@dataclass
class UserProgress:
    """Curriculum progress for a single user."""

    id: int
    user_id: int
    cefr_level: str
    theme_index: int
    grammar_index: int
    phase: int
    week_number: int
    words_learned: int
    lessons_completed: int
    current_streak: int
    longest_streak: int
    last_lesson_date: str | None
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> UserProgress:
        """Construct a UserProgress from a database row dict."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            cefr_level=row["cefr_level"],
            theme_index=row["theme_index"],
            grammar_index=row["grammar_index"],
            phase=row["phase"],
            week_number=row["week_number"],
            words_learned=row["words_learned"],
            lessons_completed=row["lessons_completed"],
            current_streak=row["current_streak"],
            longest_streak=row["longest_streak"],
            last_lesson_date=row["last_lesson_date"],
            updated_at=row["updated_at"],
        )
