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

    /*
     * SDL_WINDOW_FULLSCREEN_DESKTOP est censé masquer les décorations
     * (barre de titre) tout seul — constaté sur le terrain sous labwc :
     * la barre de titre restait affichée malgré un retour de succès de
     * SDL_SetWindowFullscreen() ci-dessus (voir CHANGELOG.md, capture
     * d'écran montrant "PiDecoder v1.2.0" en haut d'une fenêtre pourtant
     * censée être plein écran). On force donc explicitement l'état des
     * bordures en plus, plutôt que de compter uniquement sur la
     * négociation automatique du compositeur.
     */
    SDL_SetWindowBordered(
        window_,
        fullscreen_ ? SDL_FALSE : SDL_TRUE
    );

    if (fullscreen_) {
        /*
         * Retour terrain (photos à l'appui) : même sans barre de titre
         * (correctif ci-dessus), le contenu rendu restait confiné à la
         * taille de fenêtre d'origine (1280x720), dans un coin — le reste
         * de l'écran étant simplement le fond du bureau labwc derrière une
         * fenêtre en réalité jamais redimensionnée. SDL_SetWindowFullscreen
         * ci-dessus a beau renvoyer un succès, il ne semble donc pas
         * redimensionner réellement la fenêtre sous ce compositeur — malgré
         * ce que documente SDL pour SDL_WINDOW_FULLSCREEN_DESKTOP. Plutôt
         * que de continuer à faire confiance à cette négociation, on impose
         * ici explicitement la taille et la position de la fenêtre à
         * celles du mode d'affichage courant. Erreurs ignorées
         * volontairement (SDL_GetWindowDisplayIndex/SDL_GetCurrentDisplayMode
         * peuvent échouer sur un système sans écran détecté correctement) :
         * la géométrie reste alors celle négociée par
         * SDL_SetWindowFullscreen ci-dessus plutôt que de faire planter
         * l'application pour ce seul confort visuel.
         */
        const int display_index =
            SDL_GetWindowDisplayIndex(
                window_
            );

        SDL_DisplayMode mode{};

        if (
            display_index >= 0 &&
            SDL_GetCurrentDisplayMode(
                display_index,
                &mode
            ) == 0
        ) {
            SDL_SetWindowPosition(
                window_,
                0,
                0
            );

            SDL_SetWindowSize(
                window_,
                mode.w,
                mode.h
            );
        }
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