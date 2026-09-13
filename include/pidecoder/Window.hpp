#pragma once

#include <SDL2/SDL.h>

#include <string>

namespace pidecoder {

class Window final {
public:
    Window(
        std::string title,
        int width,
        int height
    );

    ~Window();

    Window(const Window&) = delete;
    Window& operator=(const Window&) = delete;
    Window(Window&&) = delete;
    Window& operator=(Window&&) = delete;

    [[nodiscard]] SDL_Window* native_handle() const noexcept;

    [[nodiscard]] int drawable_width() const noexcept;
    [[nodiscard]] int drawable_height() const noexcept;

    void toggle_fullscreen();
    void make_current();
    void swap_buffers();

private:
    SDL_Window* window_{nullptr};
    SDL_GLContext gl_context_{nullptr};

    bool fullscreen_{false};
};

} // namespace pidecoder