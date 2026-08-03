#include "pidecoder/Renderer.hpp"

#include <SDL2/SDL_opengl.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cmath>
#include <string>

namespace pidecoder {

namespace {

/*
 * Police 3x5 minimaliste destinée uniquement à l'indicateur de zoom.
 * Chaque bit représente un pixel logique.
 */
constexpr std::array<
    std::array<int, 5>,
    10
> digit_rows{{
    {{0b111, 0b101, 0b101, 0b101, 0b111}},
    {{0b010, 0b110, 0b010, 0b010, 0b111}},
    {{0b111, 0b001, 0b111, 0b100, 0b111}},
    {{0b111, 0b001, 0b111, 0b001, 0b111}},
    {{0b101, 0b101, 0b111, 0b001, 0b001}},
    {{0b111, 0b100, 0b111, 0b001, 0b111}},
    {{0b111, 0b100, 0b111, 0b101, 0b111}},
    {{0b111, 0b001, 0b001, 0b001, 0b001}},
    {{0b111, 0b101, 0b111, 0b101, 0b111}},
    {{0b111, 0b101, 0b111, 0b001, 0b111}}
}};

using Glyph = std::array<std::uint8_t, 7>;

Glyph glyph_for(const char raw_character)
{
    const unsigned char value =
        static_cast<unsigned char>(raw_character);

    if (value >= 0x80U) {
        return {{0b01110, 0b10001, 0b00010, 0b00100, 0b00100, 0b00000, 0b00100}};
    }

    const char character =
        static_cast<char>(
            std::toupper(value)
        );

    switch (character) {
        case 'A': return {{0b01110,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}};
        case 'B': return {{0b11110,0b10001,0b10001,0b11110,0b10001,0b10001,0b11110}};
        case 'C': return {{0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01111}};
        case 'D': return {{0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110}};
        case 'E': return {{0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b11111}};
        case 'F': return {{0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b10000}};
        case 'G': return {{0b01111,0b10000,0b10000,0b10111,0b10001,0b10001,0b01111}};
        case 'H': return {{0b10001,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}};
        case 'I': return {{0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b11111}};
        case 'J': return {{0b00111,0b00010,0b00010,0b00010,0b10010,0b10010,0b01100}};
        case 'K': return {{0b10001,0b10010,0b10100,0b11000,0b10100,0b10010,0b10001}};
        case 'L': return {{0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b11111}};
        case 'M': return {{0b10001,0b11011,0b10101,0b10101,0b10001,0b10001,0b10001}};
        case 'N': return {{0b10001,0b11001,0b10101,0b10011,0b10001,0b10001,0b10001}};
        case 'O': return {{0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}};
        case 'P': return {{0b11110,0b10001,0b10001,0b11110,0b10000,0b10000,0b10000}};
        case 'Q': return {{0b01110,0b10001,0b10001,0b10001,0b10101,0b10010,0b01101}};
        case 'R': return {{0b11110,0b10001,0b10001,0b11110,0b10100,0b10010,0b10001}};
        case 'S': return {{0b01111,0b10000,0b10000,0b01110,0b00001,0b00001,0b11110}};
        case 'T': return {{0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100}};
        case 'U': return {{0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}};
        case 'V': return {{0b10001,0b10001,0b10001,0b10001,0b10001,0b01010,0b00100}};
        case 'W': return {{0b10001,0b10001,0b10001,0b10101,0b10101,0b10101,0b01010}};
        case 'X': return {{0b10001,0b10001,0b01010,0b00100,0b01010,0b10001,0b10001}};
        case 'Y': return {{0b10001,0b10001,0b01010,0b00100,0b00100,0b00100,0b00100}};
        case 'Z': return {{0b11111,0b00001,0b00010,0b00100,0b01000,0b10000,0b11111}};
        case '0': return {{0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110}};
        case '1': return {{0b00100,0b01100,0b00100,0b00100,0b00100,0b00100,0b01110}};
        case '2': return {{0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111}};
        case '3': return {{0b11110,0b00001,0b00001,0b01110,0b00001,0b00001,0b11110}};
        case '4': return {{0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010}};
        case '5': return {{0b11111,0b10000,0b10000,0b11110,0b00001,0b00001,0b11110}};
        case '6': return {{0b01110,0b10000,0b10000,0b11110,0b10001,0b10001,0b01110}};
        case '7': return {{0b11111,0b00001,0b00010,0b00100,0b01000,0b01000,0b01000}};
        case '8': return {{0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110}};
        case '9': return {{0b01110,0b10001,0b10001,0b01111,0b00001,0b00001,0b01110}};
        case '-': return {{0b00000,0b00000,0b00000,0b11111,0b00000,0b00000,0b00000}};
        case '_': return {{0b00000,0b00000,0b00000,0b00000,0b00000,0b00000,0b11111}};
        case '.': return {{0b00000,0b00000,0b00000,0b00000,0b00000,0b00110,0b00110}};
        case ':': return {{0b00000,0b00110,0b00110,0b00000,0b00110,0b00110,0b00000}};
        case '/': return {{0b00001,0b00010,0b00010,0b00100,0b01000,0b01000,0b10000}};
        case ' ': return {{0,0,0,0,0,0,0}};
        default: return {{0b01110,0b10001,0b00010,0b00100,0b00100,0b00000,0b00100}};
    }
}

} // namespace

Renderer::Renderer(
    Window& window
)
    : window_(window)
{
}

void Renderer::clear(
    const int width,
    const int height
)
{
    window_.make_current();

    glBindFramebuffer(
        GL_FRAMEBUFFER,
        0
    );

    glViewport(
        0,
        0,
        width,
        height
    );

    glClearColor(
        0.0F,
        0.0F,
        0.0F,
        1.0F
    );

    glClear(
        GL_COLOR_BUFFER_BIT
    );
}

void Renderer::render(
    const std::vector<
        std::unique_ptr<Player>
    >& players,
    const LayoutConfig& layout
)
{
    const int width =
        window_.drawable_width();

    const int height =
        window_.drawable_height();

    if (
        width <= 0 ||
        height <= 0
    ) {
        return;
    }

    clear(
        width,
        height
    );

    const auto rectangles =
        grid_.calculate(
            players.size(),
            width,
            height,
            layout
        );

    for (
        std::size_t index = 0;
        index < players.size();
        ++index
    ) {
        players[index]->render(
            rectangles[index],
            width,
            height
        );

        if (
            players[index]
                ->error_marker_visible()
        ) {
            draw_error_marker(
                rectangles[index],
                height
            );
        }
    }

    window_.swap_buffers();
}

void Renderer::render_focus(
    Player& player,
    const double zoom,
    const double center_x,
    const double center_y,
    const bool show_zoom_indicator,
    const bool ptz_available,
    const bool show_ptz_overlay,
    const PtzCommand active_ptz_command,
    const std::vector<PtzPreset>& presets,
    const bool preset_menu_open
)
{
    const int width =
        window_.drawable_width();

    const int height =
        window_.drawable_height();

    if (
        width <= 0 ||
        height <= 0
    ) {
        return;
    }

    clear(
        width,
        height
    );

    const Rect target{
        0,
        0,
        width,
        height
    };

    player.render_inspected(
        target,
        width,
        height,
        zoom,
        center_x,
        center_y
    );

    if (
        player.error_marker_visible()
    ) {
        draw_error_marker(
            target,
            height
        );
    }

    if (show_zoom_indicator) {
        const int percent =
            static_cast<int>(
                std::lround(
                    zoom * 100.0
                )
            );

        draw_zoom_indicator(
            percent,
            width,
            height
        );
    }

    if (
        ptz_available &&
        show_ptz_overlay
    ) {
        draw_ptz_overlay(
            width,
            height,
            active_ptz_command,
            presets,
            preset_menu_open
        );
    }

    window_.swap_buffers();
}

std::array<Renderer::PtzButton, 7>
Renderer::ptz_buttons(
    const int canvas_width,
    const int canvas_height
) const
{
    const int shortest =
        std::min(
            canvas_width,
            canvas_height
        );

    const int button_size =
        std::clamp(
            shortest / 16,
            34,
            46
        );

    const int gap =
        std::clamp(
            button_size / 8,
            4,
            7
        );

    const int margin =
        std::clamp(
            button_size / 3,
            12,
            18
        );

    const int left =
        std::max(
            margin,
            canvas_width -
                margin -
                3 * button_size -
                2 * gap
        );

    const int top =
        std::max(
            margin,
            canvas_height -
                margin -
                4 * button_size -
                3 * gap
        );

    const auto rectangle =
        [&](
            const int column,
            const int row
        ) {
            return Rect{
                left +
                    column *
                    (button_size + gap),
                top +
                    row *
                    (button_size + gap),
                button_size,
                button_size
            };
        };

    return std::array<PtzButton, 7>{{
        {PtzCommand::Up, rectangle(1, 0)},
        {PtzCommand::Left, rectangle(0, 1)},
        {PtzCommand::Stop, rectangle(1, 1)},
        {PtzCommand::Right, rectangle(2, 1)},
        {PtzCommand::Down, rectangle(1, 2)},
        {PtzCommand::ZoomOut, rectangle(0, 3)},
        {PtzCommand::ZoomIn, rectangle(2, 3)},
    }};
}

Rect Renderer::ptz_preset_selector(
    const int canvas_width,
    const int canvas_height
) const
{
    const auto buttons =
        ptz_buttons(
            canvas_width,
            canvas_height
        );

    const int gap =
        std::max(
            4,
            buttons[0].rectangle.width / 8
        );

    const int height =
        std::max(
            26,
            buttons[0].rectangle.height * 3 / 4
        );

    const int left =
        buttons[1].rectangle.x;

    const int width =
        buttons[3].rectangle.x +
        buttons[3].rectangle.width -
        left;

    return Rect{
        left,
        std::max(
            8,
            buttons[0].rectangle.y -
                gap -
                height
        ),
        width,
        height
    };
}

std::vector<Rect>
Renderer::ptz_preset_items(
    const int canvas_width,
    const int canvas_height,
    const std::size_t preset_count
) const
{
    std::vector<Rect> rectangles;

    if (preset_count == 0U) {
        return rectangles;
    }

    const Rect selector =
        ptz_preset_selector(
            canvas_width,
            canvas_height
        );

    const int gap = 4;
    const int margin = 8;
    const int item_height =
        std::max(
            26,
            selector.height
        );

    const int available =
        std::max(
            0,
            selector.y -
                margin -
                gap
        );

    const int fitting =
        std::max(
            0,
            (available + gap) /
            (item_height + gap)
        );

    const std::size_t visible_count =
        std::min(
            preset_count,
            std::min<std::size_t>(
                10U,
                static_cast<std::size_t>(
                    fitting
                )
            )
        );

    if (visible_count == 0U) {
        return rectangles;
    }

    rectangles.reserve(visible_count);

    const int total_height =
        static_cast<int>(visible_count) *
            item_height +
        (
            static_cast<int>(visible_count) - 1
        ) *
            gap;

    const int top =
        selector.y -
        gap -
        total_height;

    for (
        std::size_t index = 0;
        index < visible_count;
        ++index
    ) {
        rectangles.push_back(
            Rect{
                selector.x,
                top +
                    static_cast<int>(index) *
                    (item_height + gap),
                selector.width,
                item_height
            }
        );
    }

    return rectangles;
}

std::optional<PtzCommand>
Renderer::ptz_command_at(
    const int logical_x,
    const int logical_y
) const noexcept
{
    int logical_width = 0;
    int logical_height = 0;

    SDL_GetWindowSize(
        window_.native_handle(),
        &logical_width,
        &logical_height
    );

    const int drawable_width =
        window_.drawable_width();

    const int drawable_height =
        window_.drawable_height();

    if (
        logical_width <= 0 ||
        logical_height <= 0 ||
        drawable_width <= 0 ||
        drawable_height <= 0
    ) {
        return std::nullopt;
    }

    const int x =
        logical_x *
        drawable_width /
        logical_width;

    const int y =
        logical_y *
        drawable_height /
        logical_height;

    for (
        const PtzButton& button :
        ptz_buttons(
            drawable_width,
            drawable_height
        )
    ) {
        const Rect& rectangle =
            button.rectangle;

        if (
            x >= rectangle.x &&
            x < rectangle.x + rectangle.width &&
            y >= rectangle.y &&
            y < rectangle.y + rectangle.height
        ) {
            return button.command;
        }
    }

    return std::nullopt;
}

std::optional<Renderer::PtzPresetHit>
Renderer::ptz_preset_hit_at(
    const int logical_x,
    const int logical_y,
    const std::size_t preset_count,
    const bool menu_open
) const noexcept
{
    if (preset_count == 0U) {
        return std::nullopt;
    }

    int logical_width = 0;
    int logical_height = 0;

    SDL_GetWindowSize(
        window_.native_handle(),
        &logical_width,
        &logical_height
    );

    const int drawable_width =
        window_.drawable_width();

    const int drawable_height =
        window_.drawable_height();

    if (
        logical_width <= 0 ||
        logical_height <= 0 ||
        drawable_width <= 0 ||
        drawable_height <= 0
    ) {
        return std::nullopt;
    }

    const int x =
        logical_x *
        drawable_width /
        logical_width;

    const int y =
        logical_y *
        drawable_height /
        logical_height;

    const auto contains =
        [&](const Rect& rectangle) {
            return (
                x >= rectangle.x &&
                x < rectangle.x + rectangle.width &&
                y >= rectangle.y &&
                y < rectangle.y + rectangle.height
            );
        };

    if (
        contains(
            ptz_preset_selector(
                drawable_width,
                drawable_height
            )
        )
    ) {
        return PtzPresetHit{
            true,
            0U
        };
    }

    if (!menu_open) {
        return std::nullopt;
    }

    const auto items =
        ptz_preset_items(
            drawable_width,
            drawable_height,
            preset_count
        );

    for (
        std::size_t index = 0;
        index < items.size();
        ++index
    ) {
        if (contains(items[index])) {
            return PtzPresetHit{
                false,
                index
            };
        }
    }

    return std::nullopt;
}

void Renderer::draw_ptz_overlay(
    const int canvas_width,
    const int canvas_height,
    const PtzCommand active_command,
    const std::vector<PtzPreset>& presets,
    const bool preset_menu_open
)
{
    for (
        const PtzButton& button :
        ptz_buttons(
            canvas_width,
            canvas_height
        )
    ) {
        const bool active =
            button.command ==
            active_command;

        const Rect& rectangle =
            button.rectangle;

        fill_ui_rect(
            rectangle.x,
            rectangle.y,
            rectangle.width,
            rectangle.height,
            canvas_height,
            active ? 0.18F : 0.08F,
            active ? 0.38F : 0.10F,
            active ? 0.72F : 0.13F,
            1.0F
        );

        const int border =
            std::max(
                2,
                rectangle.width / 24
            );

        const float border_red =
            active ? 0.35F : 0.28F;

        const float border_green =
            active ? 0.62F : 0.33F;

        const float border_blue =
            active ? 1.0F : 0.40F;

        fill_ui_rect(
            rectangle.x,
            rectangle.y,
            rectangle.width,
            border,
            canvas_height,
            border_red,
            border_green,
            border_blue,
            1.0F
        );

        fill_ui_rect(
            rectangle.x,
            rectangle.y + rectangle.height - border,
            rectangle.width,
            border,
            canvas_height,
            border_red,
            border_green,
            border_blue,
            1.0F
        );

        fill_ui_rect(
            rectangle.x,
            rectangle.y,
            border,
            rectangle.height,
            canvas_height,
            border_red,
            border_green,
            border_blue,
            1.0F
        );

        fill_ui_rect(
            rectangle.x + rectangle.width - border,
            rectangle.y,
            border,
            rectangle.height,
            canvas_height,
            border_red,
            border_green,
            border_blue,
            1.0F
        );

        draw_ptz_icon(
            button.command,
            rectangle,
            canvas_height
        );
    }

    if (presets.empty()) {
        return;
    }

    const Rect selector =
        ptz_preset_selector(
            canvas_width,
            canvas_height
        );

    fill_ui_rect(
        selector.x,
        selector.y,
        selector.width,
        selector.height,
        canvas_height,
        preset_menu_open ? 0.18F : 0.08F,
        preset_menu_open ? 0.38F : 0.10F,
        preset_menu_open ? 0.72F : 0.13F,
        1.0F
    );

    draw_text(
        "PRESET",
        selector,
        canvas_height,
        selector.height
    );

    const int arrow_size =
        std::max(
            3,
            selector.height / 8
        );

    const int arrow_x =
        selector.x +
        selector.width -
        selector.height / 2;

    const int arrow_y =
        selector.y +
        selector.height / 2;

    for (int step = 0; step < 3; ++step) {
        const int offset =
            preset_menu_open
                ? 2 - step
                : step;

        fill_ui_rect(
            arrow_x -
                (step + 1) * arrow_size,
            arrow_y -
                arrow_size / 2 +
                offset * arrow_size,
            arrow_size,
            arrow_size,
            canvas_height,
            1.0F,
            1.0F,
            1.0F,
            1.0F
        );

        fill_ui_rect(
            arrow_x +
                step * arrow_size,
            arrow_y -
                arrow_size / 2 +
                offset * arrow_size,
            arrow_size,
            arrow_size,
            canvas_height,
            1.0F,
            1.0F,
            1.0F,
            1.0F
        );
    }

    if (!preset_menu_open) {
        return;
    }

    const auto items =
        ptz_preset_items(
            canvas_width,
            canvas_height,
            presets.size()
        );

    for (
        std::size_t index = 0;
        index < items.size();
        ++index
    ) {
        const Rect& item =
            items[index];

        fill_ui_rect(
            item.x,
            item.y,
            item.width,
            item.height,
            canvas_height,
            0.07F,
            0.09F,
            0.12F,
            1.0F
        );

        const std::string label =
            presets[index].name.empty()
                ? presets[index].token
                : presets[index].name;

        draw_text(
            label,
            item,
            canvas_height
        );
    }
}

void Renderer::draw_ptz_icon(
    const PtzCommand command,
    const Rect& rectangle,
    const int canvas_height
)
{
    const int thickness =
        std::max(
            2,
            rectangle.width / 14
        );

    const int center_x =
        rectangle.x +
        rectangle.width / 2;

    const int center_y =
        rectangle.y +
        rectangle.height / 2;

    const int arm =
        std::max(
            thickness * 3,
            rectangle.width / 5
        );

    const auto draw =
        [&](
            const int x,
            const int y,
            const int width,
            const int height
        ) {
            fill_ui_rect(
                x,
                y,
                width,
                height,
                canvas_height,
                1.0F,
                1.0F,
                1.0F,
                1.0F
            );
        };

    if (command == PtzCommand::Stop) {
        const int size =
            std::max(
                thickness * 3,
                rectangle.width / 5
            );
        draw(
            center_x - size / 2,
            center_y - size / 2,
            size,
            size
        );
        return;
    }

    if (
        command == PtzCommand::ZoomIn ||
        command == PtzCommand::ZoomOut
    ) {
        draw(
            center_x - arm,
            center_y - thickness / 2,
            arm * 2,
            thickness
        );

        if (command == PtzCommand::ZoomIn) {
            draw(
                center_x - thickness / 2,
                center_y - arm,
                thickness,
                arm * 2
            );
        }

        return;
    }

    constexpr int steps = 4;

    for (int step = 0; step < steps; ++step) {
        if (
            command == PtzCommand::Left ||
            command == PtzCommand::Right
        ) {
            const int x =
                command == PtzCommand::Left
                    ? center_x - arm + step * thickness
                    : center_x + arm - (step + 1) * thickness;

            draw(
                x,
                center_y - (step + 1) * thickness,
                thickness,
                thickness
            );
            draw(
                x,
                center_y + step * thickness,
                thickness,
                thickness
            );
            continue;
        }

        if (
            command == PtzCommand::Up ||
            command == PtzCommand::Down
        ) {
            const int y =
                command == PtzCommand::Up
                    ? center_y - arm + step * thickness
                    : center_y + arm - (step + 1) * thickness;

            draw(
                center_x - (step + 1) * thickness,
                y,
                thickness,
                thickness
            );
            draw(
                center_x + step * thickness,
                y,
                thickness,
                thickness
            );
        }
    }
}

void Renderer::draw_text(
    const std::string& text,
    const Rect& rectangle,
    const int canvas_height,
    const int right_reserve
)
{
    std::string display_text;
    display_text.reserve(text.size());

    for (
        std::size_t index = 0;
        index < text.size();
        ++index
    ) {
        const unsigned char character =
            static_cast<unsigned char>(
                text[index]
            );

        if (character < 0x80U) {
            display_text.push_back(
                static_cast<char>(character)
            );
            continue;
        }

        if (
            character == 0xC3U &&
            index + 1U < text.size()
        ) {
            const unsigned char continuation =
                static_cast<unsigned char>(
                    text[index + 1U]
                );

            char replacement = '?';

            switch (continuation) {
                case 0x80U: case 0x81U: case 0x82U: case 0x83U:
                case 0x84U: case 0x85U: case 0xA0U: case 0xA1U:
                case 0xA2U: case 0xA3U: case 0xA4U: case 0xA5U:
                    replacement = 'A';
                    break;
                case 0x87U: case 0xA7U:
                    replacement = 'C';
                    break;
                case 0x88U: case 0x89U: case 0x8AU: case 0x8BU:
                case 0xA8U: case 0xA9U: case 0xAAU: case 0xABU:
                    replacement = 'E';
                    break;
                case 0x8CU: case 0x8DU: case 0x8EU: case 0x8FU:
                case 0xACU: case 0xADU: case 0xAEU: case 0xAFU:
                    replacement = 'I';
                    break;
                case 0x91U: case 0xB1U:
                    replacement = 'N';
                    break;
                case 0x92U: case 0x93U: case 0x94U: case 0x95U:
                case 0x96U: case 0xB2U: case 0xB3U: case 0xB4U:
                case 0xB5U: case 0xB6U:
                    replacement = 'O';
                    break;
                case 0x99U: case 0x9AU: case 0x9BU: case 0x9CU:
                case 0xB9U: case 0xBAU: case 0xBBU: case 0xBCU:
                    replacement = 'U';
                    break;
                case 0x9DU: case 0xBDU: case 0xBFU:
                    replacement = 'Y';
                    break;
                default:
                    break;
            }

            display_text.push_back(replacement);
            ++index;
            continue;
        }

        display_text.push_back('?');
    }

    const int scale =
        rectangle.height >= 32
            ? 2
            : 1;

    const int glyph_width =
        5 * scale;

    const int glyph_height =
        7 * scale;

    const int spacing =
        scale;

    const int padding =
        std::max(
            6,
            rectangle.height / 5
        );

    const int available_width =
        std::max(
            0,
            rectangle.width -
                padding * 2 -
                right_reserve
        );

    const int character_width =
        glyph_width + spacing;

    const std::size_t maximum_characters =
        character_width > 0
            ? static_cast<std::size_t>(
                available_width /
                character_width
            )
            : 0U;

    const std::size_t character_count =
        std::min(
            display_text.size(),
            maximum_characters
        );

    int cursor_x =
        rectangle.x +
        padding;

    const int cursor_y =
        rectangle.y +
        std::max(
            0,
            (
                rectangle.height -
                glyph_height
            ) /
            2
        );

    for (
        std::size_t index = 0;
        index < character_count;
        ++index
    ) {
        const Glyph glyph =
            glyph_for(display_text[index]);

        for (int row = 0; row < 7; ++row) {
            for (int column = 0; column < 5; ++column) {
                const std::uint8_t bit =
                    static_cast<std::uint8_t>(
                        1U <<
                        static_cast<unsigned int>(
                            4 - column
                        )
                    );

                if (
                    (
                        glyph[
                            static_cast<std::size_t>(row)
                        ] &
                        bit
                    ) == 0U
                ) {
                    continue;
                }

                fill_ui_rect(
                    cursor_x +
                        column * scale,
                    cursor_y +
                        row * scale,
                    scale,
                    scale,
                    canvas_height,
                    1.0F,
                    1.0F,
                    1.0F,
                    1.0F
                );
            }
        }

        cursor_x +=
            character_width;
    }
}

void Renderer::fill_ui_rect(
    const int x,
    const int y,
    const int width,
    const int height,
    const int canvas_height,
    const float red,
    const float green,
    const float blue,
    const float alpha
)
{
    if (
        width <= 0 ||
        height <= 0
    ) {
        return;
    }

    glEnable(
        GL_SCISSOR_TEST
    );

    glScissor(
        x,
        canvas_height -
            y -
            height,
        width,
        height
    );

    glClearColor(
        red,
        green,
        blue,
        alpha
    );

    glClear(
        GL_COLOR_BUFFER_BIT
    );

    glDisable(
        GL_SCISSOR_TEST
    );
}

void Renderer::draw_digit(
    const int digit,
    const int x,
    const int y,
    const int scale,
    const int canvas_height
)
{
    if (
        digit < 0 ||
        digit > 9
    ) {
        return;
    }

    for (
        int row = 0;
        row < 5;
        ++row
    ) {
        for (
            int column = 0;
            column < 3;
            ++column
        ) {
            const int bit =
                1 <<
                (
                    2 -
                    column
                );

            if (
                (
                    digit_rows[
                        static_cast<std::size_t>(
                            digit
                        )
                    ][
                        static_cast<std::size_t>(
                            row
                        )
                    ] &
                    bit
                ) == 0
            ) {
                continue;
            }

            fill_ui_rect(
                x +
                    column *
                    scale,
                y +
                    row *
                    scale,
                scale,
                scale,
                canvas_height,
                1.0F,
                1.0F,
                1.0F,
                1.0F
            );
        }
    }
}

void Renderer::draw_zoom_indicator(
    const int percent,
    const int canvas_width,
    const int canvas_height
)
{
    const std::string text =
        std::to_string(
            percent
        );

    const int scale = 4;
    const int digit_width =
        3 * scale;

    const int spacing =
        scale;

    const int percent_width =
        3 * scale;

    const int content_width =
        static_cast<int>(
            text.size()
        ) *
        digit_width +
        std::max(
            0,
            static_cast<int>(
                text.size()
            ) - 1
        ) *
        spacing +
        spacing +
        percent_width;

    const int content_height =
        5 * scale;

    const int padding = 10;

    const int box_width =
        content_width +
        padding * 2;

    const int box_height =
        content_height +
        padding * 2;

    const int box_x =
        std::max(
            12,
            canvas_width -
                box_width -
                18
        );

    const int box_y =
        18;

    fill_ui_rect(
        box_x,
        box_y,
        box_width,
        box_height,
        canvas_height,
        0.08F,
        0.08F,
        0.08F,
        1.0F
    );

    int cursor_x =
        box_x +
        padding;

    const int cursor_y =
        box_y +
        padding;

    for (
        const char character :
        text
    ) {
        draw_digit(
            character - '0',
            cursor_x,
            cursor_y,
            scale,
            canvas_height
        );

        cursor_x +=
            digit_width +
            spacing;
    }

    /*
     * Signe % en police pixel :
     * point haut-gauche, diagonale et point bas-droit.
     */
    fill_ui_rect(
        cursor_x,
        cursor_y,
        scale,
        scale,
        canvas_height,
        1.0F,
        1.0F,
        1.0F,
        1.0F
    );

    fill_ui_rect(
        cursor_x +
            2 * scale,
        cursor_y +
            4 * scale,
        scale,
        scale,
        canvas_height,
        1.0F,
        1.0F,
        1.0F,
        1.0F
    );

    for (
        int index = 0;
        index < 4;
        ++index
    ) {
        fill_ui_rect(
            cursor_x +
                (
                    2 -
                    index / 2
                ) *
                scale,
            cursor_y +
                (
                    1 +
                    index
                ) *
                scale,
            scale,
            scale,
            canvas_height,
            1.0F,
            1.0F,
            1.0F,
            1.0F
        );
    }
}

void Renderer::draw_error_marker(
    const Rect& target,
    const int canvas_height
)
{
    const int marker_size =
        std::max(
            24,
            std::min(
                target.width,
                target.height
            ) / 8
        );

    const int margin = 12;

    const int left =
        target.x +
        target.width -
        marker_size -
        margin;

    const int right =
        target.x +
        target.width -
        margin;

    const int top_from_ui =
        target.y +
        margin;

    const int bottom_gl =
        canvas_height -
        (
            top_from_ui +
            marker_size
        );

    const int top_gl =
        canvas_height -
        top_from_ui;

    glEnable(
        GL_SCISSOR_TEST
    );

    glScissor(
        left,
        bottom_gl,
        marker_size,
        marker_size
    );

    glClearColor(
        0.75F,
        0.0F,
        0.0F,
        1.0F
    );

    glClear(
        GL_COLOR_BUFFER_BIT
    );

    glDisable(
        GL_SCISSOR_TEST
    );

    glEnable(
        GL_SCISSOR_TEST
    );

    const int thickness =
        std::max(
            3,
            marker_size / 10
        );

    for (
        int offset = 0;
        offset < marker_size;
        ++offset
    ) {
        const int x1 =
            left +
            offset;

        const int y1 =
            bottom_gl +
            offset;

        glScissor(
            x1,
            y1,
            thickness,
            thickness
        );

        glClearColor(
            1.0F,
            1.0F,
            1.0F,
            1.0F
        );

        glClear(
            GL_COLOR_BUFFER_BIT
        );

        const int x2 =
            left +
            offset;

        const int y2 =
            top_gl -
            offset -
            thickness;

        glScissor(
            x2,
            y2,
            thickness,
            thickness
        );

        glClear(
            GL_COLOR_BUFFER_BIT
        );
    }

    glDisable(
        GL_SCISSOR_TEST
    );

    (void) right;
}

} // namespace pidecoder
