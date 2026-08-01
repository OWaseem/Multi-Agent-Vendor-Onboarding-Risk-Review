---
doc_type: risk_scoring_rubric
risk_tier: general
default_category: general
---

# Risk Scoring Criteria / Rubric

## Risk Flag Severities

category: general

Each high-risk criterion contributes a severity weight to the vendor's risk
score. Sanctions or watchlist matches are the most severe at 45 points and
escalate a case on their own. A missing security questionnaire contributes 20
points. A foreign (non-US) entity and a missing certificate of insurance each
contribute 15 points. A new vendor in a data-sensitive category contributes
10 points.

## Inherent Category Risk

category: general

IT/Software vendors carry 20 inherent risk points because they touch software
and systems. Any vendor flagged data-sensitive carries 15 inherent risk
points. These are added to the flag severities.

## Escalation Threshold

category: general

A total risk score at or above 30 escalates the case to human review. Below
30, a vendor may be approved for standard onboarding when no risk flags are
present. A single sanctions/watchlist hit (45 points) always exceeds the
threshold.

## Standard Onboarding Definition

category: general

A vendor qualifies for standard onboarding when it has no risk flags, a
complete document set, a country of operation inside the US, and no elevated
inherent category risk. Standard onboarding auto-completes without human
review.

## Revision Guidance

category: general

When the reviewer sends a recommendation back for revision, the planner must
recompute the risk profile and correct the recommended path. If the vendor's
score and flags are unchanged and below the escalation threshold, the revised
recommendation should be the standard path.
