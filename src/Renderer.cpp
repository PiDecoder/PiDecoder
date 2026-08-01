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
    const bool show_zoom_indicator
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

    window_.swap_buffers();
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
