# Spec Delta

## Purpose

Defines the markdown test plan format TestForge accepts and how a plan is
translated into the intermediate representation that every later stage consumes.
Plans are written and maintained by engineers, so the format must tolerate
inconsistency and report what it found rather than demand perfection.

## ADDED Requirements

### Requirement: Test case detection

The parser SHALL treat a heading at the configured case heading level as the
start of a test case, and SHALL support any number of test cases in one
document. Each case is generated independently.

#### Scenario: Multiple cases in one document

- **WHEN** a plan contains two `# Test Case:` headings
- **THEN** the result contains two cases, each carrying only its own steps
- **AND** each case records the 1-based position at which it appeared

#### Scenario: Case title prefix is removed

- **WHEN** a case heading reads `# Test Case: Sensor Initialization`
- **THEN** the case title is `Sensor Initialization`, without the prefix

### Requirement: Step detection and positional indexing

The parser SHALL treat a heading at the configured step heading level as a step.
The `Step` keyword and the number are both optional. The step's position in the
document SHALL be authoritative for indexing and naming; a number written in the
heading is recorded separately and never renumbers the step.

#### Scenario: Step heading spellings

- **WHEN** a case contains the headings `## Step 1: Alpha`, `## 2. Beta` and `## Gamma`
- **THEN** three steps are produced with positions 1, 2 and 3
- **AND** the declared numbers are 1, 2 and none respectively

#### Scenario: Misnumbered plan keeps document order

- **WHEN** a case contains `## Step 1: A` followed by `## Step 7: B`
- **THEN** the second step has position 2, not 7
- **AND** a `step.index_mismatch` warning is reported against that heading

### Requirement: Step bodies preserve raw markdown

The parser SHALL carry each step's body through as the author's original
markdown, without rendering, reflowing or re-serializing it, so that templates
decide how to present it.

#### Scenario: Fenced code block survives intact

- **WHEN** a step body contains a fenced code block
- **THEN** the step description contains that block with its fences and content
  byte-for-byte as written

### Requirement: Headings inside fenced blocks are not structure

The parser SHALL determine document structure from the markdown token stream, so
that a line beginning with `#` inside a fenced code block is content and not a
heading.

#### Scenario: Hash inside a fence is ignored

- **WHEN** a step body contains a fenced block whose content is `## Step 2: Not a step`
- **THEN** no second step is produced

### Requirement: Case metadata block

The parser SHALL read a bullet list placed directly under a case heading as
`Key: Value` metadata, normalising keys to lowercase with underscores. A bullet
that is not a key-value pair SHALL be kept as description and reported, not
discarded.

#### Scenario: Metadata is extracted

- **WHEN** a case heading is followed by `- ID: TC-001` and `- Author: Jonas Huang`
- **THEN** the case metadata contains `id` as `TC-001` and `author` as `Jonas Huang`
- **AND** the case identifier resolves to `TC-001`

#### Scenario: Non key-value bullet is retained

- **WHEN** the preamble bullet list contains a plain prose bullet
- **THEN** that line appears in the case description
- **AND** a `metadata.unparsed_line` diagnostic is reported for it

### Requirement: Expectation block

The parser SHALL recognise a paragraph opening with an expectation label as the
step's expected outcome and separate it from the description. Bold markers around
the label SHALL NOT leak into the captured text, and bold markers belonging to
the text itself SHALL be preserved.

#### Scenario: Accepted label spellings

- **WHEN** a step body contains any of `**Expected:**`, `**Expected**:`,
  `Expected:`, `Expected result:` or `預期結果：` followed by text
- **THEN** that text becomes the step's expected outcome
- **AND** it does not appear in the step description

#### Scenario: Bold text in the expectation is kept

- **WHEN** a step body contains `Expected: **READY** is asserted`
- **THEN** the expected outcome is `**READY** is asserted`

#### Scenario: A word merely starting with the label is not an expectation

- **WHEN** a step body contains the sentence `Expectedly the device fails.`
- **THEN** the step has no expected outcome

### Requirement: Configurable heading levels

The case and step heading levels SHALL be configurable per device and
overridable per request, so a team can keep an existing plan layout rather than
rewrite its documents.

#### Scenario: Steps at level three

- **WHEN** a plan uses `###` for steps and the step heading level is set to 3
- **THEN** those headings are parsed as steps

#### Scenario: Default level does not match

- **WHEN** the same plan is parsed with the default step heading level of 2
- **THEN** no steps are found for that case

### Requirement: Optional case prefix enforcement

When case prefix enforcement is enabled, the parser SHALL treat only headings
beginning with a recognised case prefix as test cases, so that documents using
the case heading level for unrelated sections can still be parsed.

#### Scenario: Unrelated top-level heading is skipped

- **WHEN** a plan contains `# Introduction` and `# Test Case: Real` and prefix
  enforcement is enabled
- **THEN** only `Real` is produced as a case

### Requirement: Plans that yield nothing are rejected

The parser SHALL report an error-severity diagnostic, and produce no cases, when
a document contains no case heading or when every case it contains has no steps.
A case without steps SHALL be skipped rather than emitted empty.

#### Scenario: No case heading

- **WHEN** a document contains prose but no case heading
- **THEN** no cases are produced and `document.no_test_case` is reported as an error

#### Scenario: Every case is empty

- **WHEN** a document's only case has no step headings
- **THEN** `case.no_steps` is reported as a warning for that case
- **AND** `document.no_usable_case` is reported as an error
