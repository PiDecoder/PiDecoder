#include "pidecoder/Config.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <stdexcept>
#include <utility>
namespace pidecoder {
std::vector<CameraConfig> Config::load(const std::string& path)
{
    std::ifstream input{path};
    if (!input) throw std::runtime_error("Impossible d'ouvrir la configuration : " + path);
    nlohmann::json doc; input >> doc;
    if (!doc.contains("cameras") || !doc["cameras"].is_array())
        throw std::runtime_error("La configuration doit contenir un tableau cameras");
    std::vector<CameraConfig> cameras;
    for (const auto& item : doc["cameras"]) {
        CameraConfig c;
        c.name = item.value("name", "Caméra");
        c.grid_url = item.value("grid_url", "");
        c.focus_url = item.value("focus_url", c.grid_url);
        c.enabled = item.value("enabled", true);
        if (!c.enabled) continue;
        if (c.grid_url.empty()) throw std::runtime_error("URL mosaïque absente pour : " + c.name);
        if (c.focus_url.empty()) c.focus_url = c.grid_url;
        cameras.push_back(std::move(c));
    }
    if (cameras.empty()) throw std::runtime_error("Aucune caméra active dans la configuration");
    return cameras;
}
}
