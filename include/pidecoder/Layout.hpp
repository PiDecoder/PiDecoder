#pragma once

#include <cstddef>
#include <string>
#include <vector>

namespace pidecoder {

struct LayoutPlacement final {
    std::size_t camera{0};
    int x{0};
    int y{0};
    int width{1};
    int height{1};
};

struct LayoutConfig final {
    int columns{3};
    int rows{3};
    bool fullscreen_on_start{false};
    std::vector<std::size_t> camera_order;
    std::vector<LayoutPlacement> placements;
};

class LayoutStore final {
public:
    static LayoutConfig load(
        const std::string& path,
        std::size_t camera_count
    );

    static void save(
        const std::string& path,
        const LayoutConfig& layout
    );

    static void normalize(
        LayoutConfig& layout,
        std::size_t camera_count
    );
};

} // namespace pidecoder
