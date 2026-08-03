#pragma once

#include "pidecoder/Grid.hpp"
#include "pidecoder/Layout.hpp"
#include "pidecoder/Player.hpp"
#include "pidecoder/PtzController.hpp"
#include "pidecoder/Window.hpp"

#include <array>
#include <memory>
#include <optional>
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
        bool show_zoom_indicator,
        bool ptz_available,
        PtzCommand active_ptz_command
    );

    [[nodiscard]] std::optional<PtzCommand>
    ptz_command_at(
        int logical_x,
        int logical_y
    ) const noexcept;

private:
    struct PtzButton final {
        PtzCommand command{PtzCommand::None};
        Rect rectangle{};
    };

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

    void draw_ptz_overlay(
        int canvas_width,
        int canvas_height,
        PtzCommand active_command
    );

    [[nodiscard]] std::array<PtzButton, 7>
    ptz_buttons(
        int canvas_width,
        int canvas_height
    ) const;

    void draw_ptz_icon(
        PtzCommand command,
        const Rect& rectangle,
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
