import os

from conan import ConanFile
from conan.tools.files import get
from conan.errors import ConanInvalidConfiguration


class KhipuConan(ConanFile):
    """Published Conan recipe for Khipu's C++ feature engine.

    THIN subclass: all build/package/package_info logic -- including the
    spec-compilation TOOLCHAIN that ships khipu_codegen.py + the cmake
    machinery + cpp_info.builddirs -- is inherited from the khipu-base
    python_requires recipe (recipes/khipu-base/), the SINGLE SOURCE OF
    TRUTH shared with khipu's in-tree conanfile. The ONLY thing this recipe
    adds is source(): instead of exports_sources (which needs the khipu
    checkout), it downloads the v<version> git-tag source archive from the
    PRIVATE chakana-capital/khipu GitHub repo.

    Before the python_requires split this recipe carried its OWN
    build/package logic and had drifted to headers-only -- it did NOT ship
    the spec toolchain the in-tree recipe shipped. Inheriting the base
    fixes that: this published recipe now ships the toolchain too.

    Private repo -> the download needs auth. The token is read from the
    CHAKANA_GH_TOKEN environment variable at build time and sent as an
    Authorization header; it is NEVER stored in this recipe, conandata.yml,
    or anywhere in git. Provide a fine-grained PAT (chakana-capital,
    Contents: Read-only) via CHAKANA_GH_TOKEN before building.

    Downstream (yachay): `requires = "khipu/0.2.0"` +
    find_package(khipu CONFIG REQUIRED) -> khipu::khipu.
    """

    python_requires = "khipu-base/1.0"
    python_requires_extend = "khipu-base.KhipuBase"

    name = "khipu"

    def source(self):
        token = os.environ.get("CHAKANA_GH_TOKEN")
        if not token:
            raise ConanInvalidConfiguration(
                "khipu is a PRIVATE repo; set CHAKANA_GH_TOKEN (a "
                "fine-grained GitHub PAT with Contents:read on "
                "chakana-capital/khipu) before building this recipe. "
                "The token is read from the environment and never stored."
            )
        # filename=...tar.gz so Conan untars (the GitHub API tarball URL has
        # no extension, else it tries to unzip -> BadZipFile). The 302 ->
        # codeload redirect carries the auth through (verified for pachamama).
        get(self, **self.conan_data["sources"][self.version],
            headers={"Authorization": f"Bearer {token}"},
            filename="khipu-src.tar.gz",
            strip_root=True)
