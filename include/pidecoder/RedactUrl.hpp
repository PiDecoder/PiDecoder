#pragma once

#include <string>

namespace pidecoder {

// Remplace les identifiants éventuellement embarqués dans une URL
// (schéma://utilisateur:motdepasse@hôte/...) par des astérisques, pour
// pouvoir journaliser une URL RTSP/ONVIF sans jamais exposer de mot de
// passe en clair dans journalctl. Ne modifie rien s'il n'y a pas
// d'identifiants, ou si la chaîne n'a pas la forme d'une URL.
[[nodiscard]] std::string redact_credentials(const std::string& url);

} // namespace pidecoder
