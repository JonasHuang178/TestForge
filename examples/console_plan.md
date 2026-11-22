# Console App Test Plan

## Purpose

Smoke test for the console build. Everything above `## Test Case List` is
prose: TestForge never looks at it, so revision history and environment notes
can live here safely.

## Environment

### Hardware

A heading at test-case level, but outside the list — it is ignored.

## Test Case List

### print all info

#### Step 1 Print the build version

Call the version helper and write it to stdout.

**Expected:** A non-empty version string is printed.

#### Step 2 Print the device id

Read the id from EEPROM and print it as hex.

#### Step 3 Print the uptime

Read the tick counter and print it in seconds.

### check sensors

#### Step 1 Read the temperature

Poll the sensor once and print the reading.

**Expected:** The reading is between -40 and 85 degrees.

#### Step 2 Read the humidity

Poll the second channel.
