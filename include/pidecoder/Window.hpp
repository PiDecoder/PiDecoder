#pragma once

#include <SDL2/SDL.h>

#include <string>

namespace pidecoder {

class Window final {
public:
    /*
     * start_fullscreen : demande la création directe d'une fenêtre sans
     * bordure, positionnée en (0,0) et déjà à la taille demandée (width,
     * height), sans jamais passer par un redimensionnement après coup.
     *
     * Retour terrain (voir CHANGELOG.md) : sur l'image Lite minimale
     * (labwc sans configuration, contrairement à Raspberry Pi OS Desktop
     * où ça fonctionne), aucun redimensionnement demandé après la
     * création — ni un vrai SDL_SetWindowFullscreen(), ni un
     * SDL_SetWindowSize() manuel, à aucun moment, y compris bien après le
     * démarrage — ne change réellement la surface affichée : SDL rapporte
     * la nouvelle taille comme acquise (SDL_GetWindowSize /
     * SDL_GL_GetDrawableSize la confirment), mais le rendu réel reste
     * confiné à la taille d'origine. Le seul contournement fiable
     * constaté est de ne jamais redimensionner : créer la fenêtre
     * directement à la bonne taille. C'est ce que start_fullscreen fait
     * pour le démarrage en plein écran ; toggle_fullscreen() reste
     * disponible pour un usage interactif (touche F) mais son
     * redimensionnement après coup n'est pas fiable sur ce type
     * d'installation.
     */
    Window(
        std::string title,
        int width,
        int height,
        bool start_fullscreen = false
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