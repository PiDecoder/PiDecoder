#include "pidecoder/Config.hpp"

#include <nlohmann/json.hpp>

#include <fstream>
#include <stdexcept>
#include <utility>

namespace pidecoder {

namespace {

/*
 * Réécrit le schéma "rtsp://" en "rtsps://" quand l'utilisateur a coché
 * l'option RTSPS pour cette caméra (menu avancé de la config Web, voir
 * CameraConfig::rtsps_enabled). Ne touche pas une URL qui n'utilise pas
 * exactement ce schéma — pas de double réécriture si l'utilisateur a déjà
 * tapé une URL "rtsps://" à la main dans le champ avancé.
 */
std::string with_rtsps_scheme(const std::string& url)
{
    static const std::string prefix = "rtsp://";

    if (url.rfind(prefix, 0) != 0) {
        return url;
    }

    return "rtsps://" + url.substr(prefix.size());
}

} // namespace

std::vector<CameraConfig> Config::load(
    const std::string& path
)
{
    std::ifstream input{path};

    if (!input) {
        throw std::runtime_error(
            "Impossible d'ouvrir la configuration : " +
            path
        );
    }

    nlohmann::json document;
    input >> document;

    if (
        !document.contains("cameras") ||
        !document["cameras"].is_array()
    ) {
        throw std::runtime_error(
            "La configuration doit contenir un tableau cameras"
        );
    }

    std::vector<CameraConfig> cameras;

    for (
        const auto& item :
        document["cameras"]
    ) {
        CameraConfig camera;
        camera.name =
            item.value(
                "name",
                "Caméra"
            );
        camera.grid_url =
            item.value(
                "grid_url",
                ""
            );
        camera.focus_url =
            item.value(
                "focus_url",
                camera.grid_url
            );
        camera.enabled =
            item.value(
                "enabled",
                true
            );

        if (!camera.enabled) {
            continue;
        }

        camera.audio_enabled =
            item.value(
                "audio_enabled",
                false
            );

        camera.rtsps_enabled =
            item.value(
                "rtsps_enabled",
                false
            );

        if (camera.grid_url.empty()) {
            throw std::runtime_error(
                "URL mosaïque absente pour : " +
                camera.name
            );
        }

        if (camera.focus_url.empty()) {
            camera.focus_url =
                camera.grid_url;
        }

        if (camera.rtsps_enabled) {
            camera.grid_url = with_rtsps_scheme(camera.grid_url);
            camera.focus_url = with_rtsps_scheme(camera.focus_url);
        }

        if (
            item.contains("onvif") &&
            item["onvif"].is_object()
        ) {
            const auto& metadata =
                item["onvif"];

            camera.ptz_xaddr =
                metadata.value(
                    "ptz_xaddr",
                    ""
                );

            camera.ptz_profile_token =
                metadata.value(
                    "ptz_profile_token",
                    metadata.value(
                        "focus_profile_token",
                        metadata.value(
                            "grid_profile_token",
                            ""
                        )
                    )
                );

            camera.ptz_enabled =
                !camera.ptz_xaddr.empty() &&
                !camera.ptz_profile_token.empty();

            if (
                metadata.contains("ptz_presets") &&
                metadata["ptz_presets"].is_array()
            ) {
                for (
                    const auto& preset_item :
                    metadata["ptz_presets"]
                ) {
                    if (!preset_item.is_object()) {
                        continue;
                    }

                    PtzPreset preset;
                    preset.token =
                        preset_item.value(
                            "token",
                            ""
                        );
                    preset.name =
                        preset_item.value(
                            "name",
                            preset.token
                        );

                    if (preset.token.empty()) {
                        continue;
                    }

                    if (preset.name.empty()) {
                        preset.name = preset.token;
                    }

                    camera.ptz_presets.push_back(
                        std::move(preset)
                    );
                }
            }
        }

        cameras.push_back(
            std::move(camera)
        );
    }

    if (cameras.empty()) {
        throw std::runtime_error(
            "Aucune caméra active dans la configuration"
        );
    }

    return cameras;
}

} // namespace pidecoder
