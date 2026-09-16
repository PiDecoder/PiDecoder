#pragma once

#include <string>

namespace pidecoder {

/*
 * Construit le texte de l'overlay "informations réseau" affiché quelques
 * secondes au démarrage du player (et rappelable au clavier) : adresse
 * IPv4 locale, nom d'hôte et port de l'interface Web d'administration —
 * de quoi retrouver le Pi sur le réseau sans écran/clavier branché
 * dessus ni accès SSH préalable.
 *
 * Renvoie une chaîne vide si aucune adresse IPv4 utilisable n'a pu être
 * déterminée (aucune interface active, par exemple juste après le
 * démarrage réseau) ; l'appelant doit alors simplement ne pas afficher
 * l'overlay plutôt que de montrer une ligne vide.
 */
[[nodiscard]] std::string startup_network_info_text();

} // namespace pidecoder
