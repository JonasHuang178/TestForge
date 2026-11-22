# Proposal

## Why

TestForge's Phase 1 generator is implemented and working, but its contracts live
only in code, docstrings and a README. The decisions that matter most — what the
IR means, how anchors make regeneration safe, what a device manifest may declare,
what the HTTP surface guarantees — were settled in discussion and never written
down as requirements anyone can check against.

This becomes a problem at the next step. The real device templates and the real
test plan format are still unknown, and adapting to them will touch the parser's
heading rules, the manifest schema and the template contract. Without a recorded
baseline there is nothing to distinguish "we deliberately changed the contract"
from "we broke it while fitting a template". This change records the Phase 1
behaviour as specs so that the adaptation work has something to be measured
against.

## What Changes

- No production code changes. This change documents behaviour that already
  exists on `feat/phase1-generator` and is covered by 80 passing tests.
- Six capabilities are introduced as specs, each owning the requirements for one
  contract of the pipeline `markdown plan -> IR -> code fragments -> assembled C++`.
- Three cross-cutting guarantees are stated explicitly as requirements rather
  than left as conventions:
  - **Determinism** — identical input yields byte-identical output, with no
    timestamps or generated ids. Golden-file tests and reviewable diffs on
    committed generated code both depend on it.
  - **Idempotent regeneration** — only the span between a paired anchor's
    markers is rewritten, so hand-written code around it survives.
  - **Statelessness** — nothing persists between requests; a client that wants
    regeneration sends the current file content back.
- The known gaps are recorded as open questions against the specs they affect,
  so the next change starts from a written list rather than from memory.

## Capabilities

### New Capabilities

- `test-plan-parsing`: The markdown test plan format and its translation into
  the IR — case and step detection, metadata, expectation blocks, configurable
  heading levels, and the raw-markdown guarantee for step bodies.
- `step-naming`: Deriving C++ identifiers from human step titles — the pattern
  language, stability under retitling, keyword escaping, non-ASCII handling and
  deduplication.
- `code-assembly`: Anchor-based injection — paired marker semantics, indentation
  handling, idempotent regeneration, and the error cases for missing,
  unbalanced or duplicated anchors.
- `device-templates`: The device manifest contract — what a manifest declares,
  the template context available to authors, load-time validation, and device
  discovery and shadowing.
- `diagnostics`: The structured problem-reporting contract shared by every
  stage — severity semantics, stable codes, and the rule that recoverable
  problems are returned rather than raised.
- `generation-api`: The HTTP surface — resources, request and response shapes,
  the `existing_files` regeneration round trip, status code assignment, the
  error envelope, and the response representations for download.

### Modified Capabilities

None. The project has no existing specs.

## Impact

- **Specs**: six new capability specs under
  `openspec/changes/formalize-generation-pipeline/specs/`, promoted to
  `openspec/specs/` on archive.
- **Code**: none. If writing a requirement exposes a genuine mismatch with the
  implementation, that is recorded as a task rather than silently fixed, so the
  spec and the fix stay separately reviewable.
- **Downstream work**: the adaptation to real device templates and real plan
  formats becomes a delta against these specs instead of an open-ended rewrite.
- **Dependencies**: none added. The OpenSpec CLI (`@fission-ai/openspec`) is a
  development tool, not a runtime dependency of the package.
