#pragma once

// Mini harnais de test, volontairement sans dépendance externe (dans le même
// esprit que le reste du projet : pas de Catch2/GoogleTest/doctest à
// installer sur le Pi juste pour ce garde-fou).
//
// Usage :
//   pidecoder::test::TestResult result;
//   pidecoder::test::begin_suite(result, "Nom du groupe de tests");
//   PD_CHECK(result, condition);
//   PD_CHECK_EQ(result, valeur_obtenue, valeur_attendue);
//   ...
//   return pidecoder::test::summarize(result);

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

namespace pidecoder::test {

struct TestResult final {
    int passed{0};
    int failed{0};
    std::string current_suite;
};

inline void begin_suite(
    TestResult& result,
    const std::string& name
)
{
    result.current_suite = name;
    std::cout << "== " << name << " ==\n";
}

inline void report(
    TestResult& result,
    const bool condition,
    const std::string& description,
    const char* file,
    const int line
)
{
    if (condition) {
        ++result.passed;
        return;
    }

    ++result.failed;

    std::cerr
        << "[FAIL] " << file << ":" << line
        << " (" << result.current_suite << ") "
        << description << "\n";
}

inline int summarize(const TestResult& result)
{
    std::cout
        << "\n"
        << result.passed << " test(s) réussi(s), "
        << result.failed << " échec(s).\n";

    return result.failed == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}

} // namespace pidecoder::test

#define PD_CHECK(result, condition) \
    ::pidecoder::test::report( \
        (result), \
        static_cast<bool>(condition), \
        #condition, \
        __FILE__, \
        __LINE__ \
    )

#define PD_CHECK_EQ(result, actual, expected) \
    do { \
        const auto pd_actual_value = (actual); \
        const auto pd_expected_value = (expected); \
        std::ostringstream pd_message; \
        pd_message \
            << #actual << " == " << #expected \
            << " (obtenu " << pd_actual_value \
            << ", attendu " << pd_expected_value << ")"; \
        ::pidecoder::test::report( \
            (result), \
            pd_actual_value == pd_expected_value, \
            pd_message.str(), \
            __FILE__, \
            __LINE__ \
        ); \
    } while (false)
