# Tasks

## 1. Audit each capability against the implementation

Each task reads one spec against the code and the test suite and records the
outcome as either a confirmation or a finding. A finding is written into
`audit-findings.md` with its spec reference; it is not fixed here.

- [ ] 1.1 Audit `specs/test-plan-parsing/spec.md` against `src/testforge/core/parser.py` and `tests/test_parser.py`; verify every requirement is either exercised by a named test or listed in `audit-findings.md`
- [x] 1.2 Audit `specs/step-naming/spec.md` against `src/testforge/device_api.py` and `tests/test_python_device.py`; verify the same (rewritten: the naming rule now lives in each device's module, not in a pattern language)
- [ ] 1.3 Audit `specs/code-assembly/spec.md` against `src/testforge/core/assembler.py` and `tests/test_assembler.py`; verify the same
- [x] 1.4 Audit `specs/device-templates/spec.md` against `src/testforge/devices/` and `tests/test_python_device.py`; verify the same (rewritten: devices are now Python modules, the declarative manifest system was removed on request)
- [ ] 1.5 Audit `specs/diagnostics/spec.md` against `src/testforge/core/diagnostics.py` and every call site that emits a diagnostic; verify that each code named in the spec is produced by the code and asserted somewhere in the suite
- [ ] 1.6 Audit `specs/generation-api/spec.md` against `src/testforge/api/` and `tests/test_api.py`; verify the status code table in the spec matches `_STATUS_BY_TYPE` entry for entry
- [ ] 1.7 Write `audit-findings.md` listing every mismatch found, each with its spec reference and whether the spec or the code is wrong; verify the file exists and that an empty result is stated explicitly rather than left implied

## 2. Close scenario coverage gaps

The specs were written from the contracts, not from the tests, so some scenarios
have no test. Each task adds the missing test and states the assertion.

- [ ] 2.1 Add a test for the `metadata.unparsed_line` scenario in `test-plan-parsing`, asserting a non key-value preamble bullet lands in the case description and emits that code; verify `pytest tests/test_parser.py` passes
- [ ] 2.3 Add a test for the device-templates scenario "Shared directory overrides a project device", using a temporary directory as a later search root; verify `pytest tests/test_python_device.py` passes
- [ ] 2.4 Add a test for the device-templates scenario "Example output compiles" that compiles both example devices' output under `-Wall -Wextra -Werror` and asserts a non-zero run exit code, skipped when no compiler is present; verify it passes locally and skips cleanly when no compiler is available
- [x] 2.7 Preserve the existing file's line endings on regeneration, with tests for CRLF, LF and mixed input; verify `pytest tests/test_assembler.py` passes (found while checking Windows behaviour: a CRLF file was being rewritten as LF, reporting every line as changed in the next diff)
- [ ] 2.5 Add a test for the generation-api scenario "Server fault withholds internals", asserting a 5xx body carries no `details` content; verify `pytest tests/test_api.py` passes
- [ ] 2.6 Run the full suite and confirm no regression; verify `pytest` reports zero failures and a test count greater than the 80 recorded in the proposal

## 3. Make the specs navigable from the code

- [ ] 3.1 Add a short "Specs" section to `README.md` pointing at `openspec/specs/` and naming the six capabilities with one line each; verify the section renders and every path it names exists after archive
- [ ] 3.2 Record in `README.md` that diagnostic codes are contractual while messages are not, matching the `diagnostics` spec; verify the statement is present and consistent with the spec's wording

## 4. Integration verification

- [ ] 4.1 Run `openspec validate formalize-generation-pipeline --strict` and confirm it reports the change as valid
- [ ] 4.2 Walk the README quick start on a clean clone of the branch and confirm each documented command runs as written, including `pytest`, `testforge parse`, `testforge generate` into an existing directory, and `testforge serve` serving its published API description

## Workflow follow-up

- Archive the change once the audit findings have been reviewed, promoting the six capability specs into `openspec/specs/`.
- Verify after archive that `openspec list --specs` reports all six capabilities and that each retains the `## Purpose` written here rather than a placeholder.
