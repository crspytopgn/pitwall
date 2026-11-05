#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "pcars2data.h"
#include "rf2data.h"
#include "r3e.h"
#include "lmu.h"
#define T(x) _Generic((x), float:"f", double:"d", int32_t:"i", uint32_t:"I", int8_t:"b", uint8_t:"B", char:"c", bool:"?", int16_t:"h", uint16_t:"H", default:"?")
#define F(S,fld) printf("\"%s.%s\": [%zu, %zu, \"%s\"],\n", #S, #fld, offsetof(S,fld), sizeof(((S*)0)->fld), T(((S*)0)->fld))
#define Z(S) printf("\"%s.__size__\": [%zu, 0, \"\"],\n", #S, sizeof(S))
int main(){
 printf("{\n");
 F(struct pcars2APIStruct,mVersion);F(struct pcars2APIStruct,mGameState);F(struct pcars2APIStruct,mViewedParticipantIndex);F(struct pcars2APIStruct,mParticipantInfo);
 F(struct pcars2APIStruct,mUnfilteredThrottle);F(struct pcars2APIStruct,mUnfilteredBrake);F(struct pcars2APIStruct,mUnfilteredSteering);F(struct pcars2APIStruct,mUnfilteredClutch);
 F(struct pcars2APIStruct,mCarName);F(struct pcars2APIStruct,mTrackLocation);F(struct pcars2APIStruct,mTrackVariation);F(struct pcars2APIStruct,mTrackLength);
 F(struct pcars2APIStruct,mBestLapTime);F(struct pcars2APIStruct,mLastLapTime);F(struct pcars2APIStruct,mCurrentTime);F(struct pcars2APIStruct,mFuelLevel);
 F(struct pcars2APIStruct,mSpeed);F(struct pcars2APIStruct,mRpm);F(struct pcars2APIStruct,mMaxRPM);F(struct pcars2APIStruct,mGear);F(struct pcars2APIStruct,mTyreTemp);F(struct pcars2APIStruct,mSequenceNumber);F(struct pcars2APIStruct,mLapInvalidated);
 Z(ParticipantInfo);F(ParticipantInfo,mIsActive);F(ParticipantInfo,mWorldPosition);F(ParticipantInfo,mCurrentLapDistance);F(ParticipantInfo,mLapsCompleted);
 F(struct rF2Telemetry,mVersionUpdateBegin);F(struct rF2Telemetry,mVersionUpdateEnd);F(struct rF2Telemetry,mNumVehicles);F(struct rF2Telemetry,mVehicles);Z(rF2VehicleTelemetry);
 F(rF2VehicleTelemetry,mID);F(rF2VehicleTelemetry,mElapsedTime);F(rF2VehicleTelemetry,mLapNumber);F(rF2VehicleTelemetry,mLapStartET);F(rF2VehicleTelemetry,mVehicleName);F(rF2VehicleTelemetry,mTrackName);
 F(rF2VehicleTelemetry,mPos);F(rF2VehicleTelemetry,mLocalVel);F(rF2VehicleTelemetry,mGear);F(rF2VehicleTelemetry,mEngineRPM);F(rF2VehicleTelemetry,mEngineMaxRPM);
 F(rF2VehicleTelemetry,mUnfilteredThrottle);F(rF2VehicleTelemetry,mUnfilteredBrake);F(rF2VehicleTelemetry,mUnfilteredClutch);F(rF2VehicleTelemetry,mUnfilteredSteering);F(rF2VehicleTelemetry,mFuel);F(rF2VehicleTelemetry,mFuelCapacity);
 F(struct rF2Scoring,mVersionUpdateBegin);F(struct rF2Scoring,mVersionUpdateEnd);F(struct rF2Scoring,mScoringInfo);F(struct rF2Scoring,mVehicles);Z(rF2VehicleScoring);
 F(rF2ScoringInfo,mTrackName);F(rF2ScoringInfo,mNumVehicles);F(rF2ScoringInfo,mGamePhase);F(rF2ScoringInfo,mInRealtime);F(rF2ScoringInfo,mLapDist);
 F(rF2VehicleScoring,mID);F(rF2VehicleScoring,mIsPlayer);F(rF2VehicleScoring,mTotalLaps);F(rF2VehicleScoring,mBestLapTime);F(rF2VehicleScoring,mLastLapTime);F(rF2VehicleScoring,mLapDist);F(rF2VehicleScoring,mVehicleName);
 F(struct LMUObject,generic);F(struct LMUObject,scoring);F(struct LMUObject,telemetry);
 F(LMUScoringData,scoringInfo);F(LMUScoringData,vehScoringInfo);Z(LMUVehicleScoring);
 F(LMUScoringInfo,mTrackName);F(LMUScoringInfo,mNumVehicles);F(LMUScoringInfo,mGamePhase);F(LMUScoringInfo,mInRealtime);F(LMUScoringInfo,mLapDist);
 F(LMUVehicleScoring,mID);F(LMUVehicleScoring,mIsPlayer);F(LMUVehicleScoring,mTotalLaps);F(LMUVehicleScoring,mBestLapTime);F(LMUVehicleScoring,mLastLapTime);F(LMUVehicleScoring,mLapDist);F(LMUVehicleScoring,mVehicleName);
 F(LMUTelemetryData,activeVehicles);F(LMUTelemetryData,playerVehicleIdx);F(LMUTelemetryData,playerHasVehicle);F(LMUTelemetryData,telemInfo);Z(LMUVehicleTelemetry);
 F(LMUVehicleTelemetry,mID);F(LMUVehicleTelemetry,mElapsedTime);F(LMUVehicleTelemetry,mLapNumber);F(LMUVehicleTelemetry,mLapStartET);F(LMUVehicleTelemetry,mVehicleName);F(LMUVehicleTelemetry,mTrackName);
 F(LMUVehicleTelemetry,mPos);F(LMUVehicleTelemetry,mLocalVel);F(LMUVehicleTelemetry,mGear);F(LMUVehicleTelemetry,mEngineRPM);F(LMUVehicleTelemetry,mEngineMaxRPM);
 F(LMUVehicleTelemetry,mUnfilteredThrottle);F(LMUVehicleTelemetry,mUnfilteredBrake);F(LMUVehicleTelemetry,mUnfilteredClutch);F(LMUVehicleTelemetry,mUnfilteredSteering);F(LMUVehicleTelemetry,mFuel);F(LMUVehicleTelemetry,mFuelCapacity);
 F(struct r3e_share,version_major);F(struct r3e_share,game_paused);F(struct r3e_share,game_in_menus);F(struct r3e_share,game_in_replay);F(struct r3e_share,track_name);F(struct r3e_share,layout_name);F(struct r3e_share,layout_length);
 F(struct r3e_share,completed_laps);F(struct r3e_share,lap_distance);F(struct r3e_share,lap_distance_fraction);F(struct r3e_share,lap_time_best_self);F(struct r3e_share,lap_time_previous_self);F(struct r3e_share,lap_time_current_self);
 F(struct r3e_share,car_speed);F(struct r3e_share,engine_rps);F(struct r3e_share,max_engine_rps);F(struct r3e_share,gear);F(struct r3e_share,car_cg_location);F(struct r3e_share,fuel_left);F(struct r3e_share,fuel_capacity);
 F(struct r3e_share,throttle_raw);F(struct r3e_share,brake_raw);F(struct r3e_share,clutch_raw);F(struct r3e_share,steer_input_raw);
 printf("\"_\": 0}\n");
}
