# Multi-Agent Vendor Onboarding & Risk Review Sides

# Slide 1 – Title (30–45 sec)
Multi-Agent Vendor Onboarding Risk Review

Team Members

Capstone Project

Speaker Notes

"Today we'll be presenting our Multi-Agent Vendor Onboarding Risk Review system. This project demonstrates how multiple AI agents can work together to automate vendor risk assessment for enterprise procurement. Instead of using a single chatbot, our solution divides responsibilities among specialized agents, creating a more reliable, explainable, and scalable workflow."

# Slide 2 – The Business Problem (1.5 min)
Why does vendor onboarding matter?

Every large company works with hundreds or even thousands of vendors.

Before approving a vendor, organizations need to answer questions like:

Is this company financially stable?
Are they on any sanctions lists?
Are they compliant with regulations?
Do they meet security requirements?
Should we trust them with sensitive company data?
Current Problems
Manual research
Long approval cycles
Different teams reviewing the same vendor
Human error
Inconsistent decisions
Limited auditability
Speaker Notes

"Vendor onboarding is much more than filling out paperwork. Procurement, security, compliance, finance, and legal teams all have to review the vendor before approval. This process can take days or even weeks because every department has different responsibilities. Our goal was to automate as much of this workflow as possible while keeping humans involved when necessary."

# Slide 3 – Our Solution (1.5 min)
AI-Powered Multi-Agent Workflow

Instead of asking one AI model to complete every task, we divided the work among multiple specialized agents, coordinated by a LangGraph state machine.

Benefits include:

Better organization
Easier debugging
More reliable outputs
Modular architecture
Easier maintenance
Enterprise scalability
Speaker Notes

"Each agent has one responsibility and focuses only on that task. This follows good software engineering principles because each component has a single responsibility. If we need to improve risk assessment later, we only update the Risk/Compliance Reviewer without affecting the rest of the workflow."

# Slide 4 – System Architecture (2 min)
                 Requester
                     │
                     ▼
      Intake Agent (documents + format check)
                     │
                     ▼
   Evidence Gathering (vendor lookup + RAG policy retrieval)
                     │
                     ▼
              Onboarding Planner
                     │
                     ▼
          Risk / Compliance Reviewer
        │            │             │
    approved      revise       escalate /
        │       (loops back    exception
        │        to Planner)       │
        ▼                          ▼
   Mock Action                Human Review
        │                          │
        └────────────┬─────────────┘
                      ▼
             Summarizer (final report)

Responsibilities

LangGraph (orchestration layer)

Coordinates node execution and conditional routing (approve / revise / escalate) as a compiled state graph — this is the workflow engine itself, not a separate agent.

Intake / Document-Completeness Agent

Checks the submission against the required-document checklist and validates each document's format/fields.

Onboarding Planner

Looks up the vendor record and retrieves relevant policy via RAG, then drafts a recommended path (standard / high-risk / needs-exception).

Risk / Compliance Reviewer

Computes a risk score, checks the sanctions watchlist, and validates the planner's recommendation: approves, sends back for revision, or escalates to a human.

Summarizer

Drafts a plain-language wrap-up of the decision (why the risk score is what it is, whether human sign-off was needed, and the outcome) — the audit-ready report.

Speaker Notes

Spend about 20–30 seconds explaining each stage and emphasize that LangGraph handles coordination/routing itself, while each specialist agent focuses on one domain.

# Slide 5 – End-to-End Workflow (2 min)
Step 1

Requester submits a vendor request with supporting documents.

↓

Step 2

Intake Agent checks document completeness and format; pauses and asks the requester if anything is missing or invalid.

↓

Step 3

Evidence Gathering runs automatically: vendor lookup plus a metadata-filtered RAG search over the policy vector store.

↓

Step 4

Onboarding Planner drafts a recommended path based on the vendor record and retrieved policy.

↓

Step 5

Risk / Compliance Reviewer evaluates:

Risk score (financial/category/data-sensitivity weighting)
Sanctions watchlist
Compliance policy fit

↓

Step 6

Reviewer decides: approve, send back to the Planner for revision, or escalate to a human reviewer.

↓

Step 7

Summarizer produces the final plain-language report explaining the decision.

Speaker Notes

Walk the audience through the workflow as if they were submitting a real vendor. This helps non-technical listeners understand how information flows through the system.

# Slide 6 – AI Engineering Concepts (2 min)

This project demonstrates several AI engineering principles:

Multi-Agent Architecture

Breaking one complex task into multiple specialized AI agents.

Graph-Based Orchestration

LangGraph manages state and conditional routing between nodes as a compiled graph, rather than a separate coordinator agent passing messages.

Structured Outputs

Passing structured JSON (Pydantic models) instead of free-form text.

State Management

Keeping track of workflow progress across every node, with a full audit trail.

Human-in-the-Loop

Escalating medium- and high-risk vendors to human reviewers via a LangGraph interrupt.

Explainability

Producing transparent, plain-language reasoning with supporting evidence at every stage.

Speaker Notes

"This project isn't just about using an LLM. It's about engineering reliable AI systems by combining software engineering principles with modern AI capabilities."

# Slide 7 – Technology Stack (1.5 min)
Languages
Python
Orchestration
LangGraph (state machine, conditional routing, interrupts/resume)
AI / LLMs
Amazon Bedrock (Claude), with OpenAI, Anthropic, and Google Gemini as pluggable fallbacks; deterministic template fallback when no provider is configured
Retrieval (RAG)
Chroma vector store, sentence-transformers embeddings, category-aware metadata filtering
Data Validation
Pydantic (schemas, structured outputs), pypdf (document format validation)
Interface
Streamlit
Development
Git, GitHub
Software Engineering
Modular architecture
Graph-based orchestration
State management
Deterministic business rules
Speaker Notes

Explain that the project combines traditional software engineering with AI rather than relying only on prompts.

# Slide 8 – Engineering Challenges (2 min)
Challenge 1

Coordinating multiple agents and routing.

Solution:

LangGraph's compiled state graph manages node execution order and conditional routing (approve/revise/escalate) automatically.

Challenge 2

Keeping outputs consistent.

Solution:

Structured JSON and Pydantic schema validation.

Challenge 3

Reducing hallucinations.

Solution:

Deterministic approval rules (risk score + watchlist) instead of relying solely on LLM reasoning; the LLM only generates explanatory prose.

Challenge 4

Creating audit trails.

Solution:

Every decision is persisted (approval requests + vendor status log) and explained in a generated plain-language report.

Speaker Notes

Talk about what the team learned from solving these problems. Enterprise AI requires reliability and traceability, not just intelligent responses.

# Slide 9 – Business Impact (1.5 min)
Benefits
Faster onboarding
Less manual work
More consistent decisions
Better compliance
Easier auditing
Scalable architecture
Policy-grounded reasoning (RAG already implemented, not just planned)
Future Improvements
Live sanctions APIs
Financial data integrations
Enterprise authentication
Dashboard analytics
Workflow notifications
Speaker Notes

Explain how this project could evolve into a production-ready enterprise system with integrations and richer data sources. Note that RAG-grounded policy retrieval is already built and running today — it's listed under Benefits, not Future Improvements.

# Slide 10 – Demo (2–3 min)

Show:

Enter vendor information, or use the bundled sample documents button to attach valid example PDFs.
Start the workflow and show the workflow trace.
Show the risk score and reviewer decision.
If escalated, approve or reject at the human review gate.
Display the final plain-language summary report.

Narrate which node is active at each stage so the audience can connect the architecture to the live application.

# Slide 11 – Key Takeaways (1 min)
What We Built
Enterprise AI workflow
Multi-agent architecture with LangGraph orchestration
Automated vendor review, including document format validation
Explainable AI decisions
What We Learned
AI engineering is more than prompting an LLM.
Agent specialization improves maintainability.
Structured outputs increase reliability.
Human oversight remains essential in high-stakes workflows.

# Slide 12 – Questions

Thank You!

Questions?
