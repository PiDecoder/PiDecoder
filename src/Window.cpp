#include "pidecoder/Window.hpp"

#include <iostream>
#include <stdexcept>
#include <utility>

namespace pidecoder {

Window::Window(
    std::string title,
    const int width,
    const int height,
    const bool start_fullscreen
)
    : fullscreen_(start_fullscreen),
      /*
       * Taille de secours pour un retour en fenêtré (touche F) : la
       * taille demandée ici n'est la "taille fenêtrée" que si on démarre
       * effectivement en fenêtré. Si on démarre directement en plein
       * écran simulé, (width, height) est la résolution de l'écran, pas
       * une taille de fenêtre raisonnable — on garde 1280x720 comme repli
       * dans ce cas.
       */
      windowed_width_(start_fullscreen ? 1280 : width),
      windowed_height_(start_fullscreen ? 720 : height)
{
    SDL_GL_SetAttribute(
        SDL_GL_DOUBLEBUFFER,
        1
    );

    Uint32 window_flags =
        SDL_WINDOW_OPENGL |
        SDL_WINDOW_ALLOW_HIGHDPI |
        SDL_WINDOW_SHOWN;

    int pos_x = SDL_WINDOWPOS_CENTERED;
    int pos_y = SDL_WINDOWPOS_CENTERED;

    if (start_fullscreen) {
        /*
         * Voir Window.hpp : on crée directement la fenêtre sans bordure
         * à la taille finale plutôt que de la redimensionner après
         * coup, ce second redimensionnement s'étant révélé sans effet
         * réel sur cette installation (voir CHANGELOG.md).
         */
        window_flags |= SDL_WINDOW_BORDERLESS;
        pos_x = 0;
        pos_y = 0;
    } else {
        window_flags |= SDL_WINDOW_RESIZABLE;
    }

    window_ = SDL_CreateWindow(
        title.c_str(),
        pos_x,
        pos_y,
        width,
        height,
        window_flags
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

    int actual_width = 0;
    int actual_height = 0;

    SDL_GetWindowSize(
        window_,
        &actual_width,
        &actual_height
    );

    std::cerr
        << "[Window] fenetre creee (start_fullscreen=" << start_fullscreen
        << ") : demandee=" << width << "x" << height
        << " taille fenetre=" << actual_width << "x" << actual_height
        << " taille dessin=" << drawable_width() << "x" << drawable_height()
        << std::endl;
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

    /*
     * Historique (voir CHANGELOG.md) : trois tentatives précédentes en
     * s'appuyant sur SDL_SetWindowFullscreen(..., SDL_WINDOW_FULLSCREEN_DESKTOP)
     * — délai avant l'appel, double rebasculement, puis forcer la taille en
     * plus — sont toutes restées sans effet sur le terrain (photos à
     * l'appui : la fenêtre ne fait jamais réellement la taille de
     * l'écran). Hypothèse la plus probable pour expliquer que même un
     * SDL_SetWindowSize() explicite après coup n'ait rien changé : sous
     * Wayland, une fois la surface dans l'état "fullscreen" du protocole
     * xdg-shell, c'est le compositeur seul qui en contrôle la taille — une
     * demande de resize du client est alors un no-op tant que cet état
     * reste actif. On arrête donc de demander cet état réel : on simule le
     * plein écran nous-mêmes (fenêtre sans bordure, positionnée en (0,0),
     * redimensionnée à la résolution de l'écran) — visuellement
     * indiscernable pour un mur d'images toujours affiché, sans dépendre
     * de cette négociation avec le compositeur.
     *
     * Chaque bascule journalise sa géométrie avant/après (voir plus bas) :
     * si ce correctif ne suffit toujours pas, `journalctl -u
     * pidecoder.service` donnera directement les tailles réelles vues par
     * SDL plutôt que de continuer à deviner à distance.
     */
    if (fullscreen_) {
        const int display_index =
            SDL_GetWindowDisplayIndex(
                window_
            );

        SDL_DisplayMode mode{};

        const bool have_mode =
            display_index >= 0 &&
            SDL_GetCurrentDisplayMode(
                display_index,
                &mode
            ) == 0;

        std::cerr
            << "[Window] passage en plein ecran simule : display_index="
            << display_index
            << " mode="
            << (have_mode ? std::to_string(mode.w) + "x" + std::to_string(mode.h) : "inconnu")
            << std::endl;

        SDL_SetWindowBordered(
            window_,
            SDL_FALSE
        );

        if (have_mode) {
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
        } else {
            /*
             * Repli si la résolution de l'écran n'a pas pu être lue
             * (rare) : au moins retenter la négociation SDL standard
             * plutôt que de laisser la fenêtre à sa taille fenêtrée.
             */
            SDL_SetWindowFullscreen(
                window_,
                SDL_WINDOW_FULLSCREEN_DESKTOP
            );
        }
    } else {
        SDL_SetWindowFullscreen(
            window_,
            0
        );

        SDL_SetWindowBordered(
            window_,
            SDL_TRUE
        );

        SDL_SetWindowPosition(
            window_,
            SDL_WINDOWPOS_CENTERED,
            SDL_WINDOWPOS_CENTERED
        );

        SDL_SetWindowSize(
            window_,
            windowed_width_,
            windowed_height_
        );
    }

    int actual_width = 0;
    int actual_height = 0;

    SDL_GetWindowSize(
        window_,
        &actual_width,
        &actual_height
    );

    std::cerr
        << "[Window] apres toggle_fullscreen (fullscreen=" << fullscreen_
        << ") : taille fenetre=" << actual_width << "x" << actual_height
        << " taille dessin=" << drawable_width() << "x" << drawable_height()
        << std::endl;
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