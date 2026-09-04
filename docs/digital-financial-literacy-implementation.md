# Digital Financial Literacy Agent — Implementation Plan

**Document Type**: Implementation Plan
**Version**: 1.0
**Date**: 2025
**Status**: Draft
**Related Documents**:
- [digital-financial-literacy-overview.md](digital-financial-literacy-overview.md) (Business Overview)
- [digital-financial-literacy-architecture.md](digital-financial-literacy-architecture.md) (Technical Architecture)

---

## 1. Implementation Overview

Refer to the [Solution Overview](digital-financial-literacy-overview.md) for business context and the [Architecture document](digital-financial-literacy-architecture.md) for technical design.

The solution is largely built: the Flask application, chat UI, voice input, and agent YAML are all in place. The primary remaining implementation work is:
1. Deploying the updated agent to watsonx Orchestrate (blocked on authentication token renewal)
2. Hardening the production deployment (secret key, HTTPS, session storage)
3. Ongoing maintenance of the embedded financial data (bank rates, tax rules)

No implementation timeline was specified in the source requirements.

---

## 2. Implementation Roadmap

Implementation roadmap to be defined based on organisational priorities and resource availability.

The logical sequence of work, at a high level, is:

### Phase 1: Agent Deployment (Immediate)
**Objectives**: Get the updated agent instruction set live in watsonx Orchestrate

**Deliverables**:
- Renewed watsonx Orchestrate environment token
- Successfully imported `agents/digital_financial_literacy_agent.yaml` (v2 — 9 domains + 6 behavioral rules)
- Smoke-tested agent responses for FD comparison, scam detection, and fraud escalation

**Dependencies**:
- Valid IBM Cloud credentials and active watsonx Orchestrate environment
- `orchestrate env activate <env-id>` completed in the venv

---

### Phase 2: Production Hardening
**Objectives**: Make the Flask app production-safe

**Deliverables**:
- Strong `FLASK_SECRET_KEY` set in production `.env`
- HTTPS enabled (reverse proxy or cloud platform TLS)
- Debug mode disabled (`app.run(debug=False)`)
- Remove `app.logger.error("RAW ORCHESTRATE RESPONSE: %s", result)` debug line from `app.py`
- Rate limiting on `/chat` endpoint to prevent abuse

**Dependencies**: Phase 1 complete, hosting environment decided

---

### Phase 3: Data Freshness Process
**Objectives**: Establish a repeatable process for updating embedded financial data

**Deliverables**:
- Documented process for updating FD rates, tax rules, and regulatory references in `agents/digital_financial_literacy_agent.yaml`
- Schedule for quarterly review of rate accuracy
- Git commit + `orchestrate agents import` runbook

**Dependencies**: Phase 1 complete

---

## 3. Assumptions and Constraints

### 3.1 Assumptions

**Assumption 1**: Embedded FD rates are sufficiently accurate for educational use
- **Rationale**: Rates as of 2025 are embedded; the agent instructs users to confirm on official bank sites before acting
- **Impact if Invalid**: Users may see slightly outdated rate comparisons; the winner recommendation could change if a bank revises rates significantly
- **Validation Approach**: Quarterly check against each bank's official FD rate page

**Assumption 2**: groq/openai/gpt-oss-120b LLM has sufficient capability for react_core financial reasoning
- **Rationale**: The model is explicitly configured in the agent YAML; react_core style enables multi-step reasoning for calculations
- **Impact if Invalid**: Complex calculations or nuanced scam analysis may produce inaccurate outputs
- **Validation Approach**: Test FD maturity calculations and scam detection scenarios against known correct answers

**Assumption 3**: Users access the application via a Chromium-based browser
- **Rationale**: Web Speech API for voice input has full support only in Chrome and Edge; Firefox does not support it
- **Impact if Invalid**: Voice input button is disabled (gracefully) for unsupported browsers; text input still works
- **Validation Approach**: Test on Chrome, Edge, Firefox, and mobile Chrome; confirm graceful degradation

**Assumption 4**: No user authentication is required for this educational tool
- **Rationale**: The agent provides financial education, not personalised account access; no user PII is processed or stored
- **Impact if Invalid**: If personalised advice or account linking is added later, authentication and data protection controls must be implemented
- **Validation Approach**: Confirm no PII is logged or persisted; review Flask session data

**Assumption 5**: The watsonx Orchestrate environment token can be renewed by the operator
- **Rationale**: The current blocker is an expired token (`orchestrate env activate` requires interactive login)
- **Impact if Invalid**: Agent deployment remains blocked until token issue is resolved
- **Validation Approach**: Run `orchestrate env activate <env-id>` and `orchestrate agents import` successfully

---

### 3.2 Constraints

**Constraint 1**: LLM fixed to `groq/openai/gpt-oss-120b`
- **Type**: Technical (specified in agent YAML)
- **Impact**: Response quality and latency are bounded by this model's capabilities
- **Workaround**: Model can be changed by editing the `llm` field in the YAML and re-importing

**Constraint 2**: Embedded knowledge requires manual updates
- **Type**: Technical (no live data feeds connected)
- **Impact**: FD rates, RBI policy rates, and tax rules embedded in instructions can become stale
- **Workaround**: Quarterly review and re-import process (Phase 3); agent always instructs users to verify on official sources

**Constraint 3**: Flask in-memory sessions are not multi-instance safe
- **Type**: Technical
- **Impact**: If multiple Flask instances run behind a load balancer, `thread_id` session data will not be shared across instances
- **Workaround**: Use `Flask-Session` with Redis backend if horizontal scaling is needed

**Constraint 4**: Web Speech API not supported on all browsers
- **Type**: Technical (browser capability)
- **Impact**: Voice input unavailable on Firefox and some mobile browsers
- **Workaround**: Graceful degradation already implemented — mic button disabled with tooltip on unsupported browsers

---

## 4. Next Steps and Recommendations

### 4.1 Immediate Next Steps

1. **Renew watsonx Orchestrate environment token**
   - Owner: Developer / IBM Cloud account holder
   - Action: Run `.\venv\Scripts\Activate.ps1` then `orchestrate env activate jp-tok-0814fc42-a553-483a-ad4d-a52717974e8f`
   - Dependencies: Active IBM Cloud account with watsonx Orchestrate access

2. **Deploy updated agent**
   - Owner: Developer
   - Action: Run `orchestrate agents import --file agents/digital_financial_literacy_agent.yaml`
   - Dependencies: Step 1 complete

3. **Remove debug logging from `app.py`**
   - Owner: Developer
   - Action: Remove line `app.logger.error("RAW ORCHESTRATE RESPONSE: %s", result)` (line 121 in `app.py`)
   - Dependencies: None (can be done immediately)

4. **Set a strong `FLASK_SECRET_KEY` in production**
   - Owner: Developer / DevOps
   - Action: Generate a random 32-byte key: `python -c "import secrets; print(secrets.token_hex(32))"` and set in `.env`
   - Dependencies: None

5. **Commit and push all current changes to GitHub**
   - Owner: Developer
   - Action: `git add . && git commit -m "feat: expand agent + voice input" && git push origin main`
   - Dependencies: None

---

### 4.2 Recommendations

**Recommendation 1: Remove the debug log line before any production exposure**
- **Rationale**: Line 121 in `app.py` logs the full raw API response to `stderr`, which may include conversation content in production logs
- **Benefits**: Cleaner logs, no inadvertent data exposure
- **Considerations**: Keep the structured error logging (`app.logger.error("Orchestrate HTTP error %s: %s", ...)`) — only remove the raw response dump

**Recommendation 2: Add a live rate disclaimer banner to the UI**
- **Rationale**: Embedded FD rates will drift over time; users should be reminded to verify before acting
- **Benefits**: Reduces liability; reinforces the "educational, not advice" positioning
- **Considerations**: A single static banner below the chat header is sufficient — no backend changes needed

**Recommendation 3: Add Redis-backed session storage if scaling beyond one instance**
- **Rationale**: Current Flask in-memory sessions break conversation continuity under multi-instance load balancing
- **Benefits**: Enables horizontal scaling without losing conversation thread IDs
- **Considerations**: Requires `Flask-Session` and a Redis instance; minimal code change

**Recommendation 4: Implement quarterly rate review process**
- **Rationale**: Bank FD rates change multiple times a year; outdated rates reduce agent credibility
- **Benefits**: Keeps the agent accurate and trustworthy
- **Considerations**: Simple process — update YAML, run `orchestrate agents import`, done

**Recommendation 5: Extend to Hindi-first voice input**
- **Rationale**: `recognition.lang = 'en-IN'` currently set; changing to `'hi-IN'` or auto-detecting from user's browser language would serve Hindi-first users better
- **Benefits**: Broader reach for rural/semi-urban target audience
- **Considerations**: Web Speech API `lang` can be toggled dynamically; add a language toggle button to the UI

---

## 5. SOP Breakdown for Implementation

This section maps each architectural component to a recommended SOP for detailed documentation, using the `sop-builder` skill.

### 5.1 Recommended SOPs

**SOP 1: User Query Processing (Core Conversation Flow)**
- **Scope**: End-to-end flow from user submitting a question to receiving the agent's response
- **Source Material**:
  - Architecture document, Component 1 (Flask App) and Component 3 (Agent)
  - Architecture document, Section 4.2 (Data Flow Diagram)
- **Key Processes**: Message submission → IAM token fetch → API call → response parsing → markdown rendering
- **Integration Points**: IBM IAM, watsonx Orchestrate Chat Completions API
- **Priority**: High

---

**SOP 2: Agent Instruction Update and Deployment**
- **Scope**: Process for updating embedded financial data (rates, tax rules) and re-deploying the agent
- **Source Material**:
  - Architecture document, Component 4 (Agent Instruction Set)
  - `agents/digital_financial_literacy_agent.yaml`
- **Key Processes**: Identify stale data → update YAML → validate YAML syntax → run `orchestrate agents import` → smoke test
- **Integration Points**: watsonx Orchestrate CLI (`orchestrate` command), IBM Cloud IAM
- **Priority**: High (required for ongoing accuracy)

---

**SOP 3: Scam Detection and Fraud Escalation**
- **Scope**: How the agent analyses a described suspicious situation and produces a warning + escalation guidance
- **Source Material**:
  - Architecture document, Component 3 (Agent), behavioral rule 1 and rule 6
  - Agent instructions, Section 7 (Loan & Scam Detection) and Section 9 (Cyber Fraud Helpline)
- **Key Processes**: Pattern detection (urgency / OTP / guaranteed returns) → risk classification → warning generation → 1930 / cybercrime.gov.in escalation
- **Integration Points**: None (agent-internal reasoning); output references external helpline URLs
- **Priority**: Critical

---

**SOP 4: Voice Input Processing (Client-Side)**
- **Scope**: How voice input is captured, transcribed, and submitted as a chat message
- **Source Material**:
  - Architecture document, Component 2 (Chat UI), Integration 3 (Web Speech API)
  - `templates/index.html` voice input JS section
- **Key Processes**: Mic button click → permission prompt → speech recognition start → interim display → final transcript → textarea population → send button activation
- **Integration Points**: Browser Web Speech API (no server involvement)
- **Priority**: Medium

---

**SOP 5: FD Comparison and Maturity Calculation**
- **Scope**: How the agent processes an FD comparison query with a stated principal and tenure, and produces a comparison table + calculation + recommendation
- **Source Material**:
  - Agent instructions, Section 1 (Fixed Deposits) — rate tables and compounding formula
  - Architecture document, Component 3 and Component 4
- **Key Processes**: Extract principal + tenure → look up bank rates → apply A = P(1 + r/4)^(4t) → compare maturity values → select winner → add caveat to verify on official site
- **Integration Points**: None (agent-internal knowledge)
- **Priority**: High

---

### 5.2 Mapping Architecture to SOPs

For each SOP above, use the `sop-builder` skill and provide:

1. **Business process**: The workflow as described in the SOP scope above
2. **Relevant architecture sections**: The source material references listed per SOP
3. **Data flows**: Refer to Architecture document Section 4.2 (Data Flow Diagram)
4. **Decision points**:
   - SOP 3: Is the pattern count above threshold → warn / escalate vs. inform
   - SOP 1: Is `thread_id` present → continue thread vs. start new
   - SOP 5: Is the best rate a clear winner → single recommendation vs. two-option comparison
5. **Integration points**: As listed per SOP
6. **Business rules**:
   - Rates confirmed to be "as of 2025" — user must verify before acting
   - Calculations use quarterly compounding (not simple interest)
   - Fraud escalation always includes 1930 — non-negotiable
7. **Exception handling**:
   - SOP 1: 404 → return "Agent not found" error; HTTPError → return `"API error {status}"`
   - SOP 4: `SpeechRecognition` unavailable → disable mic button gracefully
   - SOP 3: If live fraud in progress → lead with 1930, then analysis
