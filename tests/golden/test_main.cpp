#include <iostream>

// === TESTFORGE:TEST_CASES:BEGIN ===
// Test case: print all info
// Plan ID:   TC-100
// Plan line 15
int printAllInfo()
{
    // Step1 Print the build version
    // TODO: implement this step.

    // Step2 Print the device id
    // TODO: implement this step.

    // Step3 Print the uptime
    // TODO: implement this step.

    return 0;
}

// Test case: check sensors
// Plan ID:   TC-101
// Plan line 20
int checkSensors()
{
    // Step1 Read the temperature
    // TODO: implement this step.

    // Step2 Read the humidity
    // TODO: implement this step.

    return 0;
}
// === TESTFORGE:TEST_CASES:END ===

int main()
{
    // === TESTFORGE:CALLS:BEGIN ===
    // Step1  TC-100
    printAllInfo();

    // Step2  TC-101
    checkSensors();
    // === TESTFORGE:CALLS:END ===

    return 0;
}
