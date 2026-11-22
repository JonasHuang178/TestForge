# Design

## Context

Phase 1 is implemented on `feat/phase1-generator`: the generation pipeline, a
data-driven device layer, a reference device and a stateless REST API, with 80
passing tests. See proposal.md — Why for the motivation behind recording it.

Two constraints shape this change. First, the specs describe code that already
exists, so writing them is partly an audit: a requirement that does not match
the implementation is a finding, not a licence to edit. Second, the real device
templates and the real plan format are still unknown, so the specs must state
what is genuinely contractual and leave the shape of real-world input to the
next change.

## Goals / Non-Goals

**Goals:**

- Record the Phase 1 contracts as testable requirements, so the upcoming
  adaptation to real templates is a reviewable delta rather than a rewrite.
- Draw capability boundaries that can absorb future requirements without being
  renamed.
- Keep spec and code separable: if the audit finds a mismatch, the spec change
  and the code fix are reviewed independently.

**Non-Goals:**

- No behaviour changes. Nothing in `src/` changes as part of this work except
  where the audit proves the implementation contradicts a recorded contract.
- No specs for work not yet built — the web interface, persistence and
  compilation checks stay out until they are proposed.
- No commitment to the current markdown convention as the final format. It is
  recorded as the default and as configurable, not as fixed.

## Decisions

**Six capabilities along the pipeline's seams, not one per module.**
The boundaries follow the contracts a consumer depends on — how a plan is read,
how names are derived, how code is placed, what a device may declare, how
problems are reported, what HTTP guarantees — rather than the package layout.
The alternative, a single `code-generation` capability, was rejected because for
a code generator that is the catch-all the schema warns against: every future
requirement would land in it and it would stop discriminating. Splitting
`step-naming` out of assembly was deliberate too: identifier stability has its
own invariants (uniqueness, legality, retitling) that have nothing to do with
file placement.

**`diagnostics` is its own capability rather than a section of each stage.**
It is cross-cutting — parsing, naming and assembly all emit diagnostics, and the
API re-exposes them — and the part clients actually couple to is the shape and
the severity semantics, not which stage produced an entry. Describing it once
avoids three divergent copies. The cost is that a reader must follow one
cross-reference to learn what a parse diagnostic looks like.

**Cross-cutting guarantees are stated as requirements, not prose.**
Determinism, idempotent regeneration and statelessness were treated as
conventions in Phase 1 and are easy to erode by accident: a timestamp in a
template, an append instead of a replace, a cache for performance. Each is now
a requirement with a scenario, so erosion fails a test.

**Specs avoid naming internal structure.**
Requirements are written against observable behaviour — marker pairs, status
codes, filename patterns, diagnostic codes — and not against module or class
names. This is what lets the parser, the assembler or the HTTP framework be
replaced without touching a spec, and it is also why diagnostic codes are
specified as stable while messages explicitly are not.

**The audit is a task, not an assumption.**
Rather than asserting that the implementation already satisfies every written
requirement, the task list walks each capability against the code and the test
suite. The expected outcome is a short list of either confirmations or findings.
Writing the specs first and auditing second is what makes a mismatch visible;
auditing while writing would quietly bend the requirement to match the code.

## Risks / Trade-offs

**Retrospective specs can be written to match the code rather than the intent.**
→ The requirements were drafted from the design discussion and the README, which
predate parts of the implementation, and the audit task compares them against
the code afterwards. Any requirement that only holds because the code happens to
behave that way is recorded as an open question instead of being softened.

**Six capabilities is more surface than a 2,000-line codebase strictly needs.**
→ Accepted. The boundaries are the ones the next change has to cut along, and
merging them later is cheaper than renaming a capability that has accumulated
requirements and history.

**Specs recorded before real templates arrive may need amendment.**
→ That is the intended outcome, and the reason for doing this now: an amendment
is a visible delta against a baseline. The risk being avoided is the opposite
one, where real-template work silently changes a contract nobody wrote down. The
requirements most likely to move — heading conventions, the template context —
are stated as configurable rather than fixed.

**The audit may find a genuine mismatch, which expands scope.**
→ A finding is recorded as a task with its spec reference and fixed in a
separate commit, so the formalisation can land even if a fix needs more
discussion.

## Open Questions

- Whether the generated expectation scaffold should fail by default, as the
  reference device does today, or be emitted as a commented-out assertion. This
  is a reference-device choice covered by `device-templates`; it changes no
  requirement.
- Whether diagnostic codes need a documented deprecation policy once an external
  client depends on them. Deferrable until one does.
