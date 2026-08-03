#pragma once

#include <string>

namespace pidecoder {

struct CameraConfig final {
    std::string name;
    std::string grid_url;
    std::string focus_url;
    bool enabled{true};

    bool ptz_enabled{false};
    std::string ptz_xaddr;
    std::string ptz_profile_token;
};

} // namespace pidecoder
