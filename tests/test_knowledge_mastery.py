"""Tests for knowledge mastery calculation rules."""

from datetime import datetime, timezone

from app.models.knowledge_point import MasteryStatus
from app.services.knowledge_mastery_service import (
    calculate_mastery_status,
    calculate_next_review_at,
)


def test_calculate_mastery_status_from_accuracy():
    assert calculate_mastery_status(answered_count=0, accuracy=0.0) == MasteryStatus.unlearned
    assert calculate_mastery_status(answered_count=3, accuracy=0.5) == MasteryStatus.weak
    assert calculate_mastery_status(answered_count=3, accuracy=0.75) == MasteryStatus.basic
    assert calculate_mastery_status(answered_count=3, accuracy=0.9) == MasteryStatus.proficient


def test_calculate_next_review_at_uses_spaced_intervals():
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)

    assert (calculate_next_review_at(mastery_status=MasteryStatus.weak, now=now) - now).days == 1
    assert (calculate_next_review_at(mastery_status=MasteryStatus.basic, now=now) - now).days == 3
    assert (calculate_next_review_at(mastery_status=MasteryStatus.proficient, now=now) - now).days == 7
