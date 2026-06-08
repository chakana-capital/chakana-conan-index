# Claude Code instructions for this repo

Loaded automatically when Claude Code operates here. Project rules below
override defaults where they conflict.

## Commit messages
- **No `Co-Authored-By: Claude ...` trailer**, ever (any Chakana repo).
- Short imperative subject (<=72 chars), blank line, body explaining the
  *why*, wrapped ~72 cols.

## Repo role
chakana-conan-index is Chakana's **private Conan recipe index** -- a
`local-recipes-index` git remote of C++ recipes the stack needs but which
aren't on public ConanCenter (databento-cpp now; pachamama/khipu later).
Conan reads recipes straight from a checkout; no server. See
../amauta/foundations/packaging_and_deployment.md.

## What to never do here
- **Recipes only, never built binaries.** Text in git; binaries are built
  FROM the recipes (in the chakana-base image). No .tgz/.so/wheels here.
- **Always sha256-pin sources** in conandata.yml.
- **Validate recipes inside chakana-base** (pinned gcc 16.1 / cmake /
  conan) before committing -- never against a host toolchain. A recipe
  that only builds on someone's laptop defeats the purpose.
- Keep the conancenter layout (recipes/<name>/{config.yml, all/...}) so
  recipes stay portable to a hosted index / ConanCenter later.

## Memory mechanics
Shared pool at ~/.claude/chakana-capital-memory/. Enroll:
    mkdir -p ~/.claude/projects/-home-jgarcia-projects-chakana-chakana-conan-index
    ln -s ~/.claude/chakana-capital-memory \
          ~/.claude/projects/-home-jgarcia-projects-chakana-chakana-conan-index/memory
