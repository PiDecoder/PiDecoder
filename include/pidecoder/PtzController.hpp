#pragma once

#include "pidecoder/CameraConfig.hpp"

#include <string>

namespace pidecoder {

enum class PtzCommand {
    None,
    Up,
    Down,
    Left,
    Right,
    Stop,
    ZoomIn,
    ZoomOut,
};

class PtzController final {
public:
    explicit PtzController(
        std::string socket_path = "/run/pidecoder/ptz.sock"
    );

    PtzController(const PtzController&) = delete;
    PtzController& operator=(const PtzController&) = delete;

    PtzController(PtzController&&) = delete;
    PtzController& operator=(PtzController&&) = delete;

    ~PtzController();

    [[nodiscard]] bool send(
        const CameraConfig& camera,
        PtzCommand command
    ) noexcept;

    [[nodiscard]] bool send_preset(
        const CameraConfig& camera,
        const std::string& preset_token
    ) noexcept;

    [[nodiscard]] static const char* command_name(
        PtzCommand command
    ) noexcept;

private:
    [[nodiscard]] bool send_payload(
        const std::string& payload
    ) noexcept;

    std::string socket_path_;
    int socket_fd_{-1};
    bool socket_error_reported_{false};
};

} // namespace pidecoder
