#include "test_harness.hpp"

#include "pidecoder/RedactUrl.hpp"

namespace pidecoder::test {

void run_redact_url_tests(TestResult& result)
{
    begin_suite(result, "redact_credentials (anti-fuite RTSP dans les logs)");

    {
        // Cas réel : identifiants encodés (mot de passe contenant un '@'
        // percent-encodé en %40, comme le fait config-web.py côté Python).
        const std::string in =
            "rtsp://admin:S3cr%40t@10.0.0.210:554/onvif-media/media.amp"
            "?profile=profile_1_h264&resolution=640x360&fps=12";

        const std::string expected =
            "rtsp://***:***@10.0.0.210:554/onvif-media/media.amp"
            "?profile=profile_1_h264&resolution=640x360&fps=12";

        PD_CHECK_EQ(result, redact_credentials(in), expected);
    }

    {
        // Pas d'identifiants dans l'URL : rien à cacher, on ne touche à rien.
        const std::string in =
            "rtsp://10.0.0.42:554/axis-media/media.amp?videocodec=h264";

        PD_CHECK_EQ(result, redact_credentials(in), in);
    }

    {
        // Nom d'utilisateur seul, sans mot de passe explicite (userinfo au
        // format "user@" plutôt que "user:pass@") : toujours masqué.
        const std::string in = "rtsp://user@host/path";
        const std::string expected = "rtsp://***:***@host/path";

        PD_CHECK_EQ(result, redact_credentials(in), expected);
    }

    {
        // Chaîne qui ne ressemble pas à une URL : renvoyée telle quelle,
        // pas d'exception, pas de plantage.
        const std::string in = "chemin/local/sans/schema";

        PD_CHECK_EQ(result, redact_credentials(in), in);
    }

    {
        // Chaîne vide : cas limite, ne doit pas planter.
        const std::string in;

        PD_CHECK_EQ(result, redact_credentials(in), in);
    }

    {
        // Un '@' qui n'apparaît que dans le chemin/la requête (après le
        // premier '/' suivant l'autorité) ne fait pas partie des
        // identifiants et ne doit pas être touché.
        const std::string in =
            "rtsp://host/path?redirect=http://foo@bar";

        PD_CHECK_EQ(result, redact_credentials(in), in);
    }

    {
        // Identifiants présents ET un '@' plus loin dans la requête : seule
        // la partie identifiants (avant le premier '/' de l'autorité) doit
        // être masquée, le reste de l'URL reste inchangé.
        const std::string in =
            "rtsp://admin:pass@host/path?note=a@b";

        const std::string expected =
            "rtsp://***:***@host/path?note=a@b";

        PD_CHECK_EQ(result, redact_credentials(in), expected);
    }
}

} // namespace pidecoder::test
