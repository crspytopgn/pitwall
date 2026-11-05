#include <stdio.h>
#include <stddef.h>
#include <stdbool.h>
#include "scs2data.h"
#define P(f) printf("%s %zu %zu\n", #f, offsetof(struct scs2TelemetryMap_s, f), sizeof(((struct scs2TelemetryMap_s*)0)->f))
int main(){ P(sdkActive);P(paused);P(time);P(scs_values.game);P(truck_i.gear);P(truck_i.gearDashboard);P(config_f.fuelCapacity);P(config_f.engineRpmMax);
 P(truck_f.speed);P(truck_f.engineRpm);P(truck_f.userSteer);P(truck_f.userThrottle);P(truck_f.userBrake);P(truck_f.userClutch);P(truck_f.fuel);
 P(truck_dp.coordinateX);P(truck_dp.coordinateY);P(truck_dp.coordinateZ);P(config_s.truckBrand);P(config_s.truckName);
 printf("size %zu\n", sizeof(struct scs2TelemetryMap_s)); return 0; }
