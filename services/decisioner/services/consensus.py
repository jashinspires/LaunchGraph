"""
Consensus Engine for Stage 3 Decisioning.
Executes k=3 temperature sampling over the Judgment interface, computes raw agreement score,
derives consensus tier, calculates confidence bands, and packages answers into JudgmentConsensus.
"""

from collections import Counter
from typing import List, Dict, Any
from launchgraph_core.contracts.decisioner import (
    EvidencePack,
    JudgmentConsensus,
    QuestionAnswer,
    ConfidenceBand,
    LaunchTier,
)
from services.decisioner.services.fact_extractor import ChangeFacts
from services.decisioner.services.judgment_client import BaseJudgmentClient


class ConsensusEngine:
    """
    Executes k=3 sampling across temperature variation to achieve robust consensus
    and compute confidence bands (high, medium, low).
    """

    TEMPERATURE_LADDER = [0.0, 0.3, 0.7]

    @classmethod
    async def evaluate_consensus(
        cls,
        client: BaseJudgmentClient,
        pack: EvidencePack,
        facts: ChangeFacts,
        k_samples: int = 3
    ) -> JudgmentConsensus:
        samples_results: List[Dict[str, QuestionAnswer]] = []
        raw_samples_list: List[Dict[str, Any]] = []

        for i in range(k_samples):
            temp = cls.TEMPERATURE_LADDER[i % len(cls.TEMPERATURE_LADDER)]
            answers = await client.evaluate_sample(
                pack=pack,
                facts=facts,
                sample_index=i,
                temperature=temp
            )
            samples_results.append(answers)
            raw_samples_list.append({
                "sample_index": i,
                "temperature": temp,
                "q9_tier": answers["Q9"].answer,
                "answers": {q_id: a.model_dump() for q_id, a in answers.items()}
            })

        # 1. Consensus on Q9 Launch Tier
        tier_votes = [res["Q9"].answer for res in samples_results]
        vote_counter = Counter(tier_votes)
        consensus_tier_val, top_count = vote_counter.most_common(1)[0]
        consensus_tier = LaunchTier(consensus_tier_val)

        # 2. Raw Agreement Score
        agreement_score = round(top_count / k_samples, 2)

        # 3. Overall Confidence Band
        if agreement_score >= 0.9:
            confidence = ConfidenceBand.HIGH
        elif agreement_score >= 0.6:
            confidence = ConfidenceBand.MEDIUM
        else:
            confidence = ConfidenceBand.LOW

        # 4. Numeric Impact Score (1-100)
        base_scores = {
            LaunchTier.T1: 90,
            LaunchTier.T2: 70,
            LaunchTier.T3: 45,
            LaunchTier.T0: 15
        }
        base = base_scores.get(consensus_tier, 50)
        # Add modifier based on facts
        modifier = 0
        if facts.has_customer_docs:
            modifier += 5
        if facts.changed_files_count > 10:
            modifier += 5
        if facts.is_breaking_change:
            modifier += 5
        if confidence == ConfidenceBand.LOW:
            modifier -= 10

        final_score = max(1, min(100, base + modifier))

        # 5. Compile representative answers (from primary sample or consensus)
        primary_answers = samples_results[0]
        compiled_answers: List[QuestionAnswer] = []
        for q_id, ans in primary_answers.items():
            if q_id == "Q9":
                ans.answer = consensus_tier.value
                ans.confidence = confidence
            compiled_answers.append(ans)

        return JudgmentConsensus(
            k_samples=k_samples,
            consensus_tier=consensus_tier,
            confidence=confidence,
            score=final_score,
            answers=compiled_answers,
            raw_samples=raw_samples_list,
            agreement_score=agreement_score
        )

