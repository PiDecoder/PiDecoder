// Point d'entrée du garde-fou : exécute tous les tests Grid/Layout et
// renvoie un code de sortie non nul si l'un d'eux échoue (pour ctest et la
// CI). Volontairement sans dépendance à un framework externe.
#include "test_harness.hpp"

namespace pidecoder::test {

void run_grid_tests(TestResult&);
void run_layout_normalize_tests(TestResult&);
void run_layout_persistence_tests(TestResult&);
void run_redact_url_tests(TestResult&);

} // namespace pidecoder::test

int main()
{
    pidecoder::test::TestResult result;

    pidecoder::test::run_grid_tests(result);
    pidecoder::test::run_layout_normalize_tests(result);
    pidecoder::test::run_layout_persistence_tests(result);
    pidecoder::test::run_redact_url_tests(result);

    return pidecoder::test::summarize(result);
}
