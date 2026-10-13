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
void blend(const Matrix&,const Matrix&,float,Matrix&);
Matrix multiply(const Matrix&,const Matrix&);
Matrix inverseRigid(const Matrix&);
class TransformTrack {
    bool initialized_=false;
    Phase stamp_{};
    Matrix previous_{},current_{};
public:
    void reset() { initialized_=false; }
    Matrix sample(const Matrix&,Phase,bool camera=false);
};
}
