#pragma once

#include "pidecoder/CameraConfig.hpp"
#include "pidecoder/Grid.hpp"
#include "pidecoder/Layout.hpp"
#include "pidecoder/Player.hpp"
#include "pidecoder/PtzController.hpp"
#include "pidecoder/Renderer.hpp"
#include "pidecoder/Window.hpp"

#include <SDL2/SDL.h>

#include <chrono>
#include <cstddef>
#include <memory>
#include <optional>
#include <vector>

namespace pidecoder {

class Application final {
public:
    Application(
        std::vector<CameraConfig> cameras,
        LayoutConfig layout
    );

    Application(const Application&) = delete;
    Application& operator=(const Application&) = delete;

    int run();

private:
    void initialize_sdl();
    void initialize_players();

    void process_sdl_event(
        const SDL_Event& event
    );

    void process_player_events();
    void update_player_render_states();

    void open_focus(
        std::size_t camera_index
    );

    void close_focus();
    void render();

    void reset_inspection() noexcept;

    void begin_zoom(
        double requested_zoom,
        int mouse_x,
        int mouse_y
    );

    void update_inspection_animation();

    void begin_pan(
        int mouse_x,
        int mouse_y
    ) noexcept;

    void update_pan(
        int mouse_x,
        int mouse_y
    ) noexcept;

    void end_pan() noexcept;

    [[nodiscard]] bool focused_camera_has_ptz() const noexcept;

    [[nodiscard]] const CameraConfig*
    focused_camera() const noexcept;

    void begin_ptz_command(
        PtzCommand command
    );

    void stop_ptz_command(
        bool force = false
    ) noexcept;

    void show_ptz_overlay() noexcept;
    void update_ptz_overlay_visibility() noexcept;

    void clamp_inspection_center() noexcept;

    [[nodiscard]] bool zoom_indicator_visible() const noexcept;

    [[nodiscard]] std::optional<std::size_t>
    camera_index_at(
        int mouse_x,
        int mouse_y
    ) const;

    std::vector<CameraConfig> cameras_;
    LayoutConfig layout_;

    Uint32 mpv_event_type_{0};
    Uint32 render_event_type_{0};

    std::unique_ptr<Window> window_;
    std::unique_ptr<Renderer> renderer_;
    PtzController ptz_controller_;

    std::vector<std::unique_ptr<Player>>
        players_;

    std::unique_ptr<Player>
        focus_player_;

    std::optional<std::size_t>
        focused_camera_index_;

    PtzCommand active_ptz_command_{PtzCommand::None};
    bool ptz_pointer_active_{false};
    bool ptz_overlay_visible_{false};

    std::chrono::steady_clock::time_point
        ptz_overlay_until_{};

    Grid grid_;

    bool running_{true};
    bool redraw_requested_{true};

    double inspection_zoom_{1.0};
    double inspection_target_zoom_{1.0};
    double inspection_center_x_{0.5};
    double inspection_center_y_{0.5};

    double animation_start_zoom_{1.0};
    double animation_start_center_x_{0.5};
    double animation_start_center_y_{0.5};
    double animation_target_center_x_{0.5};
    double animation_target_center_y_{0.5};

    std::chrono::steady_clock::time_point
        inspection_animation_started_at_{};

    std::chrono::steady_clock::time_point
        zoom_indicator_until_{};

    bool inspection_animation_active_{false};
    bool inspection_dragging_{false};

    int inspection_last_mouse_x_{0};
    int inspection_last_mouse_y_{0};

    static constexpr double minimum_zoom_{1.0};
    static constexpr double maximum_zoom_{5.0};
    static constexpr double zoom_step_{1.10};

    static constexpr std::chrono::milliseconds
        zoom_animation_duration_{150};

    static constexpr std::chrono::seconds
        zoom_indicator_duration_{2};

    static constexpr std::chrono::seconds
        ptz_overlay_timeout_{5};
};

} // namespace pidecoder
