from typing import TypedDict


class Error(TypedDict):
    original: str
    correction: str
    explanation: str


class CriterionScores(TypedDict):
    content: str               # A / B / C / D
    communicative_structure: str
    linguistic_accuracy: str


class PracticeState(TypedDict):
    topic: str
    user_letter: str
    feedback: str
    score: str                 # Pass / Borderline / Fail
    criterion_scores: CriterionScores
    positives: list[str]
    errors: list[Error]
    missing_points: list[str]
