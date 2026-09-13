#include "pidecoder/Grid.hpp"

#include <algorithm>
#include <cmath>

namespace pidecoder {

std::vector<Rect> Grid::calculate(
    const std::size_t count,
    const int canvas_width,
    const int canvas_height
) const
{
    if (
        count == 0 ||
        canvas_width <= 0 ||
        canvas_height <= 0
    ) {
        return {};
    }

    const double camera_count =
        static_cast<double>(count);

    const std::size_t columns =
        static_cast<std::size_t>(
            std::ceil(
                std::sqrt(camera_count)
            )
        );

    const std::size_t rows =
        static_cast<std::size_t>(
            std::ceil(
                camera_count /
                static_cast<double>(
                    columns
                )
            )
        );

    const int cell_width =
        canvas_width /
        static_cast<int>(columns);

    const int cell_height =
        canvas_height /
        static_cast<int>(rows);

    std::vector<Rect> output;
    output.reserve(count);

    for (
        std::size_t index = 0;
        index < count;
        ++index
    ) {
        const std::size_t row =
            index / columns;

        const std::size_t column =
            index % columns;

        const int x =
            static_cast<int>(column) *
            cell_width;

        const int y =
            static_cast<int>(row) *
            cell_height;

        output.push_back(
            {
                x,
                y,
                (
                    column + 1 == columns
                        ? canvas_width - x
                        : cell_width
                ),
                (
                    row + 1 == rows
                        ? canvas_height - y
                        : cell_height
                )
            }
        );
    }

    return output;
}

std::vector<Rect> Grid::calculate(
    const std::size_t count,
    const int canvas_width,
    const int canvas_height,
    const LayoutConfig& layout
) const
{
    if (
        count == 0 ||
        canvas_width <= 0 ||
        canvas_height <= 0 ||
        layout.columns <= 0 ||
        layout.rows <= 0
    ) {
        return {};
    }

    std::vector<Rect> output(
        count
    );

    const int columns =
        std::max(1, layout.columns);

    const int rows =
        std::max(1, layout.rows);

    for (
        std::size_t player_index = 0;
        player_index < count;
        ++player_index
    ) {
        LayoutPlacement placement{
            player_index,
            static_cast<int>(
                player_index %
                static_cast<std::size_t>(
                    columns
                )
            ),
            static_cast<int>(
                player_index /
                static_cast<std::size_t>(
                    columns
                )
            ),
            1,
            1
        };

        const auto match =
            std::find_if(
                layout.placements.begin(),
                layout.placements.end(),
                [player_index](
                    const LayoutPlacement& candidate
                ) {
                    return (
                        candidate.camera ==
                        player_index
                    );
                }
            );

        if (
            match !=
            layout.placements.end()
        ) {
            placement = *match;
        }

        const int x0 =
            placement.x *
            canvas_width /
            columns;

        const int y0 =
            placement.y *
            canvas_height /
            rows;

        const int x1 =
            (
                placement.x +
                placement.width
            ) *
            canvas_width /
            columns;

        const int y1 =
            (
                placement.y +
                placement.height
            ) *
            canvas_height /
            rows;

        output[player_index] =
            {
                x0,
                y0,
                std::max(1, x1 - x0),
                std::max(1, y1 - y0)
            };
    }

    return output;
}

} // namespace pidecoder
