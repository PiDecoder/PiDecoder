#include "pidecoder/Window.hpp"

#include <stdexcept>
#include <utility>

namespace pidecoder {

Window::Window(
    std::string title,
    const int width,
    const int height
)
{
    SDL_GL_SetAttribute(
        SDL_GL_DOUBLEBUFFER,
        1
    );

    window_ = SDL_CreateWindow(
        title.c_str(),
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        width,
        height,
        SDL_WINDOW_OPENGL |
            SDL_WINDOW_RESIZABLE |
            SDL_WINDOW_ALLOW_HIGHDPI |
            SDL_WINDOW_SHOWN
    );

    if (window_ == nullptr) {
        throw std::runtime_error(
            std::string{"SDL_CreateWindow: "} +
            SDL_GetError()
        );
    }

    gl_context_ = SDL_GL_CreateContext(
        window_
    );

    if (gl_context_ == nullptr) {
        SDL_DestroyWindow(window_);
        window_ = nullptr;

        throw std::runtime_error(
            std::string{"SDL_GL_CreateContext: "} +
            SDL_GetError()
        );
    }

    make_current();

    SDL_GL_SetSwapInterval(0);
}

Window::~Window()
{
    if (gl_context_ != nullptr) {
        SDL_GL_DeleteContext(
            gl_context_
        );
    }

    if (window_ != nullptr) {
        SDL_DestroyWindow(
            window_
        );
    }
}

SDL_Window* Window::native_handle() const noexcept
{
    return window_;
}

int Window::drawable_width() const noexcept
{
    int width = 0;
    int height = 0;

    SDL_GL_GetDrawableSize(
        window_,
        &width,
        &height
    );

    return width;
}

int Window::drawable_height() const noexcept
{
    int width = 0;
    int height = 0;

    SDL_GL_GetDrawableSize(
        window_,
        &width,
        &height
    );

    return height;
}

void Window::toggle_fullscreen()
{
    fullscreen_ = !fullscreen_;

    if (
        SDL_SetWindowFullscreen(
            window_,
            fullscreen_
                ? SDL_WINDOW_FULLSCREEN_DESKTOP
                : 0
        ) != 0
    ) {
        fullscreen_ = !fullscreen_;

        throw std::runtime_error(
            std::string{"SDL_SetWindowFullscreen: "} +
            SDL_GetError()
        );
    }
}

void Window::make_current()
{
    if (
        SDL_GL_MakeCurrent(
            window_,
            gl_context_
        ) != 0
    ) {
        throw std::runtime_error(
            std::string{"SDL_GL_MakeCurrent: "} +
            SDL_GetError()
        );
    }
}

void Window::swap_buffers()
{
    SDL_GL_SwapWindow(
        window_
    );
}

} // namespace pidecoder