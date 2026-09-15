#pragma once

#include <string>
#include <vector>

namespace pidecoder {

struct PtzPreset final {
    std::string token;
    std::string name;
};

struct CameraConfig final {
    std::string name;
    std::string grid_url;
    std::string focus_url;
    bool enabled{true};

    /*
     * Coché par l'utilisateur dans la config Web pour les caméras
     * dont le flux RTSP diffuse aussi une piste audio (ex. un
     * interphone avec micro). Décoché par défaut à l'ajout d'une
     * caméra. Sert à deux choses côté moteur natif (voir
     * Player::configure) : assouplir les réglages mosaïque pour ces
     * caméras seulement (une piste audio entrelacée sur le flux UDP
     * de la mosaïque peut sinon provoquer un décalage d'image
     * croissant), et décider si le bouton son doit être proposé en
     * vue Focus.
     */
    bool audio_enabled{false};

    bool ptz_enabled{false};
    std::string ptz_xaddr;
    std::string ptz_profile_token;
    std::vector<PtzPreset> ptz_presets;
};

} // namespace pidecoder
