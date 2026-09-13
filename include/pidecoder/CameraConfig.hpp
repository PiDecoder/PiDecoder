#pragma once

#include <string>
#include <vector>

namespace pidecoder {

struct PtzPreset final {
    std::string token;
    std::string name;
};

struct CameraConfig final {
    std::string name;
    std::string grid_url;
    std::string focus_url;
    bool enabled{true};

    bool ptz_enabled{false};
    std::string ptz_xaddr;
    std::string ptz_profile_token;
    std::vector<PtzPreset> ptz_presets;
};

} // namespace pidecoder
