import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import get
from conan.errors import ConanInvalidConfiguration


class PachamamaConan(ConanFile):
    """Published Conan recipe for Pachamama's C++ control plane.

    This is the chakana-conan-index (local-recipes-index) form of the
    recipe that lives in-tree at pachamama/conanfile.py. The ONLY
    difference is source(): instead of exports_sources (which needs the
    pachamama checkout), it downloads the v<version> git-tag source
    archive from the PRIVATE chakana-capital/pachamama GitHub repo.

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

    name = "pachamama"
    license = "proprietary"
    description = "Chakana Capital data storage + acquisition C++ control plane"
    settings = "os", "arch", "compiler", "build_type"

    # Mirrors pachamama/conanfile.py. databento-cpp comes from this same
    # index; everything else from ConanCenter. databento-cpp's public
    # headers transitively supply date/cpp-httplib/zstd/openssl, so no
    # shim is needed here.
    requires = (
        "databento-cpp/0.57.0",
        "protobuf/5.27.0",
        "nlohmann_json/3.12.0",
    )

    def build_requirements(self):
        self.test_requires("gtest/1.15.0")
        self.tool_requires("protobuf/5.27.0")

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

    def layout(self):
        cmake_layout(self)

    def generate(self):
        CMakeDeps(self).generate()
        tc = CMakeToolchain(self)
        # The pybind11 native catalog extension is a Python concern, not
        # part of the installable C++ package; the hermetic build has no
        # Python dev headers. Off for the Conan build.
        tc.cache_variables["PACHAMAMA_BUILD_PYTHON_NATIVE"] = False
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        if not self.conf.get("tools.build:skip_test", default=False):
            cmake.test()

    def package(self):
        CMake(self).install()

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Pachamama")
        self.cpp_info.set_property("cmake_target_name", "Pachamama::pachamama_consumer")
        self.cpp_info.libs = ["pachamama_control", "pachamama_control_proto"]
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.system_libs = ["rt", "pthread"]
