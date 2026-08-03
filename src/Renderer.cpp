#include "pidecoder/Renderer.hpp"

#include <SDL2/SDL_opengl.h>

#include <algorithm>
#include <array>
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
    const PtzCommand active_ptz_command
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
            active_ptz_command
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

void Renderer::draw_ptz_overlay(
    const int canvas_width,
    const int canvas_height,
    const PtzCommand active_command
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
        std::max(
            12,
            canvas_height -
                box_height -
                18
        );

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
