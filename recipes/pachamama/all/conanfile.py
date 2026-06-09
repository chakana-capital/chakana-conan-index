import os

from conan import ConanFile
from conan.tools.files import get
from conan.errors import ConanInvalidConfiguration


class PachamamaConan(ConanFile):
    """Published Conan recipe for Pachamama's C++ control plane.

    THIN subclass: all build/package/package_info logic is inherited from
    the pachamama-base python_requires recipe (recipes/pachamama-base/),
    the SINGLE SOURCE OF TRUTH shared with pachamama's in-tree conanfile.
    The ONLY thing this recipe adds is source(): instead of exports_sources
    (which needs the pachamama checkout), it downloads the v<version>
    git-tag source archive from the PRIVATE chakana-capital/pachamama
    GitHub repo.

    Because the repo is private, the download needs auth. The token is
    read from the CHAKANA_GH_TOKEN environment variable at build time and
    sent as an Authorization header -- it is NEVER stored in this recipe,
    conandata.yml, or anywhere in git. Provide a fine-grained PAT
    (chakana-capital, Contents: Read-only) via CHAKANA_GH_TOKEN before
    `conan install`/`conan create`.

    Downstream: `requires = "pachamama/0.1.0"` +
    find_package(Pachamama CONFIG REQUIRED) ->
    Pachamama::pachamama_consumer.
    """

    python_requires = "pachamama-base/1.0"
    python_requires_extend = "pachamama-base.PachamamaBase"

    name = "pachamama"

    def source(self):
        token = os.environ.get("CHAKANA_GH_TOKEN")
        if not token:
            raise ConanInvalidConfiguration(
                "pachamama is a PRIVATE repo; set CHAKANA_GH_TOKEN (a "
                "fine-grained GitHub PAT with Contents:read on "
                "chakana-capital/pachamama) before building this recipe. "
                "The token is read from the environment and never stored."
            )
        # get() verifies the sha256 from conandata.yml; strip_root drops
        # the GitHub-added "chakana-capital-pachamama-<sha>/" top dir.
        # The GitHub tarball URL 302-redirects to a signed codeload URL;
        # the Authorization header carries through (verified working).
        #
        # filename=... is REQUIRED: the API tarball URL has no .tar.gz
        # extension, so Conan can't infer the archive type and defaults to
        # unzip -> "BadZipFile". Giving it a .tar.gz name makes get() pick
        # the gzip/tar extractor.
        get(self, **self.conan_data["sources"][self.version],
            headers={"Authorization": f"Bearer {token}"},
            filename="pachamama-src.tar.gz",
            strip_root=True)
