#pragma once

#include "pidecoder/Layout.hpp"
#include "pidecoder/Types.hpp"

#include <cstddef>
#include <vector>

namespace pidecoder {

class Grid final {
public:
    [[nodiscard]] std::vector<Rect> calculate(
        std::size_t count,
        int width,
        int height
    ) const;

    [[nodiscard]] std::vector<Rect> calculate(
        std::size_t count,
        int width,
        int height,
        const LayoutConfig& layout
    ) const;
};

} // namespace pidecoder
