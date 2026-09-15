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

    /*
     * Coché par l'utilisateur dans le menu avancé de la config Web (pour
     * ne pas encombrer la ligne principale de chaque caméra) : demande
     * au moteur natif de se connecter en RTSPS (RTSP sur TLS) plutôt
     * qu'en RTSP en clair. Décoché par défaut, y compris pour une
     * caméra déjà existante — c'est un choix explicite, pas une
     * migration automatique, puisque ça dépend entièrement du support
     * RTSPS de la caméra elle-même.
     *
     * Traité dans Config::load() : quand cette case est cochée, le
     * schéma de grid_url/focus_url est réécrit de "rtsp://" vers
     * "rtsps://" avant que le moteur ne s'en serve — la configuration
     * Web continue de stocker/afficher une URL "rtsp://" classique
     * (celle que la caméra annonce réellement en ONVIF), seule cette
     * case change le comportement de connexion. Voir aussi
     * Player::configure() pour les réglages TLS côté ffmpeg (vérification
     * du certificat volontairement permissive : les caméras présentent
     * presque toujours un certificat auto-signé, sans autorité
     * commune avec l'interface Web).
     */
    bool rtsps_enabled{false};

    bool ptz_enabled{false};
    std::string ptz_xaddr;
    std::string ptz_profile_token;
    std::vector<PtzPreset> ptz_presets;
};

} // namespace pidecoder
