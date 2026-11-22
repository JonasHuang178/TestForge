# Test Case: Sensor Initialization Sequence

- ID: TC-001
- Author: Jonas Huang
- Device: example_device
- Priority: High

Verifies that the sensor comes up cleanly from a cold start and reports a
usable baseline reading before any measurement is requested.

## Step 1: Power on the device

Drive the enable line high and wait for the regulator to settle.

**Expected:** The READY flag is asserted within 500 ms.

## Step 2: Read firmware version

Issue the `GET_VERSION` command over the control bus and capture the reply.

```
> 0x01 0x00
< 0x01 0x02 0x0A
```

**Expected:** Reported version is at least 1.2.

## Step 3: Acquire baseline sample

Request a single-shot measurement with the default gain.

Expected result: The sample is inside the calibration window and the error
register reads zero.

## Step 4: Verify idle current draw

Measure supply current with the sensor idle for ten seconds.

# Test Case: Sensor Fault Recovery

- ID: TC-002
- Device: example_device

## Step 1: Inject a bus timeout

Hold the clock line low long enough to trip the bus watchdog.

**Expected:** The driver reports `ERR_BUS_TIMEOUT` and does not hang.

## Step 2: Issue a soft reset

Send the reset opcode and re-run initialization.

**Expected:** The device returns to READY and the error register is cleared.
