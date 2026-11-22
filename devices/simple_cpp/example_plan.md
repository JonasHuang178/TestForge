# Console App Test Plan

## Purpose

這一段 TestForge 不會讀取。修訂紀錄、環境說明、負責人都可以安心放在
`## Test Case List` 之前。

## Environment

### Hardware

這是一個 case 層級的標題，但不在 Test Case List 區段裡，所以會被忽略。

## Test Case List

### print all info

- ID: TC-100
- Owner: QA

印出韌體的基本資訊，確認主控台輸出管線是通的。

#### Step 1 Print the build version

Call the version helper and write it to stdout.

**Expected:** A non-empty version string is printed.

#### Step 2 Print the device id

Read the id from EEPROM and print it as hex.

```
> GET_ID
< 0x4A 0x1F 0x00 0x02
```

**Expected:** The id matches the label on the board.

#### Step 3 Print the uptime

Read the tick counter and print it in seconds.

### check sensors

- ID: TC-101

#### Step 1 Read the temperature

Poll the sensor once and print the reading.

**Expected:** The reading is between -40 and 85 degrees.

#### Step 2 Read the humidity

Poll the second channel.
