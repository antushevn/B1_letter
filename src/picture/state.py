from typing import TypedDict

from ..letter.state import Error


class PictureCriterionScores(TypedDict):
    task_fulfillment: str      # A / B / C / D  (Aufgabenbewältigung)
    vocabulary: str            # Wortschatz
    accuracy: str              # Korrektheit


class PictureState(TypedDict):
    language: str              # UI / feedback language code, e.g. "ru" / "de" / "en"
    picture_id: str
    picture_file: str          # filename inside data/pictures/
    scene: str                 # German scene label, e.g. "Beim Arzt"
    description: str           # the learner's written description
    feedback: str
    score: str                 # Pass / Borderline / Fail
    criterion_scores: PictureCriterionScores
    positives: list[str]
    missing_steps: list[str]   # structure steps not covered (overview/details/…)
    errors: list[Error]
