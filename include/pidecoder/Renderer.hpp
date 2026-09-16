#pragma once

#include "pidecoder/Grid.hpp"
#include "pidecoder/Layout.hpp"
#include "pidecoder/Player.hpp"
#include "pidecoder/PtzController.hpp"
#include "pidecoder/Window.hpp"

#include <array>
#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace pidecoder {

class Renderer final {
public:
    struct PtzPresetHit final {
        bool selector{false};
        std::size_t index{0};
    };

    explicit Renderer(Window& window);

    void render(
        const std::vector<
            std::unique_ptr<Player>
        >& players,
        const LayoutConfig& layout,
        const std::optional<std::string>&
            startup_info_text = std::nullopt
    );

    void render_focus(
        Player& player,
        double zoom,
        double center_x,
        double center_y,
        bool show_zoom_indicator,
        bool ptz_available,
        bool show_ptz_overlay,
        PtzCommand active_ptz_command,
        const std::vector<PtzPreset>& presets,
        bool preset_menu_open,
        bool show_audio_indicator,
        bool audio_muted,
        bool audio_available,
        const std::optional<std::string>&
            startup_info_text = std::nullopt
    );

    [[nodiscard]] std::optional<PtzCommand>
    ptz_command_at(
        int logical_x,
        int logical_y
    ) const noexcept;

    [[nodiscard]] bool audio_button_hit_at(
        int logical_x,
        int logical_y,
        bool ptz_available
    ) const noexcept;

    [[nodiscard]] std::optional<PtzPresetHit>
    ptz_preset_hit_at(
        int logical_x,
        int logical_y,
        std::size_t preset_count,
        bool menu_open
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

    void draw_audio_indicator(
        bool muted,
        bool available,
        bool ptz_available,
        int canvas_width,
        int canvas_height
    );

    /*
     * Zone cliquable du bouton son (bas-droite de la vue Focus, décalé
     * à gauche du pavé PTZ quand celui-ci est affiché au même endroit,
     * pour ne jamais le recouvrir). Partagée entre le dessin
     * (draw_audio_indicator) et le test de clic (audio_button_hit_at).
     */
    [[nodiscard]] Rect audio_button(
        int canvas_width,
        int canvas_height,
        bool ptz_available
    ) const noexcept;

    void draw_ptz_overlay(
        int canvas_width,
        int canvas_height,
        PtzCommand active_command,
        const std::vector<PtzPreset>& presets,
        bool preset_menu_open
    );

    [[nodiscard]] std::array<PtzButton, 7>
    ptz_buttons(
        int canvas_width,
        int canvas_height
    ) const;

    [[nodiscard]] Rect ptz_preset_selector(
        int canvas_width,
        int canvas_height
    ) const;

    [[nodiscard]] std::vector<Rect>
    ptz_preset_items(
        int canvas_width,
        int canvas_height,
        std::size_t preset_count
    ) const;

    void draw_ptz_icon(
        PtzCommand command,
        const Rect& rectangle,
        int canvas_height
    );

    void draw_text(
        const std::string& text,
        const Rect& rectangle,
        int canvas_height,
        int right_reserve = 0
    );

    /*
     * Petit bandeau semi-transparent en bas à droite de l'écran (mosaïque
     * ou vue Focus indifféremment) montrant l'adresse IP/nom d'hôte/port
     * Web du Pi — affiché quelques secondes au démarrage du player et
     * rappelable au clavier (voir Application::show_startup_info_overlay).
     */
    void draw_startup_info_overlay(
        const std::string& text,
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
