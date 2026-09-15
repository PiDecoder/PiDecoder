#include "pidecoder/Player.hpp"
#include "pidecoder/RedactUrl.hpp"
#include <SDL2/SDL_opengl.h>
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <utility>

namespace pidecoder {

Player::Player(
    std::string url,
    const Uint32 mpv_event_type,
    const Uint32 render_event_type,
    const PlayerRole role,
    const bool audio_capable
)
    : url_(std::move(url)),
      role_(role),
      audio_capable_(audio_capable),
      mpv_event_type_(mpv_event_type),
      render_event_type_(render_event_type)
{
}

Player::~Player()
{
    destroy();
}

void Player::initialize()
{
    if (initialized_) return;

    mpv_ = mpv_create();
    if (mpv_ == nullptr) {
        throw std::runtime_error("mpv_create a échoué");
    }

    configure();
    check(mpv_initialize(mpv_), "mpv_initialize");

    mpv_opengl_init_params gl_init_params{
        get_proc_address,
        nullptr
    };

    mpv_render_param context_params[] = {
        {MPV_RENDER_PARAM_API_TYPE, const_cast<char*>(MPV_RENDER_API_TYPE_OPENGL)},
        {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS, &gl_init_params},
        {MPV_RENDER_PARAM_INVALID, nullptr}
    };

    check(
        mpv_render_context_create(
            &render_context_,
            mpv_,
            context_params
        ),
        "mpv_render_context_create"
    );

    mpv_set_wakeup_callback(mpv_, on_mpv_event, this);
    mpv_render_context_set_update_callback(
        render_context_,
        on_render_update,
        this
    );

    callbacks_attached_ = true;
    initialized_ = true;
    state_ = PlayerState::Connecting;
}

void Player::load()
{
    if (!initialized_) {
        throw std::logic_error(
            "Player::initialize doit être appelé avant Player::load"
        );
    }

    const char* command[] = {
        "loadfile",
        url_.c_str(),
        "replace",
        nullptr
    };

    state_ = PlayerState::Connecting;
    loaded_ = false;
    frame_pending_ = false;
    load_started_at_ =
        std::chrono::steady_clock::now();

    const int status =
        mpv_command_async(
            mpv_,
            0,
            command
        );

    if (status < 0) {
        state_ = PlayerState::Error;
        error_marker_visible_ = true;
        schedule_reconnect();
    }
}

bool Player::tick()
{
    const auto now =
        std::chrono::steady_clock::now();

    /*
     * Une session RTSP TCP peut rester ouverte alors que plus aucune
     * image n'arrive. Dans ce cas libmpv ne produit pas forcément
     * MPV_EVENT_END_FILE : on détecte donc nous-mêmes le gel.
     */
    if (
        state_ == PlayerState::Online &&
        last_frame_at_.time_since_epoch().count() != 0 &&
        now - last_frame_at_ >= frame_stall_timeout_
    ) {
        loaded_ = false;
        state_ = PlayerState::Error;
        frame_pending_ = false;
        error_marker_visible_ = true;

        std::cerr
            << "Watchdog video: aucune nouvelle image depuis "
            << frame_stall_timeout_.count()
            << " s : "
            << redact_credentials(url_)
            << std::endl;

        schedule_reconnect();
        return true;
    }

    /*
     * Même protection pendant l'ouverture du flux. Cela couvre les
     * caméras débranchées pour lesquelles avformat_open_input reste
     * occupé jusqu'au timeout réseau.
     */
    if (
        state_ == PlayerState::Connecting &&
        load_started_at_.time_since_epoch().count() != 0 &&
        now - load_started_at_ >= connect_timeout_
    ) {
        loaded_ = false;
        state_ = PlayerState::Error;
        frame_pending_ = false;
        error_marker_visible_ = true;

        std::cerr
            << "Watchdog connexion: timeout RTSP : "
            << redact_credentials(url_)
            << std::endl;

        schedule_reconnect();
        return true;
    }

    if (
        (state_ == PlayerState::Offline ||
         state_ == PlayerState::Error) &&
        now >= reconnect_at_
    ) {
        reconnect_now();
        return true;
    }

    return false;
}

void Player::process_events(bool& application_running)
{
    mpv_event_pending_.store(false, std::memory_order_release);

    if (mpv_ == nullptr) return;

    while (true) {
        mpv_event* event = mpv_wait_event(mpv_, 0.0);

        if (event->event_id == MPV_EVENT_NONE) {
            break;
        }

        switch (event->event_id) {
            case MPV_EVENT_FILE_LOADED:
                loaded_ = true;
                state_ = PlayerState::Online;
                reconnect_delay_ = std::chrono::seconds{2};
                last_frame_at_ =
                    std::chrono::steady_clock::now();
                std::cout
                    << "Flux RTSP chargé : "
                    << redact_credentials(url_)
                    << std::endl;
                break;

            case MPV_EVENT_VIDEO_RECONFIG:
                if (loaded_) {
                    state_ = PlayerState::Online;
                }
                break;

            case MPV_EVENT_END_FILE: {
                loaded_ = false;
                frame_pending_ = false;
                error_marker_visible_ = true;

                const auto* end_event =
                    static_cast<mpv_event_end_file*>(event->data);

                state_ =
                    end_event->reason == MPV_END_FILE_REASON_ERROR
                    ? PlayerState::Error
                    : PlayerState::Offline;

                std::cerr
                    << "Flux indisponible : "
                    << redact_credentials(url_)
                    << ", raison="
                    << end_event->reason
                    << ", erreur="
                    << end_event->error
                    << std::endl;

                schedule_reconnect();
                break;
            }

            case MPV_EVENT_SHUTDOWN:
                application_running = false;
                break;

            default:
                break;
        }
    }
}

bool Player::update_render_state()
{
    render_event_pending_.store(
        false,
        std::memory_order_release
    );

    if (render_context_ == nullptr) {
        return false;
    }

    const std::uint64_t flags =
        mpv_render_context_update(
            render_context_
        );

    if (
        (flags & MPV_RENDER_UPDATE_FRAME) != 0
    ) {
        frame_pending_ = true;
        last_frame_at_ =
            std::chrono::steady_clock::now();

        return true;
    }

    return false;
}

void Player::render(
    const Rect& target,
    const int /*canvas_width*/,
    const int canvas_height
)
{
    if (
        target.width <= 0 ||
        target.height <= 0 ||
        canvas_height <= 0
    ) {
        return;
    }

    render_pending_frame(
        target.width,
        target.height
    );

    if (
        has_rendered_frame_ &&
        framebuffer_ != 0
    ) {
        blit_last_frame(
            target,
            canvas_height
        );
    }
}

void Player::render_inspected(
    const Rect& target,
    const int /*canvas_width*/,
    const int canvas_height,
    const double zoom,
    const double center_x,
    const double center_y
)
{
    if (
        target.width <= 0 ||
        target.height <= 0 ||
        canvas_height <= 0
    ) {
        return;
    }

    render_pending_frame(
        target.width,
        target.height
    );

    if (
        has_rendered_frame_ &&
        framebuffer_ != 0
    ) {
        blit_last_frame_inspected(
            target,
            canvas_height,
            zoom,
            center_x,
            center_y
        );
    }
}

void Player::render_pending_frame(
    const int width,
    const int height
)
{
    /*
     * Le pipeline libmpv reste strictement identique à la v0.8.0.
     * L'inspection numérique intervient uniquement au moment du blit.
     */
    if (
        !frame_pending_ ||
        render_context_ == nullptr
    ) {
        return;
    }

    ensure_render_target(
        width,
        height
    );

    glBindFramebuffer(
        GL_FRAMEBUFFER,
        framebuffer_
    );

    glViewport(
        0,
        0,
        render_width_,
        render_height_
    );

    mpv_opengl_fbo mpv_framebuffer{
        static_cast<int>(framebuffer_),
        render_width_,
        render_height_,
        0
    };

    int flip_y = 1;

    mpv_render_param render_params[] = {
        {
            MPV_RENDER_PARAM_OPENGL_FBO,
            &mpv_framebuffer
        },
        {
            MPV_RENDER_PARAM_FLIP_Y,
            &flip_y
        },
        {
            MPV_RENDER_PARAM_INVALID,
            nullptr
        }
    };

    check(
        mpv_render_context_render(
            render_context_,
            render_params
        ),
        "Rendu libmpv"
    );

    frame_pending_ = false;
    has_rendered_frame_ = true;
    error_marker_visible_ = false;
}

void Player::blit_last_frame(
    const Rect& target,
    const int canvas_height
)
{
    if (
        framebuffer_ == 0 ||
        render_width_ <= 0 ||
        render_height_ <= 0
    ) {
        return;
    }

    glBindFramebuffer(
        GL_READ_FRAMEBUFFER,
        framebuffer_
    );

    glBindFramebuffer(
        GL_DRAW_FRAMEBUFFER,
        0
    );

    const int destination_y_bottom =
        canvas_height -
        target.y -
        target.height;

    const int destination_y_top =
        canvas_height -
        target.y;

    glBlitFramebuffer(
        0,
        0,
        render_width_,
        render_height_,
        target.x,
        destination_y_bottom,
        target.x + target.width,
        destination_y_top,
        GL_COLOR_BUFFER_BIT,
        GL_LINEAR
    );

    glBindFramebuffer(
        GL_FRAMEBUFFER,
        0
    );
}

void Player::blit_last_frame_inspected(
    const Rect& target,
    const int canvas_height,
    const double requested_zoom,
    const double requested_center_x,
    const double requested_center_y
)
{
    if (
        framebuffer_ == 0 ||
        render_width_ <= 0 ||
        render_height_ <= 0
    ) {
        return;
    }

    const double zoom =
        std::clamp(
            requested_zoom,
            1.0,
            5.0
        );

    const double visible_width =
        1.0 / zoom;

    const double visible_height =
        1.0 / zoom;

    const double center_x =
        std::clamp(
            requested_center_x,
            visible_width / 2.0,
            1.0 - visible_width / 2.0
        );

    const double center_y =
        std::clamp(
            requested_center_y,
            visible_height / 2.0,
            1.0 - visible_height / 2.0
        );

    const double source_left_normalized =
        center_x -
        visible_width / 2.0;

    const double source_right_normalized =
        center_x +
        visible_width / 2.0;

    const double source_top_normalized =
        center_y -
        visible_height / 2.0;

    const double source_bottom_normalized =
        center_y +
        visible_height / 2.0;

    const int source_left =
        static_cast<int>(
            source_left_normalized *
            static_cast<double>(render_width_)
        );

    const int source_right =
        static_cast<int>(
            source_right_normalized *
            static_cast<double>(render_width_)
        );

    /*
     * center_y est exprimé depuis le haut de l'image,
     * alors qu'OpenGL adresse le framebuffer depuis le bas.
     */
    const int source_bottom =
        static_cast<int>(
            (
                1.0 -
                source_bottom_normalized
            ) *
            static_cast<double>(render_height_)
        );

    const int source_top =
        static_cast<int>(
            (
                1.0 -
                source_top_normalized
            ) *
            static_cast<double>(render_height_)
        );

    glBindFramebuffer(
        GL_READ_FRAMEBUFFER,
        framebuffer_
    );

    glBindFramebuffer(
        GL_DRAW_FRAMEBUFFER,
        0
    );

    const int destination_y_bottom =
        canvas_height -
        target.y -
        target.height;

    const int destination_y_top =
        canvas_height -
        target.y;

    glBlitFramebuffer(
        source_left,
        source_bottom,
        source_right,
        source_top,
        target.x,
        destination_y_bottom,
        target.x + target.width,
        destination_y_top,
        GL_COLOR_BUFFER_BIT,
        GL_LINEAR
    );

    glBindFramebuffer(
        GL_FRAMEBUFFER,
        0
    );
}

void Player::detach_callbacks() noexcept
{
    if (!callbacks_attached_) return;

    if (render_context_ != nullptr) {
        mpv_render_context_set_update_callback(
            render_context_,
            nullptr,
            nullptr
        );
    }

    if (mpv_ != nullptr) {
        mpv_set_wakeup_callback(
            mpv_,
            nullptr,
            nullptr
        );
    }

    callbacks_attached_ = false;
    mpv_event_pending_.store(false, std::memory_order_release);
    render_event_pending_.store(false, std::memory_order_release);
}

const std::string& Player::url() const noexcept
{
    return url_;
}

bool Player::loaded() const noexcept
{
    return loaded_;
}

PlayerState Player::state() const noexcept
{
    return state_;
}

bool Player::has_error() const noexcept
{
    return (
        state_ == PlayerState::Offline ||
        state_ == PlayerState::Error
    );
}

bool Player::has_rendered_frame() const noexcept
{
    return has_rendered_frame_;
}

bool Player::frame_ready() const noexcept
{
    /*
     * frame_pending_ signifie que libmpv a annoncé une vraie nouvelle
     * frame mais qu'elle n'a pas encore été dessinée dans notre FBO.
     *
     * has_rendered_frame_ permet ensuite de rester en focus entre deux
     * frames sans revenir brièvement à la mosaïque.
     */
    return frame_pending_ || has_rendered_frame_;
}

bool Player::error_marker_visible() const noexcept
{
    return error_marker_visible_;
}

void Player::set_muted(const bool muted)
{
    audio_muted_ = muted;

    if (role_ != PlayerRole::Focus || mpv_ == nullptr) {
        return;
    }

    /*
     * On ne se contente pas de la propriété "mute" (qui ne fait que
     * rendre le son silencieux) : on active ou désactive le
     * décodage audio lui-même via "aid" ("no" = piste audio non
     * décodée du tout, "auto" = piste audio décodée et jouée).
     *
     * Pourquoi : dès que mpv décode une piste audio, "video-sync"
     * (réglé sur "audio" en Focus, cf. configure()) se met à
     * synchroniser l'image sur l'horloge audio. Sur un flux RTSP de
     * caméra, cette horloge peut être irrégulière (paquets audio
     * espacés, jitter réseau) : coupé par défaut avec "mute" seul,
     * l'image restait donc calée sur un flux audio décodé mais
     * silencieux, avec un fort risque de décalage et de ralenti —
     * exactement le problème constaté en test. En laissant "aid" à
     * "no" tant que l'utilisateur n'a pas explicitement demandé le
     * son, l'image retrouve son comportement d'origine (aucune
     * horloge audio à suivre), identique à celui de la mosaïque.
     */
    check(
        mpv_set_property_string(
            mpv_,
            "aid",
            (audio_capable_ && !muted) ? "auto" : "no"
        ),
        "Changement du son focus"
    );
}

bool Player::muted() const noexcept
{
    return audio_muted_;
}

bool Player::audio_capable() const noexcept
{
    return audio_capable_;
}

bool Player::has_audio_track() const noexcept
{
    /*
     * Piste audio détectée via la liste des pistes du démultiplexeur
     * (track-list), qui recense toutes les pistes trouvées dans le
     * flux dès son ouverture — que la piste audio soit ou non
     * sélectionnée pour le décodage ("aid"). Ça permet de savoir si
     * une caméra a du son avant même que l'utilisateur ait appuyé
     * sur M (voir set_muted() : le décodage audio reste coupé par
     * défaut, donc "audio-codec-name" resterait vide).
     *
     * audio_capable_ à faux (case "cette caméra a un micro" décochée
     * en config Web) coupe court immédiatement : on ne propose pas
     * le contrôle audio pour une caméra que l'utilisateur n'a pas
     * signalée comme telle, même si son flux en contient une.
     */
    if (
        role_ != PlayerRole::Focus ||
        !audio_capable_ ||
        mpv_ == nullptr ||
        !loaded_
    ) {
        return false;
    }

    int64_t track_count = 0;

    const int count_status =
        mpv_get_property(
            mpv_,
            "track-list/count",
            MPV_FORMAT_INT64,
            &track_count
        );

    if (count_status < 0 || track_count <= 0) {
        return false;
    }

    for (int64_t index = 0; index < track_count; ++index) {
        const std::string property_name =
            "track-list/" +
            std::to_string(index) +
            "/type";

        char* track_type = nullptr;

        const int status =
            mpv_get_property(
                mpv_,
                property_name.c_str(),
                MPV_FORMAT_STRING,
                &track_type
            );

        if (status < 0 || track_type == nullptr) {
            continue;
        }

        const bool is_audio =
            std::string(track_type) == "audio";

        mpv_free(track_type);

        if (is_audio) {
            return true;
        }
    }

    return false;
}

void* Player::get_proc_address(void*, const char* name)
{
    return reinterpret_cast<void*>(
        SDL_GL_GetProcAddress(name)
    );
}

void Player::on_mpv_event(void* context)
{
    auto* player = static_cast<Player*>(context);

    if (
        player->mpv_event_pending_.exchange(
            true,
            std::memory_order_acq_rel
        )
    ) {
        return;
    }

    SDL_Event event{};
    event.type = player->mpv_event_type_;
    event.user.data1 = context;

    if (SDL_PushEvent(&event) < 0) {
        player->mpv_event_pending_.store(
            false,
            std::memory_order_release
        );
    }
}

void Player::on_render_update(void* context)
{
    auto* player = static_cast<Player*>(context);

    if (
        player->render_event_pending_.exchange(
            true,
            std::memory_order_acq_rel
        )
    ) {
        return;
    }

    SDL_Event event{};
    event.type = player->render_event_type_;
    event.user.data1 = context;

    if (SDL_PushEvent(&event) < 0) {
        player->render_event_pending_.store(
            false,
            std::memory_order_release
        );
    }
}

void Player::configure()
{
    check(mpv_set_option_string(mpv_, "vo", "libmpv"), "Configuration vo=libmpv");

    if (role_ == PlayerRole::Focus) {
        /*
         * L'audio n'est disponible qu'en vue Focus (une seule caméra
         * agrandie à la fois) : jouer le son de toutes les vignettes
         * de la mosaïque en même temps serait inexploitable, donc la
         * grille garde l'audio désactivé (branche else ci-dessous).
         *
         * Le son démarre coupé (audio_muted_ vaut true par défaut à
         * la création du Player) : l'utilisateur l'active lui-même
         * avec la touche M ou le bouton, pour éviter un bruit
         * surprise à l'ouverture du focus sur un mur de
         * vidéosurveillance.
         *
         * Important : tant que c'est coupé, on met "aid" à "no",
         * c'est-à-dire qu'on ne décode PAS la piste audio du tout —
         * pas juste "mute" (silencieux mais décodé). "video-sync"
         * est réglé sur "audio" plus bas pour la vue Focus ; si mpv
         * décode réellement une piste audio, l'image se met à suivre
         * l'horloge audio au lieu de son propre rythme. Sur un flux
         * RTSP de caméra, cette horloge audio peut être irrégulière
         * (paquets espacés, jitter réseau), ce qui provoque un
         * décalage et un ralenti de l'image très visibles — c'est le
         * bug remonté en test. En laissant "aid" à "no" par défaut,
         * l'image se comporte exactement comme avant (aucune horloge
         * audio à suivre), et le décodage audio n'est activé qu'au
         * moment où l'utilisateur le demande (voir set_muted(), qui
         * fait exactement la même bascule à chaud).
         *
         * audio_capable_ reflète la case "cette caméra a un micro"
         * cochée par l'utilisateur dans la config Web : si elle n'est
         * pas cochée, on ne décode jamais l'audio pour cette caméra,
         * même si l'utilisateur appuie sur M (set_muted() respecte
         * aussi cette même règle).
         */
        check(
            mpv_set_option_string(
                mpv_,
                "aid",
                (audio_capable_ && !audio_muted_) ? "auto" : "no"
            ),
            "État initial audio focus"
        );
    } else {
        check(mpv_set_option_string(mpv_, "audio", "no"), "Désactivation audio grille");
    }

    check(mpv_set_option_string(mpv_, "hwdec", "no"), "Désactivation hwdec");
    check(mpv_set_option_string(mpv_, "profile", "low-latency"), "Profil low-latency");
    if (role_ == PlayerRole::Grid) {
        /*
         * Mosaïque = priorité absolue à l'image la plus récente.
         *
         * Les flux Axis de test n'exposent pas de PTS fiables :
         * FFmpeg affiche "No video PTS! Making something up".
         *
         * On ne demande donc plus à mpv de respecter une timeline
         * artificielle pour les vignettes. Une frame disponible est
         * rendue dès que possible.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "untimed",
                "yes"
            ),
            "Activation untimed grille"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "video-sync",
                "desync"
            ),
            "Synchronisation desync grille"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "correct-pts",
                "no"
            ),
            "Désactivation correction PTS grille"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "video-latency-hacks",
                "yes"
            ),
            "Activation video-latency-hacks grille"
        );
    } else {
        /*
         * Focus = comportement stable déjà validé.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "untimed",
                "no"
            ),
            "Désactivation untimed focus"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "video-sync",
                "audio"
            ),
            "Synchronisation vidéo focus"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "correct-pts",
                "yes"
            ),
            "Correction PTS focus"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "video-latency-hacks",
                "no"
            ),
            "Désactivation video-latency-hacks focus"
        );
    }
    if (role_ == PlayerRole::Grid) {
        /*
         * Mode "live first" pour les vignettes :
         * on préfère perdre des images plutôt que prendre du retard.
         *
         * decoder+vo permet à libavcodec de jeter aussi des frames
         * devenues inutiles avant le rendu. nonref limite le drop aux
         * images qui ne servent pas de référence aux suivantes.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "framedrop",
                "decoder+vo"
            ),
            "Configuration framedrop grille"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "vd-lavc-framedrop",
                "nonref"
            ),
            "Configuration framedrop decodeur"
        );
    } else {
        /*
         * En focus on privilégie la qualité et on conserve le mode
         * recommandé par mpv.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "framedrop",
                "vo"
            ),
            "Configuration framedrop focus"
        );
    }
    check(mpv_set_option_string(mpv_, "cache", "no"), "Désactivation cache");
    check(mpv_set_option_string(mpv_, "cache-pause", "no"), "Désactivation cache-pause");
    check(mpv_set_option_string(mpv_, "demuxer-readahead-secs", "0"), "Désactivation readahead");

    if (role_ == PlayerRole::Grid) {
        /*
         * Mosaïque = priorité absolue au direct.
         *
         * RTP/UDP ne retransmet pas les paquets perdus comme TCP.
         * max_delay=0 désactive le buffer de réordonnancement RTP
         * de libavformat : une perte peut donc produire un artefact
         * ou une frame jetée, mais ne doit pas créer une file
         * d'attente de plusieurs secondes.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "rtsp-transport",
                "udp"
            ),
            "Transport RTSP UDP grille"
        );

        if (audio_capable_) {
            /*
             * Caméra avec micro (case cochée en config Web) :
             * réglages UDP légèrement assouplis par rapport à la
             * branche ci-dessous, réservée aux caméras purement
             * vidéo.
             *
             * Constaté sur le terrain : les réglages UDP les plus
             * extrêmes (aucune tolérance au réordonnancement des
             * paquets, délai nul) tiennent très bien avec un seul
             * flux RTP (vidéo), mais provoquent un décalage d'image
             * qui grandit avec le temps dès qu'un second flux RTP
             * (audio) arrive entrelacé dessus — reproduit à
             * l'identique sur plusieurs caméras différentes (Axis
             * avec micro activé, Aqara G410), donc lié à la présence
             * d'une piste audio elle-même, pas à une marque ou un
             * codec précis. La vue Focus, qui gère cette même
             * caméra sans souci, utilise TCP (donc pas de
             * réordonnancement RTP à gérer) : ça pointe vers
             * max_delay/reorder_queue_size comme réglages en cause
             * ici.
             *
             * Valeurs choisies avec une marge prudente (toujours très
             * en dessous des valeurs par défaut de FFmpeg) plutôt que
             * strictement minimales : n'ayant pas pu tester sur du
             * matériel réel, un ajustement fin restera sans doute
             * nécessaire une fois validé sur le Pi.
             */
            check(
                mpv_set_option_string(
                    mpv_,
                    "demuxer-lavf-o",
                    "fflags=nobuffer,"
                    "max_delay=200000,"
                    "reorder_queue_size=8,"
                    "use_wallclock_as_timestamps=1,"
                    "analyzeduration=500000,"
                    "probesize=32768"
                ),
                "Configuration RTSP UDP grille (avec audio)"
            );
        } else {
            check(
                mpv_set_option_string(
                    mpv_,
                    "demuxer-lavf-o",
                    "fflags=nobuffer,"
                    "max_delay=0,"
                    "reorder_queue_size=0,"
                    "use_wallclock_as_timestamps=1,"
                    "analyzeduration=0,"
                    "probesize=32"
                ),
                "Configuration RTSP UDP grille"
            );
        }
    } else {
        /*
         * Focus = priorité à la qualité.
         * TCP reste volontairement utilisé pour le flux Full HD.
         */
        check(
            mpv_set_option_string(
                mpv_,
                "rtsp-transport",
                "tcp"
            ),
            "Transport RTSP TCP focus"
        );

        check(
            mpv_set_option_string(
                mpv_,
                "demuxer-lavf-o",
                "fflags=nobuffer,"
                "use_wallclock_as_timestamps=1,"
                "analyzeduration=0,"
                "probesize=32,"
                "stimeout=5000000"
            ),
            "Configuration RTSP TCP focus"
        );
    }

    check(mpv_set_option_string(mpv_, "terminal", "yes"), "Configuration terminal");
    check(mpv_set_option_string(mpv_, "msg-level", "all=warn"), "Configuration logs");
}

void Player::schedule_reconnect()
{
    reconnect_at_ =
        std::chrono::steady_clock::now() +
        reconnect_delay_;

    reconnect_delay_ =
        std::min(
            reconnect_delay_ * 2,
            max_reconnect_delay_
        );
}

void Player::reconnect_now()
{
    /*
     * Après une vraie coupure RTSP, on recrée complètement l'instance
     * libmpv. Certaines connexions RTSP mortes restent sinon dans un
     * état incohérent : le focus repart mais le Player mosaïque peut
     * rester figé.
     *
     * Le framebuffer OpenGL n'est PAS détruit ici : la dernière image
     * valide reste donc visible dans la tuile pendant la reconnexion.
     */
    try {
        restart_mpv_engine();
        load();
    } catch (const std::exception& exception) {
        state_ = PlayerState::Error;

        std::cerr
            << "Echec reconnexion RTSP : "
            << redact_credentials(url_)
            << " : "
            << exception.what()
            << std::endl;

        schedule_reconnect();
    }
}

void Player::restart_mpv_engine()
{
    destroy_mpv_engine();

    mpv_ = mpv_create();

    if (mpv_ == nullptr) {
        throw std::runtime_error(
            "mpv_create a échoué pendant la reconnexion"
        );
    }

    configure();

    check(
        mpv_initialize(mpv_),
        "mpv_initialize reconnexion"
    );

    mpv_opengl_init_params gl_init_params{
        get_proc_address,
        nullptr
    };

    mpv_render_param context_params[] = {
        {
            MPV_RENDER_PARAM_API_TYPE,
            const_cast<char*>(
                MPV_RENDER_API_TYPE_OPENGL
            )
        },
        {
            MPV_RENDER_PARAM_OPENGL_INIT_PARAMS,
            &gl_init_params
        },
        {
            MPV_RENDER_PARAM_INVALID,
            nullptr
        }
    };

    check(
        mpv_render_context_create(
            &render_context_,
            mpv_,
            context_params
        ),
        "mpv_render_context_create reconnexion"
    );

    mpv_set_wakeup_callback(
        mpv_,
        on_mpv_event,
        this
    );

    mpv_render_context_set_update_callback(
        render_context_,
        on_render_update,
        this
    );

    callbacks_attached_ = true;
    initialized_ = true;
    frame_pending_ = false;

    mpv_event_pending_.store(
        false,
        std::memory_order_release
    );

    render_event_pending_.store(
        false,
        std::memory_order_release
    );
}

void Player::destroy_mpv_engine() noexcept
{
    detach_callbacks();

    if (render_context_ != nullptr) {
        mpv_render_context_free(
            render_context_
        );

        render_context_ = nullptr;
    }

    if (mpv_ != nullptr) {
        mpv_terminate_destroy(
            mpv_
        );

        mpv_ = nullptr;
    }

    initialized_ = false;
    loaded_ = false;
    frame_pending_ = false;
}

void Player::ensure_render_target(
    const int width,
    const int height
)
{
    if (
        framebuffer_ != 0 &&
        texture_ != 0 &&
        render_width_ == width &&
        render_height_ == height
    ) {
        return;
    }

    destroy_render_target();

    render_width_ = width;
    render_height_ = height;

    glGenTextures(1, &texture_);
    glBindTexture(GL_TEXTURE_2D, texture_);

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    glTexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_RGBA8,
        render_width_,
        render_height_,
        0,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        nullptr
    );

    glGenFramebuffers(1, &framebuffer_);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);

    glFramebufferTexture2D(
        GL_FRAMEBUFFER,
        GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D,
        texture_,
        0
    );

    const GLenum status =
        glCheckFramebufferStatus(GL_FRAMEBUFFER);

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glBindTexture(GL_TEXTURE_2D, 0);

    if (status != GL_FRAMEBUFFER_COMPLETE) {
        destroy_render_target();
        throw std::runtime_error(
            "Framebuffer OpenGL incomplet"
        );
    }
}

void Player::destroy_render_target() noexcept
{
    if (framebuffer_ != 0) {
        glDeleteFramebuffers(1, &framebuffer_);
        framebuffer_ = 0;
    }

    if (texture_ != 0) {
        glDeleteTextures(1, &texture_);
        texture_ = 0;
    }

    render_width_ = 0;
    render_height_ = 0;
    has_rendered_frame_ = false;
    frame_pending_ = false;
}

void Player::destroy() noexcept
{
    destroy_mpv_engine();
    destroy_render_target();
    error_marker_visible_ = false;
}

void Player::check(
    const int status,
    const std::string& operation
) const
{
    if (status < 0) {
        throw std::runtime_error(
            operation + ": " + mpv_error_string(status)
        );
    }
}

} // namespace pidecoder
