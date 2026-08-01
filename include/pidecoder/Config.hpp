#pragma once
#include "pidecoder/CameraConfig.hpp"
#include <string>
#include <vector>
namespace pidecoder {
class Config final {
public:
    static std::vector<CameraConfig> load(const std::string& path);
};
}
