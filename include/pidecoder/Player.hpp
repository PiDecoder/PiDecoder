#pragma once
#include "pidecoder/Types.hpp"
#include <mpv/client.h>
#include <mpv/render_gl.h>
#include <SDL2/SDL.h>
#include <SDL2/SDL_opengl.h>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <string>

namespace pidecoder {

enum class PlayerRole {
    Grid,
    Focus
};

enum class PlayerState {
    Connecting,
    Online,
    Offline,
    Error
};

class Player final {
public:
    Player(
        std::string url,
        Uint32 mpv_event_type,
        Uint32 render_event_type,
        PlayerRole role
    );
    ~Player();

    Player(const Player&) = delete;
    Player& operator=(const Player&) = delete;
    Player(Player&&) = delete;
    Player& operator=(Player&&) = delete;

    void initialize();
    void load();
    [[nodiscard]] bool tick();
    void process_events(bool& application_running);
    [[nodiscard]] bool update_render_state();

    void render(
        const Rect& target,
        int canvas_width,
        int canvas_height
    );

    void render_inspected(
        const Rect& target,
        int canvas_width,
        int canvas_height,
        double zoom,
        double center_x,
        double center_y
    );
    void detach_callbacks() noexcept;

    [[nodiscard]] const std::string& url() const noexcept;
    [[nodiscard]] bool loaded() const noexcept;
    [[nodiscard]] PlayerState state() const noexcept;
    [[nodiscard]] bool has_error() const noexcept;
    [[nodiscard]] bool has_rendered_frame() const noexcept;
    [[nodiscard]] bool frame_ready() const noexcept;
    [[nodiscard]] bool error_marker_visible() const noexcept;

private:
    static void* get_proc_address(void* context, const char* name);
    static void on_mpv_event(void* context);
    static void on_render_update(void* context);

    void configure();
    void schedule_reconnect();
    void reconnect_now();
    void restart_mpv_engine();
    void destroy_mpv_engine() noexcept;
    void ensure_render_target(int width, int height);

    void render_pending_frame(
        int width,
        int height
    );

    void blit_last_frame(
        const Rect& target,
        int canvas_height
    );

    void blit_last_frame_inspected(
        const Rect& target,
        int canvas_height,
        double zoom,
        double center_x,
        double center_y
    );
    void destroy_render_target() noexcept;
    void destroy() noexcept;
    void check(int status, const std::string& operation) const;

    std::string url_;
    PlayerRole role_{PlayerRole::Grid};
    Uint32 mpv_event_type_;
    Uint32 render_event_type_;

    mpv_handle* mpv_{nullptr};
    mpv_render_context* render_context_{nullptr};

    GLuint framebuffer_{0};
    GLuint texture_{0};

    int render_width_{0};
    int render_height_{0};

    bool initialized_{false};
    bool loaded_{false};
    bool callbacks_attached_{false};
    bool has_rendered_frame_{false};
    bool frame_pending_{false};
    bool error_marker_visible_{false};

    PlayerState state_{PlayerState::Connecting};

    std::chrono::steady_clock::time_point reconnect_at_{};
    std::chrono::steady_clock::time_point load_started_at_{};
    std::chrono::steady_clock::time_point last_frame_at_{};
    std::chrono::seconds reconnect_delay_{2};
    static constexpr std::chrono::seconds max_reconnect_delay_{30};
    static constexpr std::chrono::seconds connect_timeout_{8};
    static constexpr std::chrono::seconds frame_stall_timeout_{5};

    std::atomic_bool mpv_event_pending_{false};
    std::atomic_bool render_event_pending_{false};
};

} // namespace pidecoder
