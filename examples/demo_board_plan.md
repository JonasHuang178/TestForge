# Test Case: LED Blink

- ID: TC-100
- Device: demo_board
- Author: QA

確認板子上電後 LED 能依指定頻率閃爍。

## Step 1: Power on the board

Apply 5V to the main rail and wait for the regulator to settle.

**Expected:** The power LED turns on within 200 ms.

## Step 2: Set blink rate to 2 Hz

Write 0x02 to the blink control register.

**Expected:** The register reads back 0x02.

## Step 3: Measure the blink period

Count LED transitions over a five second window.

**Expected:** The measured period is 500 ms, within 5 percent.

## Step 4: Power off cleanly

Drop the main rail and confirm the LED goes dark.
