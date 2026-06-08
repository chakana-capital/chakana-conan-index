# chakana-conan-index

Chakana's **private Conan recipe index** — a `conancenter`-style git repo
of C++ package recipes the stack depends on but which aren't on the public
ConanCenter (today: `databento-cpp`; later: `pachamama`, `khipu`).

It is a Conan **`local-recipes-index`** remote: Conan reads the recipes
directly from a checkout of this repo — **no Conan server to run**. The
recipes are *text*; the actual compiled binaries are built from them on
first use (and, later, optionally cached as pre-built artifacts on a real
remote).

See [`../amauta/foundations/packaging_and_deployment.md`](../amauta/foundations/packaging_and_deployment.md)
for where this sits in the 3-layer pinning model (Docker machine → **Conan
C++ deps** → pip wheels → chakana-releases blessing).

## What's here

```
recipes/
  <package>/
    config.yml                 # versions -> folder map
    all/
      conanfile.py             # the recipe (uses self.version)
      conandata.yml            # per-version source: url + sha256 (pinned)
```

Current recipes:

| Package | Version | Source | Why we package it |
|---|---|---|---|
| `databento-cpp` | 0.57.0 | github.com/databento/databento-cpp (sha256-pinned in conandata.yml) | DBN decode + Databento client; CMake/vcpkg upstream, **not on ConanCenter**. FetchContent'd by pachamama + khipu before this. Recipe declares its 5 deps (openssl/zstd/nlohmann_json/cpp-httplib/date — all on ConanCenter) + uses `DATABENTO_USE_EXTERNAL_*` so the build is fully declared, reproducible, no git fetches. |

## Use it (add as a remote)

Conan must run in the **chakana-base** image (pinned gcc 16.1 / cmake /
conan), so the package ABI matches the stack. With this repo checked out
at `<path>`:

```bash
conan remote add chakana-index <path-to-chakana-conan-index> \
    --type=local-recipes-index
conan remote list
#   chakana-index: <path> [local-recipes-index, Enabled: True]

# resolve + build a recipe from the index into the local cache:
conan install --requires=databento-cpp/0.57.0 --build=missing -r chakana-index
```

Downstream recipes (pachamama, khipu) just `requires "databento-cpp/0.57.0"`;
Conan finds it here (+ its deps on ConanCenter).

## Conventions

- **Recipes only — never built binaries.** Text in git; binaries are
  built from recipes (eventually mirrored to a real Conan remote if build
  times warrant). Same "no binaries in git" rule as chakana-releases.
- **Sources are sha256-pinned** in each `conandata.yml` (provenance).
- **Recipes are validated inside `chakana-base`** before they land here
  (gcc 16.1 / cmake 3.31.10 / conan 2.29) — never against a host toolchain.
- One package per `recipes/<name>/`, conancenter layout, so a future
  migration to a hosted index / ConanCenter contribution is trivial.

## Provenance

Created 2026-06-08 as the Conan-layer home of the Chakana packaging
initiative. First recipe (`databento-cpp/0.57.0`) validated end-to-end in
chakana-base:0.1.1 the same day (built from source against the pinned
toolchain, deps from ConanCenter, no FetchContent).
