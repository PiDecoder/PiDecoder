# Contributing to PiDecoder

Thank you for helping improve PiDecoder.

## Before opening a pull request

1. Open or reference an issue for non-trivial changes.
2. Keep release-candidate changes focused on bugs, regressions and stability.
3. Never include real credentials, RTSP URLs, private IP addresses, serial numbers or camera logs.
4. Run the release validator:

```bash
./scripts/validate-release.sh
```

5. Build the C++ project:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
```

## Branch names

```text
fix/short-description
docs/short-description
feature/short-description
release/version
```

## Commit messages

Use clear, imperative messages:

```text
Fix ONVIF profile deduplication
Improve reconnect logging
Document Raspberry Pi installation
```

## Pull requests

A pull request should include:

- the problem being solved
- the chosen approach
- test steps
- screenshots for Web UI changes
- confirmation that no credentials or private data are included
