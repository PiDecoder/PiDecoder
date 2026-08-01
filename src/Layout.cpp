#include "pidecoder/Layout.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <unordered_set>
#include <utility>
#include <vector>

namespace pidecoder {

namespace {

bool fits(
    const LayoutPlacement& placement,
    const int columns,
    const int rows
)
{
    return (
        placement.x >= 0 &&
        placement.y >= 0 &&
        placement.width >= 1 &&
        placement.height >= 1 &&
        placement.x + placement.width <= columns &&
        placement.y + placement.height <= rows
    );
}

bool overlaps(
    const LayoutPlacement& left,
    const LayoutPlacement& right
)
{
    return !(
        left.x + left.width <= right.x ||
        right.x + right.width <= left.x ||
        left.y + left.height <= right.y ||
        right.y + right.height <= left.y
    );
}

LayoutPlacement first_free(
    const std::size_t camera,
    const int columns,
    const int rows,
    const std::vector<LayoutPlacement>& occupied
)
{
    for (int y = 0; y < rows; ++y) {
        for (int x = 0; x < columns; ++x) {
            LayoutPlacement candidate{
                camera,
                x,
                y,
                1,
                1
            };

            bool collision = false;

            for (const auto& other : occupied) {
                if (overlaps(candidate, other)) {
                    collision = true;
                    break;
                }
            }

            if (!collision) {
                return candidate;
            }
        }
    }

    // The web interface normally prevents this case. Keeping the camera in
    // a deterministic virtual position is safer than dropping it silently.
    return LayoutPlacement{
        camera,
        static_cast<int>(camera % static_cast<std::size_t>(columns)),
        static_cast<int>(camera / static_cast<std::size_t>(columns)),
        1,
        1
    };
}

LayoutConfig make_default(
    const std::size_t camera_count
)
{
    LayoutConfig layout;

    for (
        std::size_t index = 0;
        index < camera_count;
        ++index
    ) {
        layout.camera_order.push_back(index);

        layout.placements.push_back(
            LayoutPlacement{
                index,
                static_cast<int>(
                    index %
                    static_cast<std::size_t>(
                        layout.columns
                    )
                ),
                static_cast<int>(
                    index /
                    static_cast<std::size_t>(
                        layout.columns
                    )
                ),
                1,
                1
            }
        );
    }

    return layout;
}

} // namespace

LayoutConfig LayoutStore::load(
    const std::string& path,
    const std::size_t camera_count
)
{
    if (!std::filesystem::exists(path)) {
        LayoutConfig layout =
            make_default(camera_count);

        normalize(layout, camera_count);
        save(path, layout);
        return layout;
    }

    std::ifstream input{path};

    if (!input) {
        throw std::runtime_error(
            "Impossible d'ouvrir le layout : " +
            path
        );
    }

    nlohmann::json document;
    input >> document;

    LayoutConfig layout;

    layout.columns =
        document.value("columns", 3);

    layout.rows =
        document.value("rows", 3);

    layout.fullscreen_on_start =
        document.value(
            "fullscreen_on_start",
            false
        );

    if (
        document.contains("camera_order") &&
        document["camera_order"].is_array()
    ) {
        for (
            const auto& value :
            document["camera_order"]
        ) {
            if (value.is_number_unsigned()) {
                layout.camera_order.push_back(
                    value.get<std::size_t>()
                );
            }
        }
    }

    if (
        document.contains("placements") &&
        document["placements"].is_array()
    ) {
        for (
            const auto& item :
            document["placements"]
        ) {
            if (!item.is_object()) {
                continue;
            }

            LayoutPlacement placement;

            placement.camera =
                item.value(
                    "camera",
                    std::size_t{0}
                );

            placement.x =
                item.value("x", 0);

            placement.y =
                item.value("y", 0);

            placement.width =
                item.value("width", 1);

            placement.height =
                item.value("height", 1);

            layout.placements.push_back(
                placement
            );
        }
    }

    normalize(layout, camera_count);
    save(path, layout);

    return layout;
}

void LayoutStore::save(
    const std::string& path,
    const LayoutConfig& layout
)
{
    const std::filesystem::path target{path};

    if (!target.parent_path().empty()) {
        std::filesystem::create_directories(
            target.parent_path()
        );
    }

    nlohmann::json placements =
        nlohmann::json::array();

    for (
        const LayoutPlacement& placement :
        layout.placements
    ) {
        placements.push_back(
            {
                {"camera", placement.camera},
                {"x", placement.x},
                {"y", placement.y},
                {"width", placement.width},
                {"height", placement.height}
            }
        );
    }

    nlohmann::json document{
        {"columns", layout.columns},
        {"rows", layout.rows},
        {
            "fullscreen_on_start",
            layout.fullscreen_on_start
        },
        {"camera_order", layout.camera_order},
        {"placements", placements}
    };

    const std::filesystem::path temp =
        target.string() + ".tmp";

    {
        std::ofstream output{temp};

        if (!output) {
            throw std::runtime_error(
                "Impossible d'écrire le layout : " +
                temp.string()
            );
        }

        output
            << document.dump(2)
            << '\n';
    }

    if (std::filesystem::exists(target)) {
        std::filesystem::remove(target);
    }

    std::filesystem::rename(
        temp,
        target
    );
}

void LayoutStore::normalize(
    LayoutConfig& layout,
    const std::size_t camera_count
)
{
    layout.columns =
        std::clamp(layout.columns, 1, 9);

    layout.rows =
        std::clamp(layout.rows, 1, 9);

    std::vector<std::size_t> normalized_order;
    std::unordered_set<std::size_t> seen_order;

    for (
        const std::size_t index :
        layout.camera_order
    ) {
        if (
            index < camera_count &&
            seen_order.insert(index).second
        ) {
            normalized_order.push_back(index);
        }
    }

    for (
        std::size_t index = 0;
        index < camera_count;
        ++index
    ) {
        if (seen_order.insert(index).second) {
            normalized_order.push_back(index);
        }
    }

    layout.camera_order =
        std::move(normalized_order);

    std::vector<LayoutPlacement> normalized;
    std::unordered_set<std::size_t> seen_placements;

    for (
        LayoutPlacement placement :
        layout.placements
    ) {
        if (
            placement.camera >= camera_count ||
            !seen_placements.insert(
                placement.camera
            ).second
        ) {
            continue;
        }

        placement.width =
            std::clamp(
                placement.width,
                1,
                layout.columns
            );

        placement.height =
            std::clamp(
                placement.height,
                1,
                layout.rows
            );

        placement.x =
            std::clamp(
                placement.x,
                0,
                layout.columns - 1
            );

        placement.y =
            std::clamp(
                placement.y,
                0,
                layout.rows - 1
            );

        if (
            placement.x + placement.width >
            layout.columns
        ) {
            placement.x =
                layout.columns -
                placement.width;
        }

        if (
            placement.y + placement.height >
            layout.rows
        ) {
            placement.y =
                layout.rows -
                placement.height;
        }

        bool collision = false;

        for (const auto& other : normalized) {
            if (overlaps(placement, other)) {
                collision = true;
                break;
            }
        }

        if (!fits(
                placement,
                layout.columns,
                layout.rows
            ) || collision) {
            placement =
                first_free(
                    placement.camera,
                    layout.columns,
                    layout.rows,
                    normalized
                );
        }

        normalized.push_back(
            placement
        );
    }

    for (
        std::size_t camera = 0;
        camera < camera_count;
        ++camera
    ) {
        if (
            seen_placements.insert(camera).second
        ) {
            normalized.push_back(
                first_free(
                    camera,
                    layout.columns,
                    layout.rows,
                    normalized
                )
            );
        }
    }

    std::sort(
        normalized.begin(),
        normalized.end(),
        [](
            const LayoutPlacement& left,
            const LayoutPlacement& right
        ) {
            return left.camera < right.camera;
        }
    );

    layout.placements =
        std::move(normalized);
}

} // namespace pidecoder
