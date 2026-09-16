#pragma once

#include <string>

namespace pidecoder {

/*
 * Construit le texte de l'overlay "informations réseau" affiché quelques
 * secondes au démarrage du player (et rappelable au clavier) : adresse
 * IPv4 locale, adresse MAC de la même interface, nom d'hôte et port de
 * l'interface Web d'administration — de quoi retrouver le Pi sur le
 * réseau (y compris par son adresse MAC, ex. pour une réservation DHCP)
 * sans écran/clavier branché dessus ni accès SSH préalable.
 *
 * Recalculé à chaque appel plutôt que mis en cache par l'appelant — voir
 * Application::show_startup_info_overlay() — pour rester à jour si
 * l'adresse a changé depuis le démarrage (via la page Web, par exemple).
 *
 * Renvoie deux lignes séparées par '\n' (IP + nom d'hôte, puis MAC + port
 * Web) — c'est Renderer::draw_startup_info_overlay() qui coupe sur ce
 * séparateur pour dessiner un petit encart à deux lignes plutôt qu'une
 * seule ligne dense ; draw_text() lui-même ne sait pas interpréter '\n'.
 *
 * Renvoie une chaîne vide si aucune adresse IPv4 utilisable n'a pu être
 * déterminée (aucune interface active, par exemple juste après le
 * démarrage réseau) ; l'appelant doit alors simplement ne pas afficher
 * l'overlay plutôt que de montrer une ligne vide. L'adresse MAC, elle,
 * est omise silencieusement si elle n'a pas pu être lue (l'IP reste
 * l'information essentielle) plutôt que de faire échouer tout l'overlay.
 */
[[nodiscard]] std::string startup_network_info_text();

} // namespace pidecoder
