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
- [ ] Vector store & policy documents authored
- [ ] Mock data sources (vendor DB, watchlist)
- [ ] LangGraph state schema implemented
- [ ] Nodes & routing implemented
- [ ] Tools implemented
- [ ] Streamlit interface
- [ ] Test scenarios verified
- [ ] Presentation materials
