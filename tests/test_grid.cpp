#include "test_harness.hpp"

#include "pidecoder/Grid.hpp"

#include <cstddef>

namespace pidecoder::test {

void run_grid_tests(TestResult& result)
{
    const Grid grid;

    begin_suite(result, "Grid::calculate (mode automatique)");

    {
        // count == 0 : toujours vide.
        const auto rects = grid.calculate(0, 1920, 1080);
        PD_CHECK(result, rects.empty());
    }

    {
        // Canvas invalide (largeur nulle) : vide, pas de division par zéro.
        const auto rects = grid.calculate(4, 0, 1080);
        PD_CHECK(result, rects.empty());
    }

    {
        // Canvas invalide (hauteur négative) : vide.
        const auto rects = grid.calculate(4, 1920, -10);
        PD_CHECK(result, rects.empty());
    }

    {
        // Une seule caméra : plein écran.
        const auto rects = grid.calculate(1, 1920, 1080);
        PD_CHECK_EQ(result, rects.size(), std::size_t{1});
        PD_CHECK_EQ(result, rects[0].x, 0);
        PD_CHECK_EQ(result, rects[0].y, 0);
        PD_CHECK_EQ(result, rects[0].width, 1920);
        PD_CHECK_EQ(result, rects[0].height, 1080);
    }

    {
        // 4 caméras, canvas divisible : grille 2x2 exacte, aucun reliquat.
        const auto rects = grid.calculate(4, 1920, 1080);
        PD_CHECK_EQ(result, rects.size(), std::size_t{4});

        PD_CHECK_EQ(result, rects[0].x, 0);
        PD_CHECK_EQ(result, rects[0].y, 0);
        PD_CHECK_EQ(result, rects[0].width, 960);
        PD_CHECK_EQ(result, rects[0].height, 540);

        PD_CHECK_EQ(result, rects[1].x, 960);
        PD_CHECK_EQ(result, rects[1].y, 0);
        PD_CHECK_EQ(result, rects[1].width, 960);
        PD_CHECK_EQ(result, rects[1].height, 540);

        PD_CHECK_EQ(result, rects[2].x, 0);
        PD_CHECK_EQ(result, rects[2].y, 540);

        PD_CHECK_EQ(result, rects[3].x, 960);
        PD_CHECK_EQ(result, rects[3].y, 540);
    }

    {
        // 3 caméras sur un canvas à dimensions impaires : colonnes=2,
        // lignes=2 (ceil(3/2)=2). La dernière colonne/ligne doit absorber
        // le reliquat de pixels plutôt que de laisser un trou.
        const auto rects = grid.calculate(3, 1921, 1081);
        PD_CHECK_EQ(result, rects.size(), std::size_t{3});

        // Les deux cellules du haut doivent couvrir toute la largeur, sans
        // trou ni recouvrement.
        PD_CHECK_EQ(result, rects[0].x, 0);
        PD_CHECK_EQ(result, rects[1].x, rects[0].width);
        PD_CHECK_EQ(result, rects[0].width + rects[1].width, 1921);

        // La caméra 2 est seule sur la deuxième ligne, mais l'algorithme ne
        // l'étire pas pour combler la colonne vide à côté : elle garde la
        // largeur de cellule normale de sa colonne (0). Seule la dernière
        // ligne/colonne absorbe le reliquat de pixels, pas les cellules
        // "orphelines" d'une ligne incomplète. On fige ce comportement réel
        // ici plutôt que le comportement "idéal" qu'on pourrait souhaiter.
        PD_CHECK_EQ(result, rects[2].x, 0);
        PD_CHECK_EQ(result, rects[2].width, rects[0].width);
        PD_CHECK_EQ(result, rects[2].y, rects[0].height);
        PD_CHECK_EQ(result, rects[2].y + rects[2].height, 1081);
    }

    {
        // 5 caméras : colonnes = ceil(sqrt(5)) = 3, lignes = ceil(5/3) = 2.
        // On vérifie l'agencement (3 sur la première ligne, 2 sur la
        // deuxième) et que tout reste dans les bornes du canvas.
        const auto rects = grid.calculate(5, 1920, 1080);
        PD_CHECK_EQ(result, rects.size(), std::size_t{5});

        PD_CHECK_EQ(result, rects[0].y, rects[1].y);
        PD_CHECK_EQ(result, rects[1].y, rects[2].y);
        PD_CHECK_EQ(result, rects[3].y, rects[4].y);
        PD_CHECK(result, rects[3].y > rects[0].y);

        for (const auto& rect : rects) {
            PD_CHECK(result, rect.x >= 0);
            PD_CHECK(result, rect.y >= 0);
            PD_CHECK(result, rect.width >= 1);
            PD_CHECK(result, rect.height >= 1);
            PD_CHECK(result, rect.x + rect.width <= 1920);
            PD_CHECK(result, rect.y + rect.height <= 1080);
        }
    }

    begin_suite(result, "Grid::calculate (mode disposition personnalisée)");

    {
        // count == 0 : vide même avec une disposition valide.
        const LayoutConfig layout{};
        const auto rects = grid.calculate(0, 1920, 1080, layout);
        PD_CHECK(result, rects.empty());
    }

    {
        // Disposition invalide (colonnes <= 0) : vide, pas de division par
        // zéro malgré le std::max(1, ...) interne côté "columns" local.
        LayoutConfig layout;
        layout.columns = 0;
        const auto rects = grid.calculate(2, 1920, 1080, layout);
        PD_CHECK(result, rects.empty());
    }

    {
        // Disposition explicite : une caméra occupant un bloc 2x1 doit
        // produire un rectangle deux fois plus large qu'une cellule simple,
        // positionné exactement sur la grille logique.
        LayoutConfig layout;
        layout.columns = 4;
        layout.rows = 2;
        layout.placements.push_back(
            LayoutPlacement{0, 0, 0, 2, 1}
        );
        layout.placements.push_back(
            LayoutPlacement{1, 2, 0, 1, 1}
        );

        const auto rects = grid.calculate(2, 1600, 800, layout);
        PD_CHECK_EQ(result, rects.size(), std::size_t{2});

        // Caméra 0 : colonnes [0,2) sur 4 -> x0=0, x1=800 (moitié du canvas).
        PD_CHECK_EQ(result, rects[0].x, 0);
        PD_CHECK_EQ(result, rects[0].y, 0);
        PD_CHECK_EQ(result, rects[0].width, 800);
        PD_CHECK_EQ(result, rects[0].height, 400);

        // Caméra 1 : colonne [2,3) sur 4 -> x0=2*1600/4=800, x1=3*1600/4=1200.
        PD_CHECK_EQ(result, rects[1].x, 800);
        PD_CHECK_EQ(result, rects[1].width, 400);
    }

    {
        // Caméra absente de layout.placements : repli sur une cellule 1x1
        // par défaut, positionnée selon son index (player_index % columns).
        LayoutConfig layout;
        layout.columns = 2;
        layout.rows = 2;
        // Aucun placement défini : les deux caméras retombent sur le calcul
        // par défaut (index 0 -> (0,0), index 1 -> (1,0)).

        const auto rects = grid.calculate(2, 1000, 1000, layout);
        PD_CHECK_EQ(result, rects.size(), std::size_t{2});

        PD_CHECK_EQ(result, rects[0].x, 0);
        PD_CHECK_EQ(result, rects[0].y, 0);

        PD_CHECK_EQ(result, rects[1].x, 500);
        PD_CHECK_EQ(result, rects[1].y, 0);
    }

    {
        // Garde-fou anti-largeur/hauteur nulle : une disposition
        // dégénérée (placement hors grille, x1 <= x0 après conversion en
        // pixels) doit quand même produire un rectangle d'au moins 1x1,
        // jamais un rectangle de taille nulle ou négative.
        LayoutConfig layout;
        layout.columns = 4;
        layout.rows = 4;
        layout.placements.push_back(
            LayoutPlacement{0, 10, 10, 1, 1}
        );

        const auto rects = grid.calculate(1, 400, 400, layout);
        PD_CHECK_EQ(result, rects.size(), std::size_t{1});
        PD_CHECK(result, rects[0].width >= 1);
        PD_CHECK(result, rects[0].height >= 1);
    }
}

} // namespace pidecoder::test
