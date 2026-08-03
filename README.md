# Multi-Agent Vendor Onboarding & Risk Review

A LangGraph + LangChain multi-agent workflow that takes a new-vendor request from
intake through document/completeness checks, risk & compliance review, and a
human-approval gate, before producing a grounded onboarding decision.

Built for: *Project 2 — Multi-Agent Business Workflow Application*
Presentation: **August 7, ~2:00 PM EST**

Domain: **Option A — Vendor onboarding and risk review**

---

## 1. Business scenario

**Who initiates a request:** An employee (the "requester") who wants their
organization to start working with a new or existing vendor submits a
**New Vendor Request**.

**What's submitted:**

| Field | Example |
|---|---|
| Vendor name | "Acme Cloud Services" |
| Vendor category | IT/Software, Professional Services, Logistics, Facilities, Marketing, Office Supplies |
| Country of operation | US, Germany, etc. |
| Data-sensitivity flag | Will this vendor touch company/customer data or IT systems? |
| Relationship status | New vendor vs. existing/prior vendor |
| Requester contact info | Name, department |
| Attached documents | Whatever the requester has on hand at submission time |

**Required documents** (base set, all vendors):

- W-9 / Tax ID form
- Certificate of Insurance (COI)
- Business license / Articles of incorporation
- Signed vendor code of conduct

**Conditionally required:**

- **Security questionnaire** — required if `vendor_category == IT/Software`
  OR `data_sensitive == true`
- **Banking / ACH form** — required before final "approved" status (not a
  blocker for onboarding review itself)

**High-risk criteria** (any one trips a `risk_flag`, evaluated by the Risk/
Compliance Reviewer against retrieved policy):

- Foreign entity (non-US)
- No Certificate of Insurance on file
- IT/Software category or data-sensitive, but no completed security
  questionnaire
- Appears on the mock sanctions/watchlist
- New vendor (no prior relationship) in a data-sensitive category

**Policy exception path:** the reviewer can recommend a **policy exception**
when a vendor fails a standard criterion but the requester has provided a
credible business justification — this still requires human sign-off.

**Outcomes:**

```text
Standard onboarding (auto-completes)
Missing information — paused, awaiting requester
Escalated to human review (high-risk / exception / retry limit hit)
Rejected
```

---

## 2. Roles (three distinct responsibilities)

| Role | Responsibility | Explicitly NOT responsible for |
|---|---|---|
| **Intake / Document-Completeness Agent** | Checks the submission against the required-document checklist for that vendor's category. Flags missing fields/documents. | Judging risk, recommending a path |
| **Onboarding Planner** | Once the submission is complete, looks up the vendor record and retrieves relevant policy via RAG, then drafts a recommended onboarding path (standard / high-risk / needs-exception) with reasoning. | Final approval, policy compliance sign-off |
| **Risk/Compliance Reviewer (critic)** | Validates the planner's recommendation against retrieved policy, a risk score, and the watchlist. Approves, sends back for revision, or escalates to human review. | Drafting the initial plan, gathering documents |

---

## 3. Tools

**Read-only:**

- `vendor_lookup` — checks mock vendor DB for prior relationship, category, certifications on file
- `policy_retriever` — RAG search over the policy vector store
- `watchlist_check` — checks a mock sanctions/watchlist table
- `risk_score_calculator` — simple weighted score from risk flags

**Side-effect (mocked — writes to local JSON/SQLite, never a real external action):**

- `create_approval_request` — logs a pending approval record
- `update_vendor_status` — writes the final onboarding status

---

## 4. Vector store documents (RAG source material)

- Vendor Onboarding Policy (general)
- Required Document Checklist by Vendor Category
- Risk Scoring Criteria / Rubric
- Sanctions & Watchlist Handling Policy
- Data Security & IT Vendor Requirements
- A handful of past vendor risk write-ups (precedent examples)

Chunked by section/policy clause. Metadata per chunk: `doc_type`,
`vendor_category`, `risk_tier`, `section`.

**Meaningful metadata filter:** when a request is `data_sensitive == true`
or `vendor_category == IT/Software`, retrieval is filtered to include
Data Security & IT Vendor Requirements chunks; low-risk categories skip them.

---

## 5. LangGraph state (draft)

```text
request_id
vendor_name
vendor_category
country
data_sensitive
vendor_history          # "new" | "existing"
submitted_documents
missing_documents
risk_flags
risk_score
retrieved_policy_chunks
planner_recommendation
reviewer_verdict
revision_count          # capped at 2 -> forces escalation
requires_human_review
human_decision
final_status
workflow_trace          # ordered list of nodes visited, for the UI
```

---

## 6. Graph shape (nodes & routes)

```text
Intake (completeness check)
    ├── missing documents → pause / ask requester (interrupt) → back to Intake
    └── complete
         ↓
    Vendor Lookup + Policy Retrieval (tools)
         ↓
    Onboarding Planner (draft recommendation)
         ↓
    Risk/Compliance Reviewer (critic)
         ├── approved → Mock Action (create approval + update status) → Complete
         ├── revision needed → back to Planner (revision_count += 1, cap 2)
         └── high-risk / exception / retry-limit hit → Human Review
                  ├── approved → Mock Action → Complete
                  └── rejected → Rejected outcome
```

---

## 7. Required test scenarios

1. **Happy path** — existing US vendor, low-risk category (e.g., Office
   Supplies), complete docs → standard onboarding, auto-completes.
2. **Branching path** — new vendor, IT/Software category, complete docs
   including security questionnaire → visibly different route through
   the reviewer.
3. **Missing-information path** — submission missing the Certificate of
   Insurance → workflow pauses and asks the requester, resumes once
   resubmitted.
4. **Failure/revision path** — reviewer rejects the planner's first
   recommendation (e.g., planner missed a risk flag) → loops back to
   Planner with feedback → revised recommendation approved within the
   retry limit.
5. **Escalation path** (bonus) — foreign vendor, data-sensitive, no
   security questionnaire → high risk → escalated to human review.

---

## 8. Status

- [x] Scenario defined
- [x] Vector store & policy documents authored
- [x] Mock data sources (vendor DB, watchlist)
- [x] LangGraph state schema implemented
- [x] Nodes & routing implemented
- [x] Tools implemented
- [x] Streamlit interface
- [x] Test scenarios verified
- [ ] Presentation materials

---

## 9. Setup & running

Requires **Python 3.11+**.

```bash
# 1. Create a virtualenv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. (Optional) configure an LLM provider — works without one, reasoning
#    text just falls back to deterministic templates.
#    Default provider is Amazon Bedrock (set BEDROCK_MODEL_ID, AWS_REGION,
#    and credentials via the standard AWS chain); OpenAI/Anthropic/Gemini
#    keys are used as fallbacks.
cp .env.example .env        # then fill in the provider you plan to use

# 3. Run the demo UI
streamlit run app.py
```

On first run the app seeds the mock vendor DB + watchlist into
`data/vendor_onboarding.db` and indexes the policy docs into
`data/chroma/` automatically.

**Run the test suite** (the 5 required scenarios + routing extras):

```bash
pytest tests/ -v
```

### Project layout

```
models.py          Pydantic models (VendorRequest, WorkflowState, enums, risk rubric)
schema.sql / db.py Mocked SQLite persistence (vendors, watchlist, approvals, status log)
seeders.py         Mock vendor master + sanctions watchlist data
policy_docs/       6 authored policy documents (RAG source material)
ingestion.py       Chunking + Chroma ingestion, metadata-filtered retrieval
embeddings.py      Local deterministic embedding model
tools.py           The 6 tools (4 read-only, 2 mocked side-effects)
llm.py             Model-agnostic LLM client (Bedrock -> OpenAI -> Anthropic -> Gemini)
graph/nodes.py     The three agents + human gate as LangGraph nodes
graph/workflow.py  Graph wiring, routing, interrupt-aware run helpers
app.py             Streamlit UI
tests/             pytest scenarios
```

### Demo scenarios

| # | Scenario | Submit in the UI |
|---|---|---|
| 1 | Happy path (auto-completes) | **Staple Supply Co.**, Office Supplies, US, existing, all 4 base docs |
| 2 | Branching → human gate | **Acme Cloud Services**, IT/Software, US, new, all 4 base docs + security questionnaire |
| 3 | Missing info pause | Same as #1 but without the Certificate of Insurance |
| 4 | Revision loop | **Firstline Facilities GmbH**, Facilities, Germany, existing, all 4 base docs |
| 5 | Escalation → human gate | **Helios Data Partners**, IT/Software, Germany, data-sensitive, new, base docs only (add security questionnaire when asked) |
| bonus | Watchlist → escalate | **Blackrock Shipping LLC**, any category, complete docs |

### Assumptions & deviations

- **Deterministic planner/reviewer.** Decisions are rule-based so the 5 scenarios
  pass without an API key and are repeatable in the demo. The LLM (when a key
  is set) only generates `reasoning`/`feedback` prose; templates are used as a
  fallback.
- **Mandatory IT/data-sensitive gate.** Per the authored policy, *any*
  IT/Software or data-sensitive vendor requires human sign-off regardless of
  risk score — this is what makes scenario 2 route visibly differently.
- **Scenario 5's missing security questionnaire first pauses intake** (it is a
  required document); once supplied, escalation comes from the residual
  foreign + new-data-sensitive profile (score ≥ 30). The "no security
  questionnaire" criterion therefore shows up as the intake pause, not as a
  reviewer flag for this specific case.
- **Planner blind spot drives the revision loop.** The planner (first pass)
  drafts `high_risk` whenever any risk flag exists and does not consult the
  watchlist (that is the reviewer's check). The reviewer re-tiers with the
  full rubric, producing the deterministic revise-then-approve path.
- **Vendor DB is authoritative** for prior-relationship when a record exists;
  otherwise the requester's claim is used.
- **Embeds use `sentence-transformers`** (`all-MiniLM-L6-v2`, 384 dims, runs
  locally after the first model download) for real semantic similarity in
  retrieval. Override the model via `SENTENCE_TRANSFORMER_MODEL`.
- **Side-effects are fully mocked** — approvals and status writes go only to
  local SQLite. Nothing external is ever called.
