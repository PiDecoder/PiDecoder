#pragma once
#include <string>
namespace pidecoder {
struct CameraConfig final {
    std::string name;
    std::string grid_url;
    std::string focus_url;
    bool enabled{true};
};
}
