# ConsultClaude Workflow And Models

## Core Loop

1. Decide why Claude is needed: divergent ideas, layout critique, UX flow review, copy direction, architecture rethink, logic stress test, or independent review.
2. Curate context. Prefer a short task summary plus the smallest relevant snippets or files. Do not pass secrets, credentials, private tokens, `.env` files, or unrelated repo dumps.
3. Pick mode and model. Use a mode preset unless the user names a model.
4. Ask for a bounded output: options, critique, risks, recommendation, or validation checklist.
5. Synthesize Claude's response. Codex keeps ownership of implementation, tests, and final answer.
6. Record durable conclusions in the task `progress.md` when the project uses one.

## Mode Presets

| Mode | Default model | Effort | Use for |
| --- | --- | --- | --- |
| `quick` | `sonnet` | `low` | Fast second opinion on one narrow question. |
| `design` | `opus` | `medium` | UX, product feel, hierarchy, states, accessibility. |
| `layout` | `opus` | `medium` | Responsive layout, density, control placement, scanability. |
| `creative` | `opus` | `medium` | Naming, concept directions, visual ideas, product angles. |
| `copy` | `sonnet` | `medium` | User-facing copy, messaging, onboarding text, CTAs. |
| `logic` | `opus` | `high` | Assumptions, invariants, algorithms, edge cases. |
| `architecture` | `opus` | `high` | Boundaries, migration plans, data flow, tradeoffs. |
| `review` | `sonnet` | `medium` | Independent critique of an approach, diff, or plan. |
| `stress-test` | `opus` | `high` | Skeptical pass before risky or expensive decisions. |
| `general` | `sonnet` | `medium` | Anything that does not fit another mode. |

Pass `model` explicitly for full control. The bridge accepts Claude CLI aliases such as `sonnet`, `opus`, and `fable`, plus full model IDs supported by the installed Claude CLI. Prefer aliases for durability unless the user explicitly asks for a specific full model.

## Model Choice Heuristics

- Use `sonnet` for routine coordination, review, copy cleanup, and cost-sensitive questions.
- Use `opus` when the value is in deep judgment: major UI direction, system architecture, subtle reasoning, or high-risk tradeoffs.
- Use `fable` only when available and the task benefits from broad creative exploration; keep Codex responsible for grounding the result.
- Use `fallback_model` for resilience. `sonnet` is a practical fallback for most `opus` calls.
- Use `effort=high` or above only when the decision is expensive to reverse or the prompt asks for adversarial reasoning.

## Context Hygiene

- Pass summaries before files. Claude should not need the whole repo for a design or reasoning consultation.
- Prefer `context_files` for small files that define the relevant surface: a screen component, CSS file, requirements doc, or current plan.
- Avoid screenshots unless the bridge is extended to support image input. For screenshots, describe the visible layout or use a separate visual-analysis-capable workflow.
- Keep Claude advisory by default with `allow_tools=none`. Use `read-only` only when Claude truly needs to inspect files directly.
- Never grant edit or shell access from this bridge for ordinary consultations. Codex should perform edits and verification.

## Claude App Fallback

The automatic request/response loop uses Claude Code CLI. The Claude app path is a manual fallback: call the bridge with `transport=app-handoff` to write a prepared prompt file under `.codex/claude-handoffs/`, then paste that prompt into the app. Do not block a Codex task waiting for an app response unless the user explicitly wants a manual handoff.

## Prompt Shapes

Design critique:

```text
Mode: design
Question: Critique this dashboard layout before implementation.
Context: product goal, target user, current component tree, constraints.
Ask for: strongest layout option, hierarchy issues, mobile risks, accessibility risks, and what to verify.
```

Logic stress test:

```text
Mode: logic
Question: Challenge this sync algorithm before I implement it.
Context: invariants, failure modes, concurrency assumptions, persistence model.
Ask for: broken assumptions, counterexamples, simpler alternatives, and tests.
```

Creative ideation:

```text
Mode: creative
Question: Generate three distinct interaction concepts for this habit-tracking app.
Context: audience, tone, platform, existing visual direction.
Ask for: concepts, why each works, what to avoid, and recommended first direction.
```
