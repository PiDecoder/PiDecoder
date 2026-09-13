#include "pidecoder/Application.hpp"
#include "pidecoder/Config.hpp"
#include "pidecoder/Layout.hpp"
#include "pidecoder/Version.hpp"

#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>
#include <utility>

int main(
    int argc,
    char* argv[]
)
{
    const std::string config_path =
        argc >= 2
            ? argv[1]
            : "config/cameras.json";

    try {
        auto cameras =
            pidecoder::Config::load(
                config_path
            );

        auto layout =
            pidecoder::LayoutStore::load(
                "config/layout.json",
                cameras.size()
            );

        pidecoder::Application app{
            std::move(cameras),
            std::move(layout)
        };

        return app.run();

    } catch (
        const std::exception& exception
    ) {
        std::cerr
            << "PiDecoder v"
            << PIDECODER_VERSION_STRING
            << "\nErreur : "
            << exception.what()
            << "\n";

        return EXIT_FAILURE;
    }
}
