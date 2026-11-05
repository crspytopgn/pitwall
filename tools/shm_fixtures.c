/* Writes shared-memory fixtures using the simapi C headers so Pitwall's
   Python readers can be checked against the real struct layouts. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include "pcars2data.h"
#include "rf2data.h"
#include "r3e.h"
#include "lmu.h"
static void dump(const char *p, void *d, size_t n){ FILE *f=fopen(p,"wb"); fwrite(d,1,n,f); fclose(f); }
int main(int argc, char **argv){
  const char *dir = argc > 1 ? argv[1] : ".";
  char path[512];
  /* AMS2 */
  struct pcars2APIStruct *pc = calloc(1, sizeof *pc);
  pc->mGameState = 2; pc->mViewedParticipantIndex = 3;
  pc->mParticipantInfo[3].mIsActive = 1;
  pc->mParticipantInfo[3].mWorldPosition[0]=10; pc->mParticipantInfo[3].mWorldPosition[1]=2; pc->mParticipantInfo[3].mWorldPosition[2]=-30;
  pc->mParticipantInfo[3].mCurrentLapDistance=1234.5f; pc->mParticipantInfo[3].mLapsCompleted=4;
  pc->mUnfilteredThrottle=0.75f; pc->mUnfilteredBrake=0.25f; pc->mUnfilteredSteering=-0.5f; pc->mUnfilteredClutch=0.1f;
  strcpy(pc->mCarName,"Formula Vintage"); strcpy(pc->mTrackLocation,"Interlagos"); strcpy(pc->mTrackVariation,"GP");
  pc->mTrackLength=4309.0f; pc->mBestLapTime=71.5f; pc->mLastLapTime=72.25f; pc->mCurrentTime=30.5f; pc->mFuelLevel=0.4f;
  pc->mSpeed=55.5f; pc->mRpm=7000; pc->mMaxRPM=9000; pc->mGear=4; pc->mTyreTemp[0]=80; pc->mTyreTemp[3]=85; pc->mSequenceNumber=10;
  snprintf(path,sizeof path,"%s/pcars2.bin",dir); dump(path, pc, sizeof *pc);
  /* rF2 */
  struct rF2Telemetry *t = calloc(1, sizeof *t); struct rF2Scoring *s = calloc(1, sizeof *s);
  t->mVersionUpdateBegin=t->mVersionUpdateEnd=5; t->mNumVehicles=2;
  t->mVehicles[1].mID=42; t->mVehicles[1].mElapsedTime=100.0; t->mVehicles[1].mLapStartET=60.0; t->mVehicles[1].mLapNumber=3;
  strcpy(t->mVehicles[1].mVehicleName,"Oreca 07"); strcpy(t->mVehicles[1].mTrackName,"Spa");
  t->mVehicles[1].mPos.x=1; t->mVehicles[1].mPos.y=2; t->mVehicles[1].mPos.z=3;
  t->mVehicles[1].mLocalVel.x=3; t->mVehicles[1].mLocalVel.y=0; t->mVehicles[1].mLocalVel.z=-4;
  t->mVehicles[1].mGear=5; t->mVehicles[1].mEngineRPM=8000; t->mVehicles[1].mEngineMaxRPM=9500;
  t->mVehicles[1].mUnfilteredThrottle=1.0; t->mVehicles[1].mUnfilteredBrake=0.0; t->mVehicles[1].mUnfilteredSteering=0.2; t->mVehicles[1].mUnfilteredClutch=0;
  t->mVehicles[1].mFuel=30; t->mVehicles[1].mFuelCapacity=75;
  s->mVersionUpdateBegin=s->mVersionUpdateEnd=7; strcpy(s->mScoringInfo.mTrackName,"Spa-Francorchamps");
  s->mScoringInfo.mNumVehicles=2; s->mScoringInfo.mInRealtime=1; s->mScoringInfo.mLapDist=7004.0;
  s->mVehicles[0].mID=7; s->mVehicles[1].mID=42; s->mVehicles[1].mIsPlayer=1; s->mVehicles[1].mTotalLaps=3;
  s->mVehicles[1].mBestLapTime=125.5; s->mVehicles[1].mLastLapTime=126.0; s->mVehicles[1].mLapDist=3502.0;
  snprintf(path,sizeof path,"%s/rf2_tel.bin",dir); dump(path, t, sizeof *t);
  snprintf(path,sizeof path,"%s/rf2_scoring.bin",dir); dump(path, s, sizeof *s);
  /* LMU */
  struct LMUObject *l = calloc(1, sizeof *l);
  l->telemetry.activeVehicles=2; l->telemetry.playerVehicleIdx=1; l->telemetry.playerHasVehicle=1;
  LMUVehicleTelemetry *lv=&l->telemetry.telemInfo[1];
  lv->mID=9; lv->mElapsedTime=50; lv->mLapStartET=20; lv->mGear=-1; lv->mEngineRPM=3000; lv->mEngineMaxRPM=8000;
  lv->mLocalVel.z=-20; lv->mUnfilteredThrottle=0.5; lv->mUnfilteredBrake=0.3; lv->mFuel=10; lv->mFuelCapacity=100;
  strcpy(lv->mVehicleName,"Toyota GR010"); strcpy(lv->mTrackName,"Le Mans");
  l->scoring.scoringInfo.mNumVehicles=2; l->scoring.scoringInfo.mInRealtime=1; l->scoring.scoringInfo.mLapDist=13626;
  l->scoring.vehScoringInfo[0].mID=9; l->scoring.vehScoringInfo[0].mTotalLaps=2; l->scoring.vehScoringInfo[0].mLapDist=500;
  l->scoring.vehScoringInfo[0].mBestLapTime=210.25; l->scoring.vehScoringInfo[0].mLastLapTime=211.0;
  snprintf(path,sizeof path,"%s/lmu.bin",dir); dump(path, l, sizeof *l);
  /* R3E */
  struct r3e_share *r = calloc(1, sizeof *r);
  strcpy((char*)r->track_name,"Nordschleife"); strcpy((char*)r->layout_name,"Tourist"); r->layout_length=20832;
  r->completed_laps=1; r->lap_distance=1000; r->lap_distance_fraction=0.048f; r->lap_time_best_self=420.5f;
  r->lap_time_previous_self=421.0f; r->lap_time_current_self=60.25f; r->car_speed=40; r->engine_rps=628.3185f; r->max_engine_rps=837.758f;
  r->gear=3; r->car_cg_location.x=5; r->car_cg_location.y=6; r->car_cg_location.z=7; r->fuel_left=20; r->fuel_capacity=80;
  r->throttle_raw=0.9f; r->brake_raw=0.0f; r->clutch_raw=0.0f; r->steer_input_raw=0.1f;
  snprintf(path,sizeof path,"%s/r3e.bin",dir); dump(path, r, sizeof *r);
  return 0;
}
