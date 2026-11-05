#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "acdata.h"
#include "pcars2data.h"
#include "rf2data.h"
#include "r3e.h"
#include "lmu.h"
#define P(S,f) printf("%s.%s %zu %zu\n", #S, #f, offsetof(S,f), sizeof(((S*)0)->f))
int main(){
 P(struct SPageFilePhysics,fuel); P(struct SPageFilePhysics,tyreWear); P(struct SPageFilePhysics,tyreCoreTemperature);
 P(struct SPageFileStatic,maxFuel); P(struct SPageFileStatic,maxRpm); P(struct SPageFileStatic,carModel); P(struct SPageFileStatic,track);
 P(struct SPageFileGraphic,completedLaps); P(struct SPageFileGraphic,iCurrentTime); P(struct SPageFileGraphic,normalizedCarPosition); P(struct SPageFileGraphic,status);
 P(struct pcars2APIStruct,mTyreWear); P(struct pcars2APIStruct,mTyreTemp); P(struct pcars2APIStruct,mFuelCapacity);
 P(rF2VehicleTelemetry,mWheel); printf("wheel size %zu\n", sizeof(TelemWheelV01)); P(TelemWheelV01,mWear); P(TelemWheelV01,mTemperature); P(TelemWheelV01,mTireCarcassTemperature);
 P(LMUVehicleTelemetry,mWheels); printf("lmuwheel size %zu\n", sizeof(LMUWheel)); P(LMUWheel,mWear); P(LMUWheel,mTireCarcassTemperature);
 P(struct r3e_share,tire_wear); P(struct r3e_share,tire_temp); printf("r3e tire temp size %zu\n", sizeof(r3e_tire_temp));
 return 0; }
