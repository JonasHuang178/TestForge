#include <iostream>

// === TESTFORGE:TEST_CASES:BEGIN ===
// Test case: print all info
// Plan line 17
int printAllInfo()
{
    // Step1 Print the build version
    // Call the version helper and write it to stdout.
    // Expected: A non-empty version string is printed.
    // TODO: implement this step.

    // Step2 Print the device id
    // Read the id from EEPROM and print it as hex.
    // TODO: implement this step.

    // Step3 Print the uptime
    // Read the tick counter and print it in seconds.
    // TODO: implement this step.

    return 0;
}

// Test case: check sensors
// Plan line 33
int checkSensors()
{
    // Step1 Read the temperature
    // Poll the sensor once and print the reading.
    // Expected: The reading is between -40 and 85 degrees.
    // TODO: implement this step.

    // Step2 Read the humidity
    // Poll the second channel.
    // TODO: implement this step.

    return 0;
}
// === TESTFORGE:TEST_CASES:END ===

int main()
{
    // === TESTFORGE:CALLS:BEGIN ===
    // Step1
    printAllInfo();

    // Step2
    checkSensors();
    // === TESTFORGE:CALLS:END ===

    return 0;
}
