"""
Unit tests for Suggestion Ranking Formula.
"""

from services.normalizer.services.suggestion_ranker import SuggestionRanker


def test_suggestion_ranker_perfect_match():
    # Same person (1.0), within 1 hour (1.0), full path match (1.0), high text similarity (1.0)
    result = SuggestionRanker.calculate_score(
        same_person=True,
        time_delta_hours=1.0,
        path_match_score=1.0,
        text_similarity_score=1.0
    )
    score = result["score"]
    assert score > 0.95
    assert result["feature_breakdown"]["s_person"] == 1.0


def test_suggestion_ranker_low_match():
    # Different person (0.0), 10 days apart (>168h -> 0.0), no path match (0.0), low text similarity (0.1)
    result = SuggestionRanker.calculate_score(
        same_person=False,
        time_delta_hours=240.0,
        path_match_score=0.0,
        text_similarity_score=0.1
    )
    score = result["score"]
    assert score <= 0.05
    assert result["feature_breakdown"]["s_person"] == 0.0
    assert result["feature_breakdown"]["s_time"] == 0.0
