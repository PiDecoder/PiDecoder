#include "test_harness.hpp"

#include "pidecoder/Layout.hpp"

#include <cstddef>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

namespace pidecoder::test {

namespace {

std::string temp_layout_path(const std::string& suffix)
{
    return (
        std::filesystem::temp_directory_path() /
        ("pidecoder-test-layout-" + suffix + ".json")
    ).string();
}

} // namespace

void run_layout_normalize_tests(TestResult& result)
{
    begin_suite(result, "LayoutStore::normalize (bornes et valeurs par défaut)");

    {
        // Configuration vide : les colonnes/lignes par défaut (3x3) sont
        // valides, et une place doit être créée pour chaque caméra.
        LayoutConfig layout;
        LayoutStore::normalize(layout, 4);

        PD_CHECK_EQ(result, layout.columns, 3);
        PD_CHECK_EQ(result, layout.rows, 3);
        PD_CHECK_EQ(result, layout.camera_order.size(), std::size_t{4});
        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{4});

        // Remplissage en balayage ligne par ligne à partir de (0,0).
        PD_CHECK_EQ(result, layout.placements[0].x, 0);
        PD_CHECK_EQ(result, layout.placements[0].y, 0);
        PD_CHECK_EQ(result, layout.placements[1].x, 1);
        PD_CHECK_EQ(result, layout.placements[1].y, 0);
        PD_CHECK_EQ(result, layout.placements[2].x, 2);
        PD_CHECK_EQ(result, layout.placements[2].y, 0);
        PD_CHECK_EQ(result, layout.placements[3].x, 0);
        PD_CHECK_EQ(result, layout.placements[3].y, 1);
    }

    {
        // columns/rows hors bornes [1,9] doivent être ramenées dans
        // l'intervalle plutôt que de produire une grille dégénérée.
        LayoutConfig layout;
        layout.columns = 20;
        layout.rows = 0;

        LayoutStore::normalize(layout, 1);

        PD_CHECK_EQ(result, layout.columns, 9);
        PD_CHECK_EQ(result, layout.rows, 1);
    }

    begin_suite(result, "LayoutStore::normalize (camera_order)");

    {
        // Doublons et indices hors bornes filtrés, puis les caméras
        // manquantes sont ajoutées dans l'ordre croissant.
        LayoutConfig layout;
        layout.camera_order = {5, 1, 1, 0, 100};

        LayoutStore::normalize(layout, 3);

        const std::vector<std::size_t> expected{1, 0, 2};
        PD_CHECK(result, layout.camera_order == expected);
    }

    begin_suite(result, "LayoutStore::normalize (placements)");

    {
        // Une deuxième entrée pour la même caméra est ignorée : c'est la
        // première occurrence qui fait foi.
        LayoutConfig layout;
        layout.placements.push_back(LayoutPlacement{0, 0, 0, 1, 1});
        layout.placements.push_back(LayoutPlacement{0, 2, 2, 1, 1});

        LayoutStore::normalize(layout, 1);

        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{1});
        PD_CHECK_EQ(result, layout.placements[0].x, 0);
        PD_CHECK_EQ(result, layout.placements[0].y, 0);
    }

    {
        // Une caméra dont l'index dépasse camera_count est purement
        // ignorée (pas de placement fantôme).
        LayoutConfig layout;
        layout.placements.push_back(LayoutPlacement{5, 0, 0, 1, 1});

        LayoutStore::normalize(layout, 2);

        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{2});

        for (const auto& placement : layout.placements) {
            PD_CHECK(result, placement.camera < 2);
        }
    }

    {
        // width/height hors bornes sont ramenées dans [1, columns/rows].
        LayoutConfig layout;
        layout.columns = 3;
        layout.rows = 3;
        layout.placements.push_back(LayoutPlacement{0, 0, 0, 0, 999});

        LayoutStore::normalize(layout, 1);

        PD_CHECK_EQ(result, layout.placements[0].width, 1);
        PD_CHECK_EQ(result, layout.placements[0].height, 3);
    }

    {
        // Un placement qui dépasse la grille après clamp de x/width est
        // repositionné (translaté) plutôt qu'envoyé en collision.
        LayoutConfig layout;
        layout.columns = 3;
        layout.rows = 1;
        layout.placements.push_back(LayoutPlacement{0, 2, 0, 2, 1});

        LayoutStore::normalize(layout, 1);

        PD_CHECK_EQ(result, layout.placements[0].x, 1);
        PD_CHECK_EQ(result, layout.placements[0].width, 2);
    }

    {
        // Deux caméras qui revendiquent la même cellule : la seconde
        // (dans l'ordre de traitement, donc la caméra d'indice le plus
        // élevé ici puisqu'on trie par caméra en sortie mais qu'on traite
        // dans l'ordre du vecteur d'entrée) est déplacée vers la première
        // cellule libre au lieu de se superposer.
        LayoutConfig layout;
        layout.columns = 2;
        layout.rows = 2;
        layout.placements.push_back(LayoutPlacement{0, 0, 0, 1, 1});
        layout.placements.push_back(LayoutPlacement{1, 0, 0, 1, 1});

        LayoutStore::normalize(layout, 2);

        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{2});
        PD_CHECK_EQ(result, layout.placements[0].x, 0);
        PD_CHECK_EQ(result, layout.placements[0].y, 0);
        // La caméra 1 est repoussée sur la cellule libre suivante (1,0).
        PD_CHECK_EQ(result, layout.placements[1].x, 1);
        PD_CHECK_EQ(result, layout.placements[1].y, 0);
    }

    {
        // Grille totalement pleine (1x1) avec 2 caméras : la deuxième ne
        // trouve aucune cellule libre. Ce cas documente le repli connu de
        // first_free() (voir le commentaire dans Layout.cpp) : une
        // position déterministe est renvoyée même si elle déborde de la
        // grille logique. Ce test fige ce comportement pour éviter qu'un
        // futur changement ne le fasse planter ou dérive silencieusement
        // vers autre chose sans qu'on s'en rende compte.
        LayoutConfig layout;
        layout.columns = 1;
        layout.rows = 1;

        LayoutStore::normalize(layout, 2);

        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{2});
        PD_CHECK_EQ(result, layout.placements[0].x, 0);
        PD_CHECK_EQ(result, layout.placements[0].y, 0);
        PD_CHECK_EQ(result, layout.placements[1].x, 0);
        PD_CHECK_EQ(result, layout.placements[1].y, 1);
    }

    {
        // La sortie est toujours triée par index de caméra, quel que soit
        // l'ordre d'entrée.
        LayoutConfig layout;
        layout.columns = 3;
        layout.rows = 3;
        layout.placements.push_back(LayoutPlacement{2, 0, 0, 1, 1});
        layout.placements.push_back(LayoutPlacement{0, 1, 0, 1, 1});
        layout.placements.push_back(LayoutPlacement{1, 2, 0, 1, 1});

        LayoutStore::normalize(layout, 3);

        PD_CHECK_EQ(result, layout.placements[0].camera, std::size_t{0});
        PD_CHECK_EQ(result, layout.placements[1].camera, std::size_t{1});
        PD_CHECK_EQ(result, layout.placements[2].camera, std::size_t{2});
    }
}

void run_layout_persistence_tests(TestResult& result)
{
    begin_suite(result, "LayoutStore::load / save (persistance disque)");

    {
        // Fichier absent : load() doit créer une disposition par défaut,
        // déjà normalisée, et la sauvegarder pour la prochaine lecture.
        const std::string path = temp_layout_path("missing");
        std::filesystem::remove(path);

        LayoutConfig layout = LayoutStore::load(path, 3);

        PD_CHECK(result, std::filesystem::exists(path));
        PD_CHECK_EQ(result, layout.placements.size(), std::size_t{3});
        PD_CHECK_EQ(result, layout.camera_order.size(), std::size_t{3});

        std::filesystem::remove(path);
    }

    {
        // Aller-retour save() -> load() : une disposition valide doit
        // ressortir identique (les champs sauvegardés sont exactement
        // ceux relus par load()).
        const std::string path = temp_layout_path("roundtrip");
        std::filesystem::remove(path);

        LayoutConfig original;
        original.columns = 4;
        original.rows = 2;
        original.fullscreen_on_start = true;
        original.camera_order = {1, 0};
        original.placements.push_back(LayoutPlacement{0, 0, 0, 2, 1});
        original.placements.push_back(LayoutPlacement{1, 2, 0, 2, 1});

        LayoutStore::save(path, original);
        const LayoutConfig reloaded = LayoutStore::load(path, 2);

        PD_CHECK_EQ(result, reloaded.columns, 4);
        PD_CHECK_EQ(result, reloaded.rows, 2);
        PD_CHECK_EQ(result, reloaded.fullscreen_on_start, true);
        PD_CHECK_EQ(result, reloaded.placements.size(), std::size_t{2});
        PD_CHECK_EQ(result, reloaded.placements[0].width, 2);
        PD_CHECK_EQ(result, reloaded.placements[1].x, 2);

        std::filesystem::remove(path);
    }

    {
        // Fichier JSON écrit à la main avec des valeurs hors bornes : load()
        // doit les corriger via normalize() (garde-fou contre un fichier de
        // config altéré ou édité manuellement), pas planter ni les garder
        // telles quelles.
        const std::string path = temp_layout_path("corrupted");
        std::filesystem::remove(path);

        {
            std::ofstream output{path};
            output << R"({
                "columns": 42,
                "rows": -1,
                "fullscreen_on_start": false,
                "camera_order": [9, 9, 0],
                "placements": [
                    {"camera": 0, "x": 0, "y": 0, "width": 1, "height": 1},
                    {"camera": 1, "x": 0, "y": 0, "width": 1, "height": 1}
                ]
            })";
        }

        const LayoutConfig reloaded = LayoutStore::load(path, 2);

        PD_CHECK_EQ(result, reloaded.columns, 9);
        PD_CHECK_EQ(result, reloaded.rows, 1);
        PD_CHECK_EQ(result, reloaded.placements.size(), std::size_t{2});

        // Les deux caméras revendiquaient la même cellule : la normalisation
        // doit les avoir séparées (pas de recouvrement).
        PD_CHECK(
            result,
            !(
                reloaded.placements[0].x == reloaded.placements[1].x &&
                reloaded.placements[0].y == reloaded.placements[1].y
            )
        );

        std::filesystem::remove(path);
    }
}

} // namespace pidecoder::test
