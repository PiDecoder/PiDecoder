#include "pidecoder/NetworkInfo.hpp"

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <netinet/in.h>
#include <unistd.h>

#include <cctype>
#include <cstdlib>

namespace pidecoder {

namespace {

/*
 * Adresse IPv4 "principale" du Pi : la première interface active,
 * différente de la boucle locale et hors plage link-local
 * (169.254.0.0/16 — une adresse que Linux s'attribue tout seul faute de
 * DHCP/IP statique, inutilisable pour joindre le Pi depuis un autre
 * poste). Ce projet suppose une seule interface réseau active à la fois
 * (Ethernet ou Wi-Fi, voir docs/PROJECT-STATE.md) : "la première
 * trouvée" suffit donc en pratique, sans essayer de choisir entre
 * plusieurs interfaces actives simultanément.
 */
std::string local_ipv4_address()
{
    struct ifaddrs* interfaces = nullptr;

    if (
        getifaddrs(&interfaces) != 0 ||
        interfaces == nullptr
    ) {
        return {};
    }

    std::string result;

    for (
        struct ifaddrs* entry = interfaces;
        entry != nullptr;
        entry = entry->ifa_next
    ) {
        if (
            entry->ifa_addr == nullptr ||
            entry->ifa_addr->sa_family != AF_INET
        ) {
            continue;
        }

        if (
            (entry->ifa_flags & IFF_LOOPBACK) != 0U ||
            (entry->ifa_flags & IFF_UP) == 0U
        ) {
            continue;
        }

        char buffer[INET_ADDRSTRLEN] = {};

        const auto* address =
            reinterpret_cast<struct sockaddr_in*>(
                static_cast<void*>(entry->ifa_addr)
            );

        if (
            inet_ntop(
                AF_INET,
                &address->sin_addr,
                buffer,
                sizeof(buffer)
            ) == nullptr
        ) {
            continue;
        }

        const std::string candidate{buffer};

        if (candidate.rfind("169.254.", 0) == 0) {
            continue;
        }

        result = candidate;
        break;
    }

    freeifaddrs(interfaces);

    return result;
}

/*
 * En majuscules : le rendu à l'écran (Renderer::draw_text) ne dispose
 * que d'une police bitmap A-Z/0-9/quelques symboles (voir glyph_for()
 * dans Renderer.cpp) — un nom d'hôte en minuscules s'afficherait en
 * points d'interrogation.
 */
std::string local_hostname_uppercase()
{
    char buffer[256] = {};

    if (
        gethostname(
            buffer,
            sizeof(buffer) - 1U
        ) != 0
    ) {
        return {};
    }

    std::string hostname{buffer};

    for (char& character : hostname) {
        character =
            static_cast<char>(
                std::toupper(
                    static_cast<unsigned char>(character)
                )
            );
    }

    return hostname;
}

/*
 * Le player n'a par ailleurs aucune connaissance du port de
 * l'administration Web (processus Python séparé, voir
 * scripts/config-web.py) : install.sh le publie dans
 * PIDECODER_WEB_PORT via systemd/pidecoder.service.in pour que ce
 * binaire puisse l'afficher sans dupliquer sa propre configuration.
 * 8080 par défaut si la variable est absente (ancienne installation pas
 * encore mise à jour), pour rester cohérent avec le port par défaut de
 * config-web.py.
 */
std::string web_admin_port()
{
    const char* env_port =
        std::getenv("PIDECODER_WEB_PORT");

    return
        (env_port != nullptr && env_port[0] != '\0')
            ? std::string{env_port}
            : std::string{"8080"};
}

} // namespace

std::string startup_network_info_text()
{
    const std::string ip = local_ipv4_address();

    if (ip.empty()) {
        return {};
    }

    std::string text = "IP " + ip;

    const std::string hostname = local_hostname_uppercase();

    if (!hostname.empty()) {
        text += "  HOTE " + hostname;
    }

    text += "  WEB :" + web_admin_port();

    return text;
}

} // namespace pidecoder
