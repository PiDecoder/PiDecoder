#include "pidecoder/RedactUrl.hpp"

namespace pidecoder {

std::string redact_credentials(const std::string& url)
{
    const auto scheme_end = url.find("://");

    if (scheme_end == std::string::npos) {
        return url;
    }

    const auto authority_start = scheme_end + 3;
    const auto path_start = url.find('/', authority_start);
    const auto search_end =
        path_start == std::string::npos ? url.size() : path_start;

    const auto at_position = url.find('@', authority_start);

    if (at_position == std::string::npos || at_position >= search_end) {
        return url;
    }

    return
        url.substr(0, authority_start) +
        "***:***" +
        url.substr(at_position);
}

} // namespace pidecoder
