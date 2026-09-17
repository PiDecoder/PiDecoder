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

    /*
     * Taille demandée à la construction (fenêtré) — utilisée par
     * toggle_fullscreen() pour restaurer une taille sensée en sortant du
     * plein écran simulé (voir ce fichier, .cpp) plutôt que de laisser la
     * fenêtre à la taille de l'écran une fois "démaximisée".
     */
    int windowed_width_{0};
    int windowed_height_{0};
};

} // namespace pidecoder