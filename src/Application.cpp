#include "pidecoder/Application.hpp"
#include "pidecoder/Version.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>

namespace {

int remove_events_for_player(
    void* userdata,
    SDL_Event* event
)
{
    if (
        event != nullptr &&
        event->user.data1 == userdata
    ) {
        return 0;
    }

    return 1;
}

} // namespace

namespace pidecoder {

Application::Application(
    std::vector<CameraConfig> cameras,
    LayoutConfig layout
)
    : cameras_(std::move(cameras)),
      layout_(std::move(layout))
{
    if (cameras_.empty()) {
        throw std::invalid_argument(
            "Au moins une caméra est nécessaire"
        );
    }
}

int Application::run()
{
    try {
        initialize_sdl();

        const std::string window_title =
            std::string{"PiDecoder v"} +
            PIDECODER_VERSION_STRING;

        window_ =
            std::make_unique<Window>(
                window_title,
                1280,
                720
            );

        renderer_ =
            std::make_unique<Renderer>(
                *window_
            );

        if (
            layout_.fullscreen_on_start
        ) {
            window_->toggle_fullscreen();
        }

        initialize_players();

        std::cout
            << "PiDecoder v"
            << PIDECODER_VERSION_STRING
            << " lancé avec "
            << players_.size()
            << " caméra(s)."
            << std::endl;

        while (running_) {
            SDL_Event event{};

            if (
                SDL_WaitEventTimeout(
                    &event,
                    10
                ) != 0
            ) {
                process_sdl_event(event);

                while (
                    running_ &&
                    SDL_PollEvent(&event) != 0
                ) {
                    process_sdl_event(event);
                }
            }

            process_player_events();
            update_player_render_states();

            for (auto& player : players_) {
                if (player->tick()) {
                    redraw_requested_ = true;
                }
            }

            if (
                focus_player_ != nullptr &&
                focus_player_->tick()
            ) {
                redraw_requested_ = true;
            }

            update_inspection_animation();
            update_ptz_overlay_visibility();

            if (redraw_requested_) {
                render();
                redraw_requested_ = false;
            }
        }

        stop_ptz_command();
        focus_player_.reset();
        players_.clear();
        renderer_.reset();
        window_.reset();

        SDL_Quit();

        return 0;

    } catch (const std::exception& exception) {
        std::cerr
            << "Erreur PiDecoder : "
            << exception.what()
            << std::endl;

        stop_ptz_command();
        focus_player_.reset();
        players_.clear();
        renderer_.reset();
        window_.reset();

        SDL_Quit();

        return 1;
    }
}

void Application::initialize_sdl()
{
    SDL_SetHint(
        SDL_HINT_NO_SIGNAL_HANDLERS,
        "1"
    );

    if (
        SDL_Init(
            SDL_INIT_VIDEO |
            SDL_INIT_EVENTS
        ) != 0
    ) {
        throw std::runtime_error(
            std::string{"SDL_Init: "} +
            SDL_GetError()
        );
    }

    mpv_event_type_ =
        SDL_RegisterEvents(1);

    render_event_type_ =
        SDL_RegisterEvents(1);

    if (
        mpv_event_type_ ==
            static_cast<Uint32>(-1) ||
        render_event_type_ ==
            static_cast<Uint32>(-1)
    ) {
        throw std::runtime_error(
            "Impossible d'enregistrer les événements SDL"
        );
    }
}

void Application::initialize_players()
{
    players_.reserve(
        layout_.camera_order.size()
    );

    for (
        const std::size_t camera_index :
        layout_.camera_order
    ) {
        if (
            camera_index >=
            cameras_.size()
        ) {
            continue;
        }

        auto player =
            std::make_unique<Player>(
                cameras_[camera_index].grid_url,
                mpv_event_type_,
                render_event_type_,
                PlayerRole::Grid
            );

        player->initialize();
        player->load();

        players_.push_back(
            std::move(player)
        );

        std::cout
            << "Player "
            << players_.size()
            << " initialisé : "
            << cameras_[camera_index].name
            << std::endl;
    }
}

void Application::process_sdl_event(
    const SDL_Event& event
)
{
    if (event.type == SDL_QUIT) {
        stop_ptz_command();
        running_ = false;
        return;
    }

    if (
        event.type == SDL_MOUSEMOTION &&
        focus_player_ != nullptr &&
        focused_camera_has_ptz()
    ) {
        show_ptz_overlay();
    }

    if (event.type == SDL_KEYDOWN) {
        if (
            event.key.keysym.sym ==
            SDLK_ESCAPE
        ) {
            if (focus_player_ != nullptr) {
                close_focus();
            }

            return;
        }

        if (
            event.key.keysym.sym ==
            SDLK_f
        ) {
            window_->toggle_fullscreen();
            redraw_requested_ = true;
            return;
        }
    }

    if (
        event.type ==
            SDL_MOUSEWHEEL &&
        focus_player_ != nullptr
    ) {
        int mouse_x = 0;
        int mouse_y = 0;

        SDL_GetMouseState(
            &mouse_x,
            &mouse_y
        );

        double requested_zoom =
            inspection_target_zoom_;

        if (event.wheel.y > 0) {
            for (
                int step = 0;
                step < event.wheel.y;
                ++step
            ) {
                requested_zoom *=
                    zoom_step_;
            }
        } else if (
            event.wheel.y < 0
        ) {
            for (
                int step = 0;
                step < -event.wheel.y;
                ++step
            ) {
                requested_zoom /=
                    zoom_step_;
            }
        }

        begin_zoom(
            requested_zoom,
            mouse_x,
            mouse_y
        );

        return;
    }

    if (
        event.type ==
            SDL_MOUSEBUTTONDOWN &&
        focus_player_ != nullptr &&
        event.button.button ==
            SDL_BUTTON_MIDDLE
    ) {
        reset_inspection();

        zoom_indicator_until_ =
            std::chrono::steady_clock::now() +
            zoom_indicator_duration_;

        redraw_requested_ = true;
        return;
    }

    if (
        event.type ==
            SDL_MOUSEBUTTONDOWN &&
        focus_player_ != nullptr &&
        event.button.button ==
            SDL_BUTTON_LEFT &&
        focused_camera_has_ptz() &&
        ptz_overlay_visible_
    ) {
        const CameraConfig* camera =
            focused_camera();

        if (
            camera != nullptr &&
            !camera->ptz_presets.empty()
        ) {
            const auto preset_hit =
                renderer_->ptz_preset_hit_at(
                    event.button.x,
                    event.button.y,
                    camera->ptz_presets.size(),
                    ptz_preset_menu_open_
                );

            if (preset_hit.has_value()) {
                if (preset_hit->selector) {
                    ptz_preset_menu_open_ =
                        !ptz_preset_menu_open_;
                    show_ptz_overlay();
                } else {
                    call_ptz_preset(
                        preset_hit->index
                    );
                }

                return;
            }
        }

        if (ptz_preset_menu_open_) {
            ptz_preset_menu_open_ = false;
            redraw_requested_ = true;
        }

        const auto ptz_command =
            renderer_->ptz_command_at(
                event.button.x,
                event.button.y
            );

        if (ptz_command.has_value()) {
            if (
                *ptz_command ==
                PtzCommand::Stop
            ) {
                stop_ptz_command(true);
            } else {
                begin_ptz_command(
                    *ptz_command
                );
            }

            return;
        }
    }

    if (
        event.type ==
            SDL_MOUSEBUTTONDOWN &&
        focus_player_ != nullptr &&
        event.button.button ==
            SDL_BUTTON_LEFT &&
        event.button.clicks == 1
    ) {
        begin_pan(
            event.button.x,
            event.button.y
        );

        return;
    }

    if (
        event.type ==
            SDL_MOUSEBUTTONUP &&
        event.button.button ==
            SDL_BUTTON_LEFT
    ) {
        if (ptz_pointer_active_) {
            stop_ptz_command();
            return;
        }

        end_pan();
        return;
    }

    if (
        event.type ==
            SDL_MOUSEMOTION &&
        ptz_pointer_active_ &&
        focus_player_ != nullptr
    ) {
        const auto command =
            renderer_->ptz_command_at(
                event.motion.x,
                event.motion.y
            );

        if (
            !command.has_value() ||
            *command != active_ptz_command_
        ) {
            stop_ptz_command();
        }

        return;
    }

    if (
        event.type ==
            SDL_MOUSEMOTION &&
        inspection_dragging_ &&
        focus_player_ != nullptr
    ) {
        update_pan(
            event.motion.x,
            event.motion.y
        );

        return;
    }

    if (
        event.type ==
            SDL_MOUSEBUTTONDOWN &&
        event.button.button ==
            SDL_BUTTON_LEFT &&
        event.button.clicks >= 2
    ) {
        if (focus_player_ != nullptr) {
            close_focus();
            return;
        }

        const auto camera_index =
            camera_index_at(
                event.button.x,
                event.button.y
            );

        if (camera_index.has_value()) {
            open_focus(*camera_index);
        }

        return;
    }

    if (event.type == SDL_WINDOWEVENT) {
        if (
            event.window.event ==
                SDL_WINDOWEVENT_FOCUS_LOST ||
            event.window.event ==
                SDL_WINDOWEVENT_LEAVE
        ) {
            stop_ptz_command();
        }

        if (
            event.window.event ==
                SDL_WINDOWEVENT_EXPOSED ||
            event.window.event ==
                SDL_WINDOWEVENT_SIZE_CHANGED ||
            event.window.event ==
                SDL_WINDOWEVENT_RESIZED
        ) {
            redraw_requested_ = true;
            return;
        }
    }

    if (event.type == mpv_event_type_) {
        auto* player =
            static_cast<Player*>(
                event.user.data1
            );

        if (player != nullptr) {
            player->process_events(running_);
        }

        redraw_requested_ = true;
        return;
    }

    if (event.type == render_event_type_) {
        auto* player =
            static_cast<Player*>(
                event.user.data1
            );

        if (
            player != nullptr &&
            player->update_render_state()
        ) {
            redraw_requested_ = true;
        }
    }
}

void Application::process_player_events()
{
    for (auto& player : players_) {
        player->process_events(running_);
    }

    if (focus_player_ != nullptr) {
        focus_player_->process_events(running_);
    }
}

void Application::update_player_render_states()
{
    for (auto& player : players_) {
        if (player->update_render_state()) {
            redraw_requested_ = true;
        }
    }

    if (
        focus_player_ != nullptr &&
        focus_player_->update_render_state()
    ) {
        redraw_requested_ = true;
    }
}

void Application::open_focus(
    const std::size_t camera_index
)
{
    if (camera_index >= cameras_.size()) {
        return;
    }

    if (
        camera_index >=
        layout_.camera_order.size()
    ) {
        return;
    }

    const std::size_t source_camera_index =
        layout_.camera_order[
            camera_index
        ];

    if (
        source_camera_index >=
        cameras_.size()
    ) {
        return;
    }

    const CameraConfig& camera =
        cameras_[source_camera_index];

    auto focus_player =
        std::make_unique<Player>(
            camera.focus_url,
            mpv_event_type_,
            render_event_type_,
            PlayerRole::Focus
        );

    focus_player->initialize();
    focus_player->load();

    focus_player_ =
        std::move(focus_player);

    reset_inspection();

    focused_camera_index_ =
        source_camera_index;

    ptz_preset_menu_open_ = false;

    if (camera.ptz_enabled) {
        show_ptz_overlay();
    } else {
        ptz_overlay_visible_ = false;
    }

    redraw_requested_ = true;

    std::cout
        << "Ouverture focus : "
        << camera.name
        << std::endl;
}

void Application::close_focus()
{
    if (focus_player_ == nullptr) {
        return;
    }

    stop_ptz_command();

    Player* closing_player =
        focus_player_.get();

    closing_player->detach_callbacks();

    SDL_FilterEvents(
        remove_events_for_player,
        closing_player
    );

    focus_player_.reset();
    focused_camera_index_.reset();
    ptz_overlay_visible_ = false;
    ptz_preset_menu_open_ = false;
    ptz_overlay_until_ = {};
    reset_inspection();
    redraw_requested_ = true;
}

void Application::reset_inspection() noexcept
{
    inspection_zoom_ =
        minimum_zoom_;

    inspection_target_zoom_ =
        minimum_zoom_;

    inspection_center_x_ =
        0.5;

    inspection_center_y_ =
        0.5;

    animation_start_zoom_ =
        minimum_zoom_;

    animation_start_center_x_ =
        0.5;

    animation_start_center_y_ =
        0.5;

    animation_target_center_x_ =
        0.5;

    animation_target_center_y_ =
        0.5;

    inspection_animation_active_ =
        false;

    inspection_dragging_ =
        false;
}

void Application::clamp_inspection_center() noexcept
{
    const double visible_width =
        1.0 /
        inspection_zoom_;

    const double visible_height =
        1.0 /
        inspection_zoom_;

    inspection_center_x_ =
        std::clamp(
            inspection_center_x_,
            visible_width / 2.0,
            1.0 -
                visible_width / 2.0
        );

    inspection_center_y_ =
        std::clamp(
            inspection_center_y_,
            visible_height / 2.0,
            1.0 -
                visible_height / 2.0
        );
}

void Application::begin_zoom(
    const double requested_zoom,
    const int mouse_x,
    const int mouse_y
)
{
    if (
        focus_player_ == nullptr ||
        window_ == nullptr
    ) {
        return;
    }

    int logical_width = 0;
    int logical_height = 0;

    SDL_GetWindowSize(
        window_->native_handle(),
        &logical_width,
        &logical_height
    );

    if (
        logical_width <= 0 ||
        logical_height <= 0
    ) {
        return;
    }

    const double old_zoom =
        inspection_zoom_;

    const double new_zoom =
        std::clamp(
            requested_zoom,
            minimum_zoom_,
            maximum_zoom_
        );

    const double mouse_normalized_x =
        std::clamp(
            static_cast<double>(
                mouse_x
            ) /
            static_cast<double>(
                logical_width
            ),
            0.0,
            1.0
        );

    const double mouse_normalized_y =
        std::clamp(
            static_cast<double>(
                mouse_y
            ) /
            static_cast<double>(
                logical_height
            ),
            0.0,
            1.0
        );

    const double source_under_mouse_x =
        inspection_center_x_ +
        (
            mouse_normalized_x -
            0.5
        ) /
        old_zoom;

    const double source_under_mouse_y =
        inspection_center_y_ +
        (
            mouse_normalized_y -
            0.5
        ) /
        old_zoom;

    double target_center_x =
        source_under_mouse_x -
        (
            mouse_normalized_x -
            0.5
        ) /
        new_zoom;

    double target_center_y =
        source_under_mouse_y -
        (
            mouse_normalized_y -
            0.5
        ) /
        new_zoom;

    const double visible_width =
        1.0 /
        new_zoom;

    const double visible_height =
        1.0 /
        new_zoom;

    target_center_x =
        std::clamp(
            target_center_x,
            visible_width / 2.0,
            1.0 -
                visible_width / 2.0
        );

    target_center_y =
        std::clamp(
            target_center_y,
            visible_height / 2.0,
            1.0 -
                visible_height / 2.0
        );

    animation_start_zoom_ =
        inspection_zoom_;

    animation_start_center_x_ =
        inspection_center_x_;

    animation_start_center_y_ =
        inspection_center_y_;

    inspection_target_zoom_ =
        new_zoom;

    animation_target_center_x_ =
        target_center_x;

    animation_target_center_y_ =
        target_center_y;

    inspection_animation_started_at_ =
        std::chrono::steady_clock::now();

    inspection_animation_active_ =
        true;

    zoom_indicator_until_ =
        inspection_animation_started_at_ +
        zoom_indicator_duration_;

    redraw_requested_ =
        true;
}

void Application::update_inspection_animation()
{
    if (
        focus_player_ == nullptr
    ) {
        return;
    }

    const auto now =
        std::chrono::steady_clock::now();

    if (
        inspection_animation_active_
    ) {
        const double progress =
            std::clamp(
                std::chrono::duration<double>(
                    now -
                    inspection_animation_started_at_
                ).count() /
                std::chrono::duration<double>(
                    zoom_animation_duration_
                ).count(),
                0.0,
                1.0
            );

        /*
         * Smoothstep : départ et arrivée sans cassure visuelle.
         */
        const double eased =
            progress *
            progress *
            (
                3.0 -
                2.0 *
                progress
            );

        inspection_zoom_ =
            animation_start_zoom_ +
            (
                inspection_target_zoom_ -
                animation_start_zoom_
            ) *
            eased;

        inspection_center_x_ =
            animation_start_center_x_ +
            (
                animation_target_center_x_ -
                animation_start_center_x_
            ) *
            eased;

        inspection_center_y_ =
            animation_start_center_y_ +
            (
                animation_target_center_y_ -
                animation_start_center_y_
            ) *
            eased;

        clamp_inspection_center();

        redraw_requested_ =
            true;

        if (progress >= 1.0) {
            inspection_zoom_ =
                inspection_target_zoom_;

            inspection_center_x_ =
                animation_target_center_x_;

            inspection_center_y_ =
                animation_target_center_y_;

            clamp_inspection_center();

            inspection_animation_active_ =
                false;
        }
    }

    if (
        zoom_indicator_until_
            .time_since_epoch()
            .count() != 0 &&
        now <
            zoom_indicator_until_
    ) {
        redraw_requested_ =
            true;
    }
}

void Application::begin_pan(
    const int mouse_x,
    const int mouse_y
) noexcept
{
    if (
        inspection_zoom_ <=
        minimum_zoom_ +
        0.001
    ) {
        return;
    }

    inspection_animation_active_ =
        false;

    inspection_target_zoom_ =
        inspection_zoom_;

    inspection_dragging_ =
        true;

    inspection_last_mouse_x_ =
        mouse_x;

    inspection_last_mouse_y_ =
        mouse_y;
}

void Application::update_pan(
    const int mouse_x,
    const int mouse_y
) noexcept
{
    if (
        !inspection_dragging_ ||
        window_ == nullptr ||
        inspection_zoom_ <=
            minimum_zoom_ +
            0.001
    ) {
        return;
    }

    int logical_width = 0;
    int logical_height = 0;

    SDL_GetWindowSize(
        window_->native_handle(),
        &logical_width,
        &logical_height
    );

    if (
        logical_width <= 0 ||
        logical_height <= 0
    ) {
        return;
    }

    const int delta_x =
        mouse_x -
        inspection_last_mouse_x_;

    const int delta_y =
        mouse_y -
        inspection_last_mouse_y_;

    inspection_last_mouse_x_ =
        mouse_x;

    inspection_last_mouse_y_ =
        mouse_y;

    /*
     * On "attrape" l'image : déplacement de la souris à droite
     * signifie que le centre de la zone source part à gauche.
     */
    inspection_center_x_ -=
        static_cast<double>(
            delta_x
        ) /
        (
            static_cast<double>(
                logical_width
            ) *
            inspection_zoom_
        );

    inspection_center_y_ -=
        static_cast<double>(
            delta_y
        ) /
        (
            static_cast<double>(
                logical_height
            ) *
            inspection_zoom_
        );

    clamp_inspection_center();

    animation_target_center_x_ =
        inspection_center_x_;

    animation_target_center_y_ =
        inspection_center_y_;

    zoom_indicator_until_ =
        std::chrono::steady_clock::now() +
        zoom_indicator_duration_;

    redraw_requested_ =
        true;
}

void Application::end_pan() noexcept
{
    inspection_dragging_ =
        false;
}

const CameraConfig*
Application::focused_camera() const noexcept
{
    if (
        !focused_camera_index_.has_value() ||
        *focused_camera_index_ >= cameras_.size()
    ) {
        return nullptr;
    }

    return &cameras_[
        *focused_camera_index_
    ];
}

bool Application::focused_camera_has_ptz() const noexcept
{
    const CameraConfig* camera =
        focused_camera();

    return (
        focus_player_ != nullptr &&
        focus_player_->frame_ready() &&
        camera != nullptr &&
        camera->ptz_enabled
    );
}

void Application::begin_ptz_command(
    const PtzCommand command
)
{
    const CameraConfig* camera =
        focused_camera();

    if (
        camera == nullptr ||
        !camera->ptz_enabled ||
        command == PtzCommand::None ||
        command == PtzCommand::Stop
    ) {
        return;
    }

    ptz_preset_menu_open_ = false;
    stop_ptz_command();

    if (
        ptz_controller_.send(
            *camera,
            command
        )
    ) {
        active_ptz_command_ =
            command;
        ptz_pointer_active_ =
            true;
        show_ptz_overlay();
        SDL_CaptureMouse(
            SDL_TRUE
        );
        redraw_requested_ =
            true;
    }
}

void Application::stop_ptz_command(
    const bool force
) noexcept
{
    const CameraConfig* camera =
        focused_camera();

    if (
        camera != nullptr &&
        camera->ptz_enabled &&
        (
            force ||
            ptz_pointer_active_ ||
            active_ptz_command_ !=
                PtzCommand::None
        )
    ) {
        (void) ptz_controller_.send(
            *camera,
            PtzCommand::Stop
        );
    }

    active_ptz_command_ =
        PtzCommand::None;
    ptz_pointer_active_ =
        false;

    if (
        camera != nullptr &&
        camera->ptz_enabled &&
        focus_player_ != nullptr
    ) {
        show_ptz_overlay();
    }
    if (
        (
            SDL_WasInit(
                SDL_INIT_VIDEO
            ) &
            SDL_INIT_VIDEO
        ) != 0
    ) {
        SDL_CaptureMouse(
            SDL_FALSE
        );
    }
    redraw_requested_ =
        true;
}

void Application::call_ptz_preset(
    const std::size_t preset_index
) noexcept
{
    const CameraConfig* camera =
        focused_camera();

    if (
        camera == nullptr ||
        !camera->ptz_enabled ||
        preset_index >=
            camera->ptz_presets.size()
    ) {
        return;
    }

    stop_ptz_command();
    ptz_preset_menu_open_ = false;

    (void) ptz_controller_.send_preset(
        *camera,
        camera->ptz_presets[
            preset_index
        ].token
    );

    show_ptz_overlay();
}

void Application::show_ptz_overlay() noexcept
{
    ptz_overlay_visible_ = true;
    ptz_overlay_until_ =
        std::chrono::steady_clock::now() +
        ptz_overlay_timeout_;
    redraw_requested_ = true;
}

void Application::update_ptz_overlay_visibility() noexcept
{
    if (
        !ptz_overlay_visible_ ||
        ptz_pointer_active_ ||
        ptz_preset_menu_open_
    ) {
        return;
    }

    if (
        std::chrono::steady_clock::now() >=
        ptz_overlay_until_
    ) {
        ptz_overlay_visible_ = false;
        redraw_requested_ = true;
    }
}

bool Application::zoom_indicator_visible() const noexcept
{
    return (
        focus_player_ != nullptr &&
        std::chrono::steady_clock::now() <
            zoom_indicator_until_
    );
}

void Application::render()
{
    /*
     * On bascule vers le focus dès que libmpv annonce sa première
     * vraie frame (frame_pending_), pas seulement après qu'elle ait
     * déjà été rendue.
     *
     * Cela casse la boucle logique de la v0.6.3 :
     *   "j'affiche le focus quand il a été rendu"
     *   alors qu'il ne pouvait être rendu qu'une fois affiché.
     *
     * Si la caméra focus est hors ligne, aucune frame n'est prête :
     * la mosaïque reste donc visible, comme prévu.
     */
    if (
        focus_player_ != nullptr &&
        focus_player_->frame_ready()
    ) {
        const CameraConfig* camera =
            focused_camera();

        static const std::vector<PtzPreset>
            no_presets;

        renderer_->render_focus(
            *focus_player_,
            inspection_zoom_,
            inspection_center_x_,
            inspection_center_y_,
            zoom_indicator_visible(),
            focused_camera_has_ptz(),
            ptz_overlay_visible_,
            active_ptz_command_,
            camera != nullptr
                ? camera->ptz_presets
                : no_presets,
            ptz_preset_menu_open_
        );
        return;
    }

    renderer_->render(
        players_,
        layout_
    );
}

std::optional<std::size_t>
Application::camera_index_at(
    const int mouse_x,
    const int mouse_y
) const
{
    if (
        window_ == nullptr ||
        players_.empty()
    ) {
        return std::nullopt;
    }

    int logical_width = 0;
    int logical_height = 0;

    SDL_GetWindowSize(
        window_->native_handle(),
        &logical_width,
        &logical_height
    );

    const int drawable_width =
        window_->drawable_width();

    const int drawable_height =
        window_->drawable_height();

    if (
        logical_width <= 0 ||
        logical_height <= 0 ||
        drawable_width <= 0 ||
        drawable_height <= 0
    ) {
        return std::nullopt;
    }

    const int drawable_x =
        mouse_x *
        drawable_width /
        logical_width;

    const int drawable_y =
        mouse_y *
        drawable_height /
        logical_height;

    const auto rectangles =
        grid_.calculate(
            players_.size(),
            drawable_width,
            drawable_height,
            layout_
        );

    for (
        std::size_t index = 0;
        index < rectangles.size();
        ++index
    ) {
        const Rect& rectangle =
            rectangles[index];

        const bool inside_x =
            drawable_x >= rectangle.x &&
            drawable_x <
                rectangle.x +
                rectangle.width;

        const bool inside_y =
            drawable_y >= rectangle.y &&
            drawable_y <
                rectangle.y +
                rectangle.height;

        if (inside_x && inside_y) {
            return index;
        }
    }

    return std::nullopt;
}

} // namespace pidecoder
