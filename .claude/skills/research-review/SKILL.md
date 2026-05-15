---
name: research-review
description: Get a deep critical review of research from GPT via Codex CLI. Use when user says "review my research", "help me review", "get external review", or wants critical feedback on research ideas, papers, or experimental results.
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent
---

# Research Review via Codex CLI (xhigh reasoning)

Get a multi-round critical review of research work from an external LLM with maximum reasoning depth.

## Constants

- REVIEWER_MODEL = `gpt-5.5` — Model used via Codex CLI. Must be an OpenAI model (e.g., `gpt-5.5`, `o3`, `gpt-4o`)
- **REVIEWER_BACKEND = `codex`** — Default: Codex CLI (xhigh). Override with `— reviewer: oracle-pro` for GPT-5.5 Pro via Oracle MCP. See `shared-references/reviewer-routing.md`.
- **PAPER_REVIEW = false** — When `true`, the reviewer is restricted to reading **only PDF files**. Use when reviewing a compiled paper/PDF rather than the live project. Claude must only pass the PDF as context; do NOT include LaTeX source, code, logs, or other non-PDF materials.
- **REVIEWER_ROLE = "NeurIPS/ICML"** — Reviewer persona and criteria set. Options: `"NeurIPS/ICML"` (default), `"TNNLS"`, `"ICLR"`, `"JMLR"`. Affects review style (e.g., TNNLS emphasizes theoretical depth, reproducibility, and practical applicability).

## Context: $ARGUMENTS

## Prerequisites

- **Codex CLI Server** configured in Claude Code:
  ```bash
  codex login  # Ensure Codex CLI is installed and authenticated
  ```
- This gives Claude Code access to `codex exec` and `codex exec resume` tools

## Workflow

### Step 1: Gather Research Context
Before calling the external reviewer, compile a comprehensive briefing:

**If `PAPER_REVIEW = true`:**
1. Locate the compiled PDF (e.g., `main.pdf`, `paper.pdf`). If not found, compile it first via `/paper-compile`.
2. Read the PDF directly (it may be large; read in chunks if needed).
3. Do NOT read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials.
4. Pass only the PDF content to the reviewer.

**If `PAPER_REVIEW = false` (default):**
1. Read project narrative documents (e.g., STORY.md, README.md, paper drafts)
2. Read any memory/notes files for key findings and experiment history
3. Identify: core claims, methodology, key results, known weaknesses

### Step 2: Initial Review (Round 1)
Send a detailed prompt with xhigh reasoning:

```bash
codex exec -c model_reasoning_effort="xhigh" "$(cat <<'PROMPT'
[Full research context + specific questions]

{% if PAPER_REVIEW %}IMPORTANT: You are reviewing a compiled paper. You may ONLY read the provided PDF file(s). Do NOT attempt to read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials. Base your entire review solely on the PDF content.{% endif %}

Please act as a senior ML reviewer ({REVIEWER_ROLE} level). Identify:
1. Logical gaps or unjustified claims
2. Missing experiments that would strengthen the story
3. Narrative weaknesses
4. Whether the contribution is sufficient for a top venue
Please be brutally honest.
PROMPT
)" 2>&1
```

### Step 3: Iterative Dialogue (Rounds 2-N)
Use `codex exec resume` with the returned `thread_id` to continue the conversation:

For each round:
1. **Respond** to criticisms with evidence/counterarguments
2. **Ask targeted follow-ups** on the most actionable points
3. **Request specific deliverables**: experiment designs, paper outlines, claims matrices

Key follow-up patterns:
- "If we reframe X as Y, does that change your assessment?"
- "What's the minimum experiment to satisfy concern Z?"
- "Please design the minimal additional experiment package (highest acceptance lift per GPU week)"
- "Please write a mock {REVIEWER_ROLE} review with scores"
- "Give me a results-to-claims matrix for possible experimental outcomes"

### Step 4: Convergence
Stop iterating when:
- Both sides agree on the core claims and their evidence requirements
- A concrete experiment plan is established
- The narrative structure is settled

### Step 5: Document Everything
Save the full interaction and conclusions to a review document in the project root:
- Round-by-round summary of criticisms and responses
- Final consensus on claims, narrative, and experiments
- Claims matrix (what claims are allowed under each possible outcome)
- Prioritized TODO list with estimated compute costs
- Paper outline if discussed

Update project memory/notes with key review conclusions.

## Key Rules

- ALWAYS use `config: {"model_reasoning_effort": "xhigh"}` for reviews
- Send comprehensive context in Round 1 — the external model cannot read your files
- Be honest about weaknesses — hiding them leads to worse feedback
- Push back on criticisms you disagree with, but accept valid ones
- Focus on ACTIONABLE feedback — "what experiment would fix this?"
- Document the thread_id for potential future resumption
- The review document should be self-contained (readable without the conversation)

## Prompt Templates

### For initial review:
"I'm going to present a complete ML research project for your critical review. Please act as a senior ML reviewer ({REVIEWER_ROLE} level)..."

### For experiment design:
"Please design the minimal additional experiment package that gives the highest acceptance lift per GPU week. Our compute: [describe]. Be very specific about configurations."

### For paper structure:
"Please turn this into a concrete paper outline with section-by-section claims and figure plan."

### For claims matrix:
"Please give me a results-to-claims matrix: what claim is allowed under each possible outcome of experiments X and Y?"

### For mock review:
"Please write a mock {REVIEWER_ROLE} review with: Summary, Strengths, Weaknesses, Questions for Authors, Score, Confidence, and What Would Move Toward Accept."

## Review Tracing

After each `codex exec` or `codex exec resume` reviewer call, save the trace following `shared-references/review-tracing.md`. Use `tools/save_trace.sh` or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
