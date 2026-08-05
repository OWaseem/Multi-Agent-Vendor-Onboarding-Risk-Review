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

Instead of asking one AI model to complete every task, we divided the work among multiple specialized agents.

Benefits include:

Better organization
Easier debugging
More reliable outputs
Modular architecture
Easier maintenance
Enterprise scalability
Speaker Notes

"Each agent has one responsibility and focuses only on that task. This follows good software engineering principles because each component has a single responsibility. If we need to improve risk assessment later, we only update the Risk Agent without affecting the rest of the workflow."

# Slide 4 – System Architecture (2 min)
               User
                 │
                 ▼
         Orchestrator Agent
                 │
    ┌────────┬─────────┬────────┐
    ▼        ▼         ▼        ▼
Research   Risk     Approval  Reporter
 Agent     Agent      Agent     Agent
    │        │          │         │
    └────────┴──────────┴─────────┘
                 │
                 ▼
          Final Decision
Responsibilities

Orchestrator

Coordinates the entire workflow.

Research Agent

Collects vendor information.

Risk Agent

Evaluates financial, compliance, and security risk.

Approval Agent

Applies deterministic business rules.

Reporter

Creates the final audit-ready report.

Speaker Notes

Spend about 20–30 seconds explaining each agent and emphasize that the orchestrator coordinates the workflow while each specialist agent focuses on one domain.

# Slide 5 – End-to-End Workflow (2 min)
Step 1

User submits a vendor.

↓

Step 2

The Orchestrator starts the review.

↓

Step 3

The Research Agent gathers company information.

↓

Step 4

The Risk Agent evaluates:

Financial risk
Compliance
Security
Sanctions

↓

Step 5

The Approval Agent determines whether to:

Approve
Escalate
Reject

↓

Step 6

The Reporter creates the final report.

Speaker Notes

Walk the audience through the workflow as if they were submitting a real vendor. This helps non-technical listeners understand how information flows through the system.

# Slide 6 – AI Engineering Concepts (2 min)

This project demonstrates several AI engineering principles:

Multi-Agent Architecture

Breaking one complex task into multiple specialized AI agents.

Agent Orchestration

Managing communication between agents.

Structured Outputs

Passing structured JSON instead of free-form text.

State Management

Keeping track of workflow progress.

Human-in-the-Loop

Escalating medium- and high-risk vendors to human reviewers.

Explainability

Producing transparent reports with supporting evidence.

Speaker Notes

"This project isn't just about using an LLM. It's about engineering reliable AI systems by combining software engineering principles with modern AI capabilities."

# Slide 7 – Technology Stack (1.5 min)
Languages
Python
AI
Large Language Models
Multi-Agent System
Data Validation
Pydantic
Structured JSON
Development
Git
GitHub
Software Engineering
Modular architecture
Agent communication
State management
Deterministic business rules
Speaker Notes

Explain that the project combines traditional software engineering with AI rather than relying only on prompts.

# Slide 8 – Engineering Challenges (2 min)
Challenge 1

Coordinating multiple agents.

Solution:

The Orchestrator manages communication.

Challenge 2

Keeping outputs consistent.

Solution:

Structured JSON and schema validation.

Challenge 3

Reducing hallucinations.

Solution:

Deterministic approval rules instead of relying solely on LLM reasoning.

Challenge 4

Creating audit trails.

Solution:

Generate detailed reports documenting each decision.

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
Future Improvements
Live sanctions APIs
Financial data integrations
RAG with company policies
Enterprise authentication
Dashboard analytics
Workflow notifications
Speaker Notes

Explain how this project could evolve into a production-ready enterprise system with integrations and richer data sources.

# Slide 10 – Demo (2–3 min)

Show:

Enter vendor information.
Start the workflow.
Display agent coordination.
Show risk assessment.
Show approval decision.
Display the final report.

Narrate which agent is active at each stage so the audience can connect the architecture to the live application.

# Slide 11 – Key Takeaways (1 min)
What We Built
Enterprise AI workflow
Multi-agent architecture
Automated vendor review
Explainable AI decisions
What We Learned
AI engineering is more than prompting an LLM.
Agent specialization improves maintainability.
Structured outputs increase reliability.
Human oversight remains essential in high-stakes workflows.

# Slide 12 – Questions

Thank You!

Questions?