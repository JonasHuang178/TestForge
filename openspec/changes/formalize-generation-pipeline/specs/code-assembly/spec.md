# Spec Delta

## Purpose

Defines how generated code is placed into an output file. Generated files are
meant to be committed and then regenerated as the plan evolves, so placement must
be repeatable and must never disturb code a person wrote around it.

## ADDED Requirements

### Requirement: Paired anchors delimit generated regions

Generated code SHALL be written only between a matching pair of begin and end
markers. The marker spelling SHALL be declared by the device. Everything between
the two marker lines is owned by the generator; everything else in the file is
not.

#### Scenario: Region is filled

- **WHEN** a file contains a begin and end marker pair for an anchor and a
  fragment is generated for it
- **THEN** the fragment appears between the two markers
- **AND** both marker lines remain in place

### Requirement: Regeneration is idempotent

Regenerating from an unchanged plan into an already generated file SHALL produce
byte-identical content. Replacing a filled region SHALL substitute its contents
rather than append to them.

#### Scenario: Second run changes nothing

- **WHEN** a file is generated and then regenerated from the same plan
- **THEN** the two results are byte-identical

#### Scenario: Changed plan replaces the old region

- **WHEN** a region holding `old();` is regenerated from a plan that now yields `new();`
- **THEN** the region contains `new();` and no longer contains `old();`

### Requirement: Hand-written code outside anchors is preserved

Content outside every anchored region SHALL be carried through untouched, so a
generated file can hold fixtures, helpers and includes that the generator does
not manage.

#### Scenario: Hand-written declaration survives

- **WHEN** a person adds a declaration outside the anchors of a generated file
  and the file is regenerated
- **THEN** that declaration is still present
- **AND** the anchored regions reflect the current plan

### Requirement: Injected code matches the marker's indentation

A fragment SHALL be re-indented to the indentation of its begin marker, so an
anchor placed inside a function or namespace body produces correctly indented
code. Blank lines within a fragment SHALL NOT be padded with trailing
whitespace.

#### Scenario: Anchor nested in a function body

- **WHEN** a begin marker is indented by two spaces and the fragment is `a();`
- **THEN** the injected line is indented by two spaces

### Requirement: An empty fragment clears its region

A fragment that renders to nothing SHALL leave its region empty with the marker
pair adjacent, rather than leaving stale content behind.

#### Scenario: Region emptied

- **WHEN** a previously filled region is regenerated with an empty fragment
- **THEN** the end marker immediately follows the begin marker

### Requirement: Malformed anchors are reported, not guessed

Assembly SHALL fail with a specific, distinguishable error when an anchor is
absent, unbalanced or duplicated, and the error SHALL state the exact marker
spelling expected. The system SHALL NOT infer an insertion point when markers
are missing.

#### Scenario: Anchor absent from the file

- **WHEN** a fragment is generated for an anchor the target file does not contain
- **THEN** assembly fails with a missing-anchor error naming the anchor
- **AND** the error states the begin and end marker lines that were expected

#### Scenario: Begin without end

- **WHEN** a file opens an anchor and never closes it
- **THEN** assembly fails with an unbalanced-anchor error

#### Scenario: End without begin

- **WHEN** a file closes an anchor that was never opened
- **THEN** assembly fails with an unbalanced-anchor error

#### Scenario: Anchor appears twice

- **WHEN** a file contains two marker pairs for the same anchor
- **THEN** assembly fails with a duplicate-anchor error

### Requirement: Generation is deterministic

Identical input SHALL produce byte-identical output. Generated code SHALL NOT
contain timestamps, random identifiers or any other value that varies between
runs, except where a device explicitly opts in.

#### Scenario: Repeated generation

- **WHEN** the same plan and device are generated twice in separate processes
- **THEN** every artifact's content is identical

#### Scenario: Archive download

- **WHEN** the same generation is downloaded as an archive twice
- **THEN** the two archives are byte-identical
