---
name: auto-review-loop
description: Autonomous multi-round research review loop. Repeatedly reviews via Codex CLI, implements fixes, and re-reviews until positive assessment or max rounds reached. Use when user says "auto review loop", "review until it passes", or wants autonomous iterative improvement.
argument-hint: [topic-or-scope]
allowed-tools: Bash(*), Read, Grep, Glob, Write, Edit, Agent, Skill
---

# Auto Review Loop: Autonomous Research Improvement

Autonomously iterate: review → implement fixes → re-review, until the external reviewer gives a positive assessment or MAX_ROUNDS is reached.

## Context: $ARGUMENTS

## Constants

- MAX_ROUNDS = 4
- POSITIVE_THRESHOLD: score >= 6/10, or verdict contains "accept", "sufficient", "ready for submission"
- REVIEW_DOC: `review-stage/AUTO_REVIEW.md` (cumulative log) *(fall back to `./AUTO_REVIEW.md` for legacy projects)*
- REVIEWER_MODEL = `gpt-5.5` — Model used via Codex CLI. Must be an OpenAI model (e.g., `gpt-5.5`, `o3`, `gpt-4o`)
- **REVIEWER_BACKEND = `codex`** — Default: Codex CLI (xhigh). Override with `— reviewer: oracle-pro` for GPT-5.5 Pro via Oracle MCP. See `shared-references/reviewer-routing.md`.
- **OUTPUT_DIR = `review-stage/`** — All review-stage outputs go here. Create the directory if it doesn't exist.
- **HUMAN_CHECKPOINT = false** — When `true`, pause after each round's review (Phase B) and present the score + weaknesses to the user. Wait for user input before proceeding to Phase C. The user can: approve the suggested fixes, provide custom modification instructions, skip specific fixes, or stop the loop early. When `false` (default), the loop runs fully autonomously.
- **COMPACT = false** — When `true`, (1) read `EXPERIMENT_LOG.md` and `findings.md` instead of parsing full logs on session recovery, (2) append key findings to `findings.md` after each round.
- **REVIEWER_DIFFICULTY = medium** — Controls how adversarial the reviewer is. Three levels:
  - `medium` (default): Current behavior — CLI-based review, Claude controls what context GPT sees.
  - `hard`: Adds **Reviewer Memory** (GPT tracks its own suspicions across rounds) + **Debate Protocol** (Claude can rebut, GPT rules).
  - `nightmare`: Everything in `hard` + **GPT reads the repo directly** via `codex exec` (Claude cannot filter what GPT sees) + **Adversarial Verification** (GPT independently checks if code matches claims).
- **PAPER_REVIEW = false** — When `true`, the reviewer is restricted to reading **only PDF files**. Use when reviewing a compiled paper/PDF (e.g., `main.pdf`) rather than the live project. The reviewer must NOT read LaTeX source, code, logs, or any non-PDF materials. Claude should only pass the PDF path as context.
- **REVIEWER_ROLE = "NeurIPS/ICML"** — Reviewer persona and criteria set. Options: `"NeurIPS/ICML"` (default), `"TNNLS"`, `"ICLR"`, `"JMLR"`. Affects review style (e.g., TNNLS emphasizes theoretical depth, reproducibility, and practical applicability over novelty-alone).

> 💡 Override: `/auto-review-loop "topic" — compact: true, human checkpoint: true, difficulty: hard`
> 💡 Paper review override: `/auto-review-loop "topic" — paper-review: true, reviewer-role: TNNLS`

## State Persistence (Compact Recovery)

Long-running loops may hit the context window limit, triggering automatic compaction. To survive this, persist state to `review-stage/REVIEW_STATE.json` after each round:

```json
{
  "round": 2,
  "thread_id": "019cd392-...",
  "status": "in_progress",
  "difficulty": "medium",
  "last_score": 5.0,
  "last_verdict": "not ready",
  "pending_experiments": ["screen_name_1"],
  "timestamp": "2026-03-13T21:00:00"
}
```

**Write this file at the end of every Phase E** (after documenting the round). Overwrite each time — only the latest state matters.

**On completion** (positive assessment or max rounds), set `"status": "completed"` so future invocations don't accidentally resume a finished loop.

## Output Protocols

> Follow these shared protocols for all output files:
> - **[Output Versioning Protocol](../shared-references/output-versioning.md)** — write timestamped file first, then copy to fixed name
> - **[Output Manifest Protocol](../shared-references/output-manifest.md)** — log every output to MANIFEST.md
> - **[Output Language Protocol](../shared-references/output-language.md)** — respect the project's language setting

## Workflow

### Initialization

1. **Check for `review-stage/REVIEW_STATE.json`** *(fall back to `./REVIEW_STATE.json` if not found — legacy path)*:
   - If neither path exists: **fresh start** (normal case, identical to behavior before this feature existed)
   - If it exists AND `status` is `"completed"`: **fresh start** (previous loop finished normally)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is older than 24 hours: **fresh start** (stale state from a killed/abandoned run — delete the file and start over)
   - If it exists AND `status` is `"in_progress"` AND `timestamp` is within 24 hours: **resume**
     - Read the state file to recover `round`, `thread_id`, `last_score`, `pending_experiments`
     - Read `review-stage/AUTO_REVIEW.md` to restore full context of prior rounds *(fall back to `./AUTO_REVIEW.md`)*
     - If `pending_experiments` is non-empty, check if they have completed (e.g., check screen sessions)
     - Resume from the next round (round = saved round + 1)
     - Log: "Recovered from context compaction. Resuming at Round N."
2. **Gather context for review**:
   - **If `PAPER_REVIEW = true`**: Locate the compiled PDF (e.g., `main.pdf`, `paper.pdf`). If not found, compile it first via `/paper-compile`. Read the PDF directly (in chunks if large). Do NOT read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials. Pass only the PDF content to the reviewer.
   - **If `PAPER_REVIEW = false` (default)**: Read project narrative documents, memory files, and any prior review documents. **When `COMPACT = true` and compact files exist**: read `findings.md` + `EXPERIMENT_LOG.md` instead of full `review-stage/AUTO_REVIEW.md` and raw logs — saves context window.
3. Read recent experiment results (check output directories, logs). **Skip entirely if `PAPER_REVIEW = true`.**
4. Identify current weaknesses and open TODOs from prior reviews
5. Initialize round counter = 1 (unless recovered from state file)
6. Create/update `review-stage/AUTO_REVIEW.md` with header and timestamp

### Loop (repeat up to MAX_ROUNDS)

#### Phase A: Review

**Route by REVIEWER_DIFFICULTY:**

##### Medium (default) — CLI Review

Send comprehensive context to the external reviewer:

```bash
codex exec -c model_reasoning_effort="xhigh" "$(cat <<'PROMPT'
[Round N/MAX_ROUNDS of autonomous review loop]

[Full research context: claims, methods, results, known weaknesses]
[Changes since last round, if any]

{% if PAPER_REVIEW %}IMPORTANT: You are reviewing a compiled paper. You may ONLY read the provided PDF file(s). Do NOT attempt to read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials. Base your entire review solely on the PDF content.{% endif %}

Please act as a senior ML reviewer ({REVIEWER_ROLE} level).

1. Score this work 1-10 for a top venue
2. List remaining critical weaknesses (ranked by severity)
3. For each weakness, specify the MINIMUM fix (experiment, analysis, or reframing)
4. State clearly: is this READY for submission? Yes/No/Almost

Be brutally honest. If the work is ready, say so clearly.
PROMPT
)" 2>&1
```

If this is round 2+, use `codex exec resume` with the saved thread_id to maintain conversation context.

##### Hard — CLI Review + Reviewer Memory

Same as medium, but **prepend Reviewer Memory** to the prompt:

```bash
codex exec -c model_reasoning_effort="xhigh" "$(cat <<'PROMPT'
[Round N/MAX_ROUNDS of autonomous review loop]

## Your Reviewer Memory (persistent across rounds)
[Paste full contents of REVIEWER_MEMORY.md here]

IMPORTANT: You have memory from prior rounds. Check whether your
previous suspicions were genuinely addressed or merely sidestepped.
The author (Claude) controls what context you see — be skeptical
of convenient omissions.

[Full research context, changes since last round...]

{% if PAPER_REVIEW %}IMPORTANT: You are reviewing a compiled paper. You may ONLY read the provided PDF file(s). Do NOT attempt to read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials. Base your entire review solely on the PDF content.{% endif %}

Please act as a senior ML reviewer ({REVIEWER_ROLE} level).
1. Score this work 1-10 for a top venue
2. List remaining critical weaknesses (ranked by severity)
3. For each weakness, specify the MINIMUM fix
4. State clearly: is this READY for submission? Yes/No/Almost
5. **Memory update**: List any new suspicions, unresolved concerns,
   or patterns you want to track in future rounds.

Be brutally honest. Actively look for things the author might be hiding.
PROMPT
)" 2>&1
```

##### Nightmare — Codex Exec (GPT reads repo directly)

**Do NOT use MCP.** Instead, let GPT access the repo autonomously via `codex exec`:

```bash
codex exec "$(cat <<'PROMPT'
You are an adversarial senior ML reviewer ({REVIEWER_ROLE} level).
This is Round N/MAX_ROUNDS of an autonomous review loop.

## Your Reviewer Memory (persistent across rounds)
[Paste full contents of REVIEWER_MEMORY.md]

## Instructions
{% if PAPER_REVIEW %}
You are reviewing a compiled paper. You may ONLY read PDF files in this repository (e.g., `main.pdf`, `paper.pdf`). Do NOT read LaTeX source files, code, experiment logs, CSV/JSON data, or any non-PDF materials. Base your entire review solely on the PDF content. The author (Claude) has been instructed to only provide PDFs as context.
{% else %}
You have FULL READ ACCESS to this repository. The author (Claude) does NOT
control what you see — explore freely. Your job is to find problems the
author might hide or downplay.

DO THE FOLLOWING:
1. Read the experiment code, results files (JSON/CSV), and logs YOURSELF
2. Verify that reported numbers match what's actually in the output files
3. Check if evaluation metrics are computed correctly (ground truth, not model output)
4. Look for cherry-picked results, missing ablations, or suspicious hyperparameter choices
5. Read NARRATIVE_REPORT.md or review-stage/AUTO_REVIEW.md for the author's claims — then verify each against code
{% endif %}

OUTPUT FORMAT:
- Score: X/10
- Verdict: ready / almost / not ready
- Verified claims: [which claims you independently confirmed]
- Unverified/false claims: [which claims don't match the code or results]
- Weaknesses (ranked): [with MINIMUM fix for each]
- Memory update: [new suspicions and patterns to track next round]

Be adversarial. Trust nothing the author tells you — verify everything yourself.
PROMPT
)" --skip-git-repo-check 2>&1
```

**Key difference**: In nightmare mode, GPT independently reads code, result files, and logs. Claude cannot filter or curate what GPT sees. This is the closest analog to a real hostile reviewer who reads your actual paper + supplementary materials.

#### Phase B: Parse Assessment

**CRITICAL: Save the FULL raw response** from the external reviewer verbatim (store in a variable for Phase E). Do NOT discard or summarize — the raw text is the primary record.

Then extract structured fields:
- **Score** (numeric 1-10)
- **Verdict** ("ready" / "almost" / "not ready")
- **Action items** (ranked list of fixes)

**STOP CONDITION**: If score >= 6 AND verdict contains "ready" or "almost" → stop loop, document final state.

#### Phase B.5: Reviewer Memory Update (hard + nightmare only)

**Skip entirely if `REVIEWER_DIFFICULTY = medium`.**

After parsing the assessment, update `REVIEWER_MEMORY.md` in the project root:

```markdown
# Reviewer Memory

## Round 1 — Score: X/10
- **Suspicion**: [what the reviewer flagged]
- **Unresolved**: [concerns not yet addressed]
- **Patterns**: [recurring issues the reviewer noticed]

## Round 2 — Score: X/10
- **Previous suspicions addressed?**: [yes/no for each, with reviewer's judgment]
- **New suspicions**: [...]
- **Unresolved**: [carried forward + new]
```

**Rules**:
- Append each round, never delete prior rounds (audit trail)
- If the reviewer's response includes a "Memory update" section, copy it verbatim
- This file is passed back to GPT in the next round's Phase A — it is GPT's persistent brain

#### Phase B.6: Debate Protocol (hard + nightmare only)

**Skip entirely if `REVIEWER_DIFFICULTY = medium`.**

After parsing the review, Claude (the author) gets a chance to **rebut**:

**Step 1 — Claude's Rebuttal:**

For each weakness the reviewer identified, Claude writes a structured response:

```markdown
### Rebuttal to Weakness #1: [title]
- **Accept / Partially Accept / Reject**
- **Argument**: [why this criticism is invalid, already addressed, or based on a misunderstanding]
- **Evidence**: [point to specific code, results, or prior round fixes]
```

Rules for Claude's rebuttal:
- Must be honest — do NOT fabricate evidence or misrepresent results
- Can point out factual errors in the review (reviewer misread code, wrong metric, etc.)
- Can argue a weakness is out of scope or would require unreasonable effort
- Maximum 3 rebuttals per round (pick the most impactful to contest)

**Step 2 — GPT Rules on Rebuttal:**

Send Claude's rebuttal back to GPT for a ruling:

*Hard mode (CLI):*
```bash
codex exec resume [saved] -c model_reasoning_effort="xhigh" "$(cat <<'PROMPT'
The author rebuts your review:

[paste Claude's rebuttal]

For each rebuttal, rule:
- SUSTAINED (author's argument is valid, withdraw this weakness)
- OVERRULED (your original criticism stands, explain why)
- PARTIALLY SUSTAINED (revise the weakness to a narrower scope)

Then update your score if any weaknesses were withdrawn.
PROMPT
)" 2>&1
```

*Nightmare mode (codex exec):*
```bash
codex exec "$(cat <<'PROMPT'
You are the same adversarial reviewer. The author rebuts your review:

[paste Claude's rebuttal]

VERIFY the author's evidence claims yourself — read the files they reference.
Do NOT take their word for it.

For each rebuttal, rule:
- SUSTAINED (verified and valid)
- OVERRULED (evidence doesn't check out or argument is weak)
- PARTIALLY SUSTAINED (partially valid, narrow the weakness)

Update your score. Update your memory.
PROMPT
)" --skip-git-repo-check 2>&1
```

**Step 3 — Update score and action items** based on the ruling:
- SUSTAINED weaknesses: remove from action items
- OVERRULED: keep as-is
- PARTIALLY SUSTAINED: revise scope

Append the full debate transcript to `review-stage/AUTO_REVIEW.md` under the round's entry.

#### Human Checkpoint (if enabled)

**Skip this step entirely if `HUMAN_CHECKPOINT = false`.**

When `HUMAN_CHECKPOINT = true`, present the review results and wait for user input:

```
📋 Round N/MAX_ROUNDS review complete.

Score: X/10 — [verdict]
Top weaknesses:
1. [weakness 1]
2. [weakness 2]
3. [weakness 3]

Suggested fixes:
1. [fix 1]
2. [fix 2]
3. [fix 3]

Options:
- Reply "go" or "continue" → implement all suggested fixes
- Reply with custom instructions → implement your modifications instead
- Reply "skip 2" → skip fix #2, implement the rest
- Reply "stop" → end the loop, document current state
```

Wait for the user's response. Parse their input:
- **Approval** ("go", "continue", "ok", "proceed"): proceed to Phase C with all suggested fixes
- **Custom instructions** (any other text): treat as additional/replacement guidance for Phase C. Merge with reviewer suggestions where appropriate
- **Skip specific fixes** ("skip 1,3"): remove those fixes from the action list
- **Stop** ("stop", "enough", "done"): terminate the loop, jump to Termination

#### Feishu Notification (if configured)

After parsing the score, check if `~/.claude/feishu.json` exists and mode is not `"off"`:
- Send a `review_scored` notification: "Round N: X/10 — [verdict]" with top 3 weaknesses
- If **interactive** mode and verdict is "almost": send as checkpoint, wait for user reply on whether to continue or stop
- If config absent or mode off: skip entirely (no-op)

#### Phase C: Implement Fixes (if not stopping)

For each action item (highest priority first):

**If `PAPER_REVIEW = true`:**
1. **Paper content changes**: Edit LaTeX source to address reviewer's criticisms (fix claims, improve exposition, add missing citations, clarify notation, etc.)
2. **Recompile PDF**: Run `/paper-compile` or equivalent to regenerate the PDF after edits
3. **Documentation**: Update project notes and review document

**If `PAPER_REVIEW = false` (default):**
1. **Code changes**: Write/modify experiment scripts, model code, analysis scripts
2. **Run experiments**: Deploy to GPU server via SSH + screen/tmux
3. **Analysis**: Run evaluation, collect results, update figures/tables
4. **Documentation**: Update project notes and review document

Prioritization rules:
- Skip fixes requiring excessive compute (flag for manual follow-up)
- Skip fixes requiring external data/models not available
- Prefer reframing/analysis over new experiments when both address the concern
- Always implement metric additions (cheap, high impact)

#### Phase D: Wait for Results

**If `PAPER_REVIEW = true`:**
- Verify the PDF recompiled successfully after LaTeX edits
- Confirm no compilation errors or unresolved citations
- Proceed directly to Phase E

**If `PAPER_REVIEW = false` (default):**
If experiments were launched:
- Monitor remote sessions for completion
- Collect results from output files and logs
- **Training quality check** — if W&B is configured, invoke `/training-check` to verify training was healthy (no NaN, no divergence, no plateau). If W&B not available, skip silently. Flag any quality issues in the next review round.

#### Phase E: Document Round

Append to `review-stage/AUTO_REVIEW.md`:

```markdown
## Round N (timestamp)

### Assessment (Summary)
- Score: X/10
- Verdict: [ready/almost/not ready]
- Key criticisms: [bullet list]

### Reviewer Raw Response

<details>
<summary>Click to expand full reviewer response</summary>

[Paste the COMPLETE raw response from the external reviewer here — verbatim, unedited.
This is the authoritative record. Do NOT truncate or paraphrase.]

</details>

### Debate Transcript (hard + nightmare only)

<details>
<summary>Click to expand debate</summary>

**Claude's Rebuttal:**
[paste rebuttal]

**GPT's Ruling:**
[paste ruling — SUSTAINED / OVERRULED / PARTIALLY SUSTAINED for each]

**Score adjustment**: X/10 → Y/10

</details>

### Actions Taken
- [what was implemented/changed]

### Results
- [experiment outcomes, if any]

### Status
- [continuing to round N+1 / stopping]
- Difficulty: [medium/hard/nightmare]
```

**Write `review-stage/REVIEW_STATE.json`** with current round, thread_id, score, verdict, and any pending experiments.

**Append to `findings.md`** (when `COMPACT = true`): one-line entry per key finding this round:

```markdown
- [Round N] [positive/negative/unexpected]: [one-sentence finding] (metric: X.XX → Y.YY)
```

Increment round counter → back to Phase A.

### Phase F: Presentation Audit (after content loop converges)

**Run once, after the content review loop reaches POSITIVE_THRESHOLD or MAX_ROUNDS.**

The Codex/GPT reviewer excels at content correctness (statistical rigor, claim-evidence alignment, consistency) but systematically misses — and even worsens — presentation quality. In particular, it tends to push numbers, p-values, and formulas into the abstract and introduction, making them read like supplementary statistics tables rather than compelling narratives. This phase corrects that blind spot.

**Claude performs this audit directly (no CLI call):**

1. **Abstract audit.** Check:
   - Count of inline numbers/formulas. Target: **≤ 3** in the entire abstract. If more, replace with qualitative descriptions ("outperforms", "matches", "the majority of") and move numbers to the body.
   - Narrative flow: does it read as problem → gap → contribution → result summary → positioning? Or as a data dump?
   - Compare against reference abstracts in the field. A good abstract has ≤ 1 specific performance number.

2. **Introduction audit.** Check:
   - Are specific p-values, effect sizes, or cell counts quoted before the reader understands the experimental setup? Move to §Experiments.
   - Does the "Contributions" list read as a story or a feature checklist? Each item should start with the *insight*, not the formula.

3. **Anti-patterns to fix:**
   - ❌ "pooled Wilcoxon p = 0.004, n = 95 paired cells" in the abstract
   - ✅ "a statistically significant pooled advantage" in the abstract; exact numbers in §Experiments
   - ❌ "$O(n^{3/2}/\sqrt{H})$" in the abstract
   - ✅ "a quantitative finite-width convergence rate" in the abstract; the bound in §Theory
   - ❌ "median gap $-0.109$, one-sided Wilcoxon $p = 0.004$; dataset-blocked $p = 0.08$, $n = 10$" in the abstract
   - ✅ "outperforms Matérn-5/2 ARD on the majority of datasets" in the abstract

4. **Rule of thumb for abstract numbers:** A reader skimming the abstract should understand WHAT you did and WHY it matters within 30 seconds. Every formula or number that interrupts this flow is a net negative. Save quantitative precision for the body, where the reader has context to interpret it.

5. Apply fixes directly, then log changes in `review-stage/AUTO_REVIEW.md` under `## Presentation Audit`.

### Termination

When loop ends (positive assessment or max rounds):

1. **Run Phase F (Presentation Audit)** — always, even if content score is high
2. Update `review-stage/REVIEW_STATE.json` with `"status": "completed"`
3. Write final summary to `review-stage/AUTO_REVIEW.md`
4. Update project notes with conclusions
5. **Write method/pipeline description** to `review-stage/AUTO_REVIEW.md` under a `## Method Description` section — a concise 1-2 paragraph description of the final method, its architecture, and data flow. This serves as input for `/paper-illustration` in Workflow 3 (so it can generate architecture diagrams automatically).
6. **Generate claims from results** — invoke `/result-to-claim` to convert experiment results from `review-stage/AUTO_REVIEW.md` into structured paper claims. Output: `CLAIMS_FROM_RESULTS.md`. This bridges Workflow 2 → Workflow 3 so `/paper-plan` can directly use validated claims instead of extracting them from scratch. If `/result-to-claim` is not available, skip silently.
7. If stopped at max rounds without positive assessment:
   - List remaining blockers
   - Estimate effort needed for each
   - Suggest whether to continue manually or pivot
8. **Feishu notification** (if configured): Send `pipeline_done` with final score progression table

## Key Rules

- **Large file handling**: If the Write tool fails due to file size, immediately retry using Bash (`cat << 'EOF' > file`) to write in chunks. Do NOT ask the user for permission — just do it silently.

- **Presentation ≠ Content.** The Codex reviewer is systematically blind to readability. It optimizes for statistical defensibility, which drives it to stuff numbers, p-values, and caveats into the abstract/introduction — exactly the opposite of what makes a paper readable. After content convergence, ALWAYS run Phase F (Presentation Audit) to undo this tendency. The abstract should have ≤ 3 numbers; the introduction should tell a story before quoting statistics.

- ALWAYS use `config: {"model_reasoning_effort": "xhigh"}` for maximum reasoning depth
- Save thread_id from first call, use `codex exec resume` for subsequent rounds
- **Anti-hallucination citations**: When adding references during fixes, NEVER fabricate BibTeX. Use the same DBLP → CrossRef → `[VERIFY]` chain as `/paper-write`: (1) `curl -s "https://dblp.org/search/publ/api?q=TITLE&format=json"` → get key → `curl -s "https://dblp.org/rec/{key}.bib"`, (2) if not found, `curl -sLH "Accept: application/x-bibtex" "https://doi.org/{doi}"`, (3) if both fail, mark with `% [VERIFY]`. Do NOT generate BibTeX from memory.
- Be honest — include negative results and failed experiments
- Do NOT hide weaknesses to game a positive score
- Implement fixes BEFORE re-reviewing (don't just promise to fix)
- **Exhaust before surrendering** — before marking any reviewer concern as "cannot address": (1) try at least 2 different solution paths, (2) for experiment issues, adjust hyperparameters or try an alternative baseline, (3) for theory issues, provide a weaker version of the result or an alternative argument, (4) only then concede narrowly and bound the damage. Never give up on the first attempt.
- If an experiment takes > 30 minutes, launch it and continue with other fixes while waiting
- Document EVERYTHING — the review log should be self-contained
- Update project notes after each round, not just at the end

## Prompt Template for Round 2+

```bash
codex exec resume [saved from round 1] -c model_reasoning_effort="xhigh" "$(cat <<'PROMPT'
[Round N update]

Since your last review, we have:
1. [Action 1]: [result]
2. [Action 2]: [result]
3. [Action 3]: [result]

Updated results table:
[paste metrics]

Please re-score and re-assess. Are the remaining concerns addressed?
Same format: Score, Verdict, Remaining Weaknesses, Minimum Fixes.
PROMPT
)" 2>&1
```

## Review Tracing

After each `codex exec` or `codex exec resume` reviewer call, save the trace following `shared-references/review-tracing.md`. Use `tools/save_trace.sh` or write files directly to `.aris/traces/<skill>/<date>_run<NN>/`. Respect the `--- trace:` parameter (default: `full`).
