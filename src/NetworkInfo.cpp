#include "pidecoder/NetworkInfo.hpp"

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <unistd.h>

#include <cctype>
#include <cstdio>
#include <cstdlib>

namespace pidecoder {

namespace {

/*
 * Adresse IPv4 "principale" du Pi et nom de l'interface qui la porte
 * (pour aller ensuite chercher l'adresse MAC de cette même interface,
 * voir mac_address_for_interface() ci-dessous) : la première interface
 * active, différente de la boucle locale et hors plage link-local
 * (169.254.0.0/16 — une adresse que Linux s'attribue tout seul faute de
 * DHCP/IP statique, inutilisable pour joindre le Pi depuis un autre
 * poste). Ce projet suppose une seule interface réseau active à la fois
 * (Ethernet ou Wi-Fi, voir docs/PROJECT-STATE.md) : "la première
 * trouvée" suffit donc en pratique, sans essayer de choisir entre
 * plusieurs interfaces actives simultanément.
 */
struct LocalIpv4 {
    std::string address;
    std::string interface_name;
};

LocalIpv4 local_ipv4_address()
{
    struct ifaddrs* interfaces = nullptr;

    if (
        getifaddrs(&interfaces) != 0 ||
        interfaces == nullptr
    ) {
        return {};
    }

    LocalIpv4 result;

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

        result.address = candidate;
        result.interface_name =
            (entry->ifa_name != nullptr)
                ? std::string{entry->ifa_name}
                : std::string{};
        break;
    }

    freeifaddrs(interfaces);

    return result;
}

/*
 * Adresse MAC de `interface_name` (celle qui porte l'adresse IPv4
 * affichée, pas "une" interface au hasard — utile en pratique pour une
 * réservation DHCP par adresse MAC). Sous Linux, getifaddrs() renvoie
 * aussi, pour chaque interface, une entrée de famille AF_PACKET
 * (sockaddr_ll) qui porte l'adresse matérielle — pas besoin de socket ni
 * d'ioctl séparé. Chaîne vide si l'interface est absente de cette
 * seconde liste ou si son adresse matérielle ne fait pas 6 octets
 * (ce qui exclurait par exemple `lo`, sans intérêt ici de toute façon).
 */
std::string mac_address_for_interface(const std::string& interface_name)
{
    if (interface_name.empty()) {
        return {};
    }

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
            entry->ifa_addr->sa_family != AF_PACKET ||
            entry->ifa_name == nullptr ||
            interface_name != entry->ifa_name
        ) {
            continue;
        }

        const auto* link =
            reinterpret_cast<struct sockaddr_ll*>(
                static_cast<void*>(entry->ifa_addr)
            );

        if (link->sll_halen != 6U) {
            continue;
        }

        char buffer[18] = {};

        std::snprintf(
            buffer,
            sizeof(buffer),
            "%02X:%02X:%02X:%02X:%02X:%02X",
            link->sll_addr[0],
            link->sll_addr[1],
            link->sll_addr[2],
            link->sll_addr[3],
            link->sll_addr[4],
            link->sll_addr[5]
        );

        result = buffer;
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
    const LocalIpv4 network = local_ipv4_address();

    if (network.address.empty()) {
        return {};
    }

    std::string text = "IP " + network.address;

    const std::string mac =
        mac_address_for_interface(network.interface_name);

    if (!mac.empty()) {
        text += "  MAC " + mac;
    }

    const std::string hostname = local_hostname_uppercase();

    if (!hostname.empty()) {
        text += "  HOTE " + hostname;
    }

    text += "  WEB :" + web_admin_port();

    return text;
}

} // namespace pidecoder
