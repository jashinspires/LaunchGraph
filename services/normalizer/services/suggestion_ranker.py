"""
Suggestion Ranking Engine.
Computes link suggestion scores using the authoritative 4-factor formula:
Score = 0.35 * S_person + 0.20 * S_time + 0.25 * S_path + 0.20 * S_text
"""

from typing import Dict, Any
from datetime import datetime


class SuggestionRanker:
    """
    Deterministic formula scorer for candidate link attachments.
    """

    WEIGHT_PERSON: float = 0.35
    WEIGHT_TIME: float = 0.20
    WEIGHT_PATH: float = 0.25
    WEIGHT_TEXT: float = 0.20

    @classmethod
    def calculate_score(
        cls,
        same_person: bool,
        time_delta_hours: float,
        path_match_score: float,
        text_similarity_score: float
    ) -> Dict[str, Any]:
        """
        Calculates normalized composite score bounded between 0.0 and 1.0.
        """
        # S_person: 1.0 if same author/assignee, else 0.0
        s_person = 1.0 if same_person else 0.0

        # S_time: Exponential decay over time (within 24h = ~1.0, 7 days = ~0.2)
        if time_delta_hours <= 0:
            s_time = 1.0
        elif time_delta_hours < 24:
            s_time = max(0.0, 1.0 - (time_delta_hours / 48.0))
        elif time_delta_hours < 168:  # 7 days
            s_time = max(0.1, 0.5 - ((time_delta_hours - 24) / 288.0))
        else:
            s_time = 0.0

        # S_path: file paths / repository proximity [0.0 - 1.0]
        s_path = max(0.0, min(1.0, float(path_match_score)))

        # S_text: title / keyword similarity [0.0 - 1.0]
        s_text = max(0.0, min(1.0, float(text_similarity_score)))

        total_score = (
            cls.WEIGHT_PERSON * s_person +
            cls.WEIGHT_TIME * s_time +
            cls.WEIGHT_PATH * s_path +
            cls.WEIGHT_TEXT * s_text
        )

        total_score = round(max(0.0, min(1.0, total_score)), 4)

        return {
            "score": total_score,
            "feature_breakdown": {
                "s_person": s_person,
                "s_time": round(s_time, 4),
                "s_path": round(s_path, 4),
                "s_text": round(s_text, 4)
            }
        }
