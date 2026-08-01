#pragma once

#include "pidecoder/Grid.hpp"
#include "pidecoder/Layout.hpp"
#include "pidecoder/Player.hpp"
#include "pidecoder/Window.hpp"

#include <memory>
#include <vector>

namespace pidecoder {

class Renderer final {
public:
    explicit Renderer(Window& window);

    void render(
        const std::vector<
            std::unique_ptr<Player>
        >& players,
        const LayoutConfig& layout
    );

    void render_focus(
        Player& player,
        double zoom,
        double center_x,
        double center_y,
        bool show_zoom_indicator
    );

private:
    void clear(
        int width,
        int height
    );

    void draw_error_marker(
        const Rect& target,
        int canvas_height
    );

    void draw_zoom_indicator(
        int percent,
        int canvas_width,
        int canvas_height
    );

    void draw_digit(
        int digit,
        int x,
        int y,
        int scale,
        int canvas_height
    );

    void fill_ui_rect(
        int x,
        int y,
        int width,
        int height,
        int canvas_height,
        float red,
        float green,
        float blue,
        float alpha
    );

    Window& window_;
    Grid grid_;
};

} // namespace pidecoder
