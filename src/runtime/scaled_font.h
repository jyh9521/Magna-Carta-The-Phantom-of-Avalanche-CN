#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

// Offline prototype only. The active game font/texture hooks do not reference this class.
class ScaledGlyphCache {
public:
    bool load(const char* path, std::string& error);
    bool draw(unsigned short pair, int x, int y, int& logicalAdvance, unsigned color,
              unsigned* pixels, size_t count, int physicalPitch) const;
    unsigned height() const { return logicalHeight; }
    unsigned scale() const { return rasterScale; }
    const std::vector<unsigned short>& ids() const { return pairs; }
private:
    unsigned logicalHeight=0, rasterScale=0;
    std::vector<unsigned short> pairs;
    std::vector<unsigned char> coverage;
};
