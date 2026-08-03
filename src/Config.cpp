#include "pidecoder/Config.hpp"

#include <nlohmann/json.hpp>

#include <fstream>
#include <stdexcept>
#include <utility>

namespace pidecoder {

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
