# Today

Open Today in the shared header (`/projects?view=daily`). It works locally without
AI or microphone. Project selection filters attention, plan and history; the
owner's current focus remains shared across the workspace.

## One focus

Choose a task and **Save focus**, or **Make current task** in its card. It survives
reload/windows without changing the task's status. Goal and next step appear
first; method/rationale expand or can be recalled before revealing. A completed
focus asks you to choose another rather than automatically selecting one.

## Questions and results

In a task, **Request decision** contains one concrete question and recommendation.
An agent can submit the same through the local CLI/API. One task has one open
question; a duplicate request does not create another. Today shows up to three,
with **All questions** for the rest. Answer in the card with its current context.

An answer is recorded in history and returned to the agent. It does not accept a
delivery or rewrite the method automatically. If the basis changed since the
question, a stale reply cannot overwrite the current version. Worker agents
cannot answer for the owner, choose focus or select recall topics.

**Results awaiting review** is separate from explicit questions. A Review status
does not invent a decision request; historical provisional statuses are separate.
The collapsed **Answered · N** history shows question, answer and time. Chat-sourced
answers additionally show quote/session/source location, labelled as recorded
by an agent, distinct from an owner's native UI answer.

## Near-term plan

Up to six upcoming/current items across seven days from today in Moscow are
shown: meetings, task intervals/deadlines and optional article dates. Finished
intervals hide, overlaps remain labelled. Open the complete week from here.
External personal calendar entries remain shared and labelled; they come from
the last local snapshot, not an AI call or automatic publication.

## Optional recall

Select **Revisit important decision** in a card with goal, method and rationale.
Today offers at most two topics. Try to recall, reveal and compare, then self-rate:
not recalled → one day; partly → three days; remembered → seven days. Completed
tasks can still be revisited. Content changes can reset the basis; schedule/status
changes do not reset newer content-fingerprinted ratings. Legacy ratings can be
revision-based. The retelling is not saved or model-graded; no reminders exist.

Closing an obsolete task removes it from focus/attention/task plan/recall but
keeps evidence, answers and ratings. Restore it explicitly from Closed. Independent
meeting/publication events remain on the calendar even if a related task closes.

## Agent records

The worker reads `daily`, posts `decision-request` with the read revision and
recommendation, and rereads `context` after a conflict. These are local actions,
not a reason to infer a question from every old conversation.

`decision-answer --json-file` can record a real supported user-chat reply. It
requires exact question, full quote, card/decision revisions and a registered
primary `source_span`. Codex JSONL and Python-3.14 Zstandard journals are supported;
an agent's paraphrase is not a substitute. The prefix is hashed from the original,
with an 8 MiB message limit, 120 s read deadline and a 512 MiB decompressed-prefix
limit for compressed input. Large plain journals are read incrementally.

Use the same request ID/body when retrying. Different content or stale revisions
conflict. Recording a reply raises the task revision but does not accept work,
resolve knowledge or grant owner-only permissions. See [Projects](Projects.md).
