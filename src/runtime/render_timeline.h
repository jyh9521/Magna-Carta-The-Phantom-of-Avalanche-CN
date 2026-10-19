#pragma once
#include <cstdint>

namespace motion {
struct Matrix { float v[16]; };
struct Phase {
    uint64_t tick=0, generation=0;
    float alpha=1;
    bool valid=false;
};
// Engine-provided consumed updates and remainder, never a second wall clock.
class Timeline {
    uintptr_t owner_=0;
    uint32_t timestamp_=0;
    Phase phase_{};
public:
    void reset();
    void observe(uintptr_t owner,unsigned interval,unsigned remainder,
                 unsigned consumed,uint32_t timestamp,bool active);
    Phase phase() const { return phase_; }
};
bool rigid(const Matrix&);
bool poseInterpolatable(const Matrix&);
void blend(const Matrix&,const Matrix&,float,Matrix&);
Matrix multiply(const Matrix&,const Matrix&);
Matrix inverseRigid(const Matrix&);
struct TransformObservation {
 bool reset=false,initial=false,phaseReset=false,cut=false,unstable=false,unsupported=false,advanced=false;
 float translationStep=0;
};
class TransformTrack {
    bool initialized_=false;
    Phase stamp_{};
    TransformObservation observation_{};
    Matrix previous_{},current_{};
    Matrix sampleImpl(const Matrix&,Phase,bool camera,bool affine);
public:
    void reset() { initialized_=false; observation_={}; }
    const TransformObservation& observation() const {return observation_;}
    Matrix sample(const Matrix&,Phase,bool camera=false);
    // Models may carry scale/reflection; camera admission remains rigid-only.
    Matrix sampleAffine(const Matrix&,Phase);
};
}
