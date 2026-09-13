#include "pidecoder/PtzController.hpp"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <iostream>
#include <sstream>
#include <utility>

namespace {

std::string json_escape(
    const std::string& value
)
{
    std::ostringstream output;

    for (const unsigned char character : value) {
        switch (character) {
            case '"':
                output << "\\\"";
                break;
            case '\\':
                output << "\\\\";
                break;
            case '\b':
                output << "\\b";
                break;
            case '\f':
                output << "\\f";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                if (character < 0x20U) {
                    constexpr char hexadecimal[] =
                        "0123456789abcdef";

                    output
                        << "\\u00"
                        << hexadecimal[
                            (character >> 4U) & 0x0FU
                        ]
                        << hexadecimal[
                            character & 0x0FU
                        ];
                } else {
                    output <<
                        static_cast<char>(
                            character
                        );
                }
                break;
        }
    }

    return output.str();
}

} // namespace

namespace pidecoder {

PtzController::PtzController(
    std::string socket_path
)
    : socket_path_(std::move(socket_path))
{
    socket_fd_ = ::socket(
        AF_UNIX,
        SOCK_DGRAM | SOCK_CLOEXEC,
        0
    );

    if (socket_fd_ < 0) {
        std::cerr
            << "PTZ indisponible : impossible de créer le socket local ("
            << std::strerror(errno)
            << ")"
            << std::endl;

        socket_error_reported_ = true;
    }
}

PtzController::~PtzController()
{
    if (socket_fd_ >= 0) {
        ::close(socket_fd_);
    }
}

const char* PtzController::command_name(
    const PtzCommand command
) noexcept
{
    switch (command) {
        case PtzCommand::Up:
            return "up";
        case PtzCommand::Down:
            return "down";
        case PtzCommand::Left:
            return "left";
        case PtzCommand::Right:
            return "right";
        case PtzCommand::Stop:
            return "stop";
        case PtzCommand::ZoomIn:
            return "zoomin";
        case PtzCommand::ZoomOut:
            return "zoomout";
        case PtzCommand::None:
            break;
    }

    return "none";
}

bool PtzController::send_payload(
    const std::string& payload
) noexcept
{
    if (socket_fd_ < 0) {
        return false;
    }

    sockaddr_un address{};
    address.sun_family = AF_UNIX;

    if (
        socket_path_.size() >=
        sizeof(address.sun_path)
    ) {
        if (!socket_error_reported_) {
            std::cerr
                << "PTZ indisponible : chemin de socket trop long"
                << std::endl;
            socket_error_reported_ = true;
        }

        return false;
    }

    std::memcpy(
        address.sun_path,
        socket_path_.c_str(),
        socket_path_.size() + 1
    );

    const ssize_t sent =
        ::sendto(
            socket_fd_,
            payload.data(),
            payload.size(),
            MSG_DONTWAIT,
            reinterpret_cast<const sockaddr*>(
                &address
            ),
            sizeof(address)
        );

    if (
        sent !=
        static_cast<ssize_t>(
            payload.size()
        )
    ) {
        if (!socket_error_reported_) {
            std::cerr
                << "PTZ indisponible : pont local non joignable ("
                << std::strerror(errno)
                << ")"
                << std::endl;
            socket_error_reported_ = true;
        }

        return false;
    }

    socket_error_reported_ = false;
    return true;
}

bool PtzController::send(
    const CameraConfig& camera,
    const PtzCommand command
) noexcept
{
    if (
        !camera.ptz_enabled ||
        camera.ptz_xaddr.empty() ||
        camera.ptz_profile_token.empty() ||
        command == PtzCommand::None
    ) {
        return false;
    }

    try {
        const std::string payload =
            std::string{"{\"action\":\""} +
            json_escape(
                command_name(command)
            ) +
            "\",\"ptz_xaddr\":\"" +
            json_escape(
                camera.ptz_xaddr
            ) +
            "\",\"profile_token\":\"" +
            json_escape(
                camera.ptz_profile_token
            ) +
            "\"}";

        return send_payload(payload);

    } catch (const std::exception& exception) {
        if (!socket_error_reported_) {
            std::cerr
                << "PTZ indisponible : "
                << exception.what()
                << std::endl;
            socket_error_reported_ = true;
        }

        return false;
    }
}

bool PtzController::send_preset(
    const CameraConfig& camera,
    const std::string& preset_token
) noexcept
{
    if (
        !camera.ptz_enabled ||
        camera.ptz_xaddr.empty() ||
        camera.ptz_profile_token.empty() ||
        preset_token.empty()
    ) {
        return false;
    }

    try {
        const std::string payload =
            std::string{"{\"action\":\"preset\",\"ptz_xaddr\":\""} +
            json_escape(
                camera.ptz_xaddr
            ) +
            "\",\"profile_token\":\"" +
            json_escape(
                camera.ptz_profile_token
            ) +
            "\",\"preset_token\":\"" +
            json_escape(
                preset_token
            ) +
            "\"}";

        return send_payload(payload);

    } catch (const std::exception& exception) {
        if (!socket_error_reported_) {
            std::cerr
                << "Preset PTZ indisponible : "
                << exception.what()
                << std::endl;
            socket_error_reported_ = true;
        }

        return false;
    }
}

} // namespace pidecoder
