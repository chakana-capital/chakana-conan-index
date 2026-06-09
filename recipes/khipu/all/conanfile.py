import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import get, copy
from conan.errors import ConanInvalidConfiguration


class KhipuConan(ConanFile):
    """Published Conan recipe for Khipu's C++ feature engine.

    The chakana-conan-index (local-recipes-index) form of khipu's in-tree
    recipe (khipu/conanfile.py). Same build/package logic; the ONLY
    difference is source(): instead of exports_sources (which needs the
    khipu checkout), it downloads the v<version> git-tag source archive
    from the PRIVATE chakana-capital/khipu GitHub repo.

    Private repo -> the download needs auth. The token is read from the
    CHAKANA_GH_TOKEN environment variable at build time and sent as an
    Authorization header; it is NEVER stored in this recipe, conandata.yml,
    or anywhere in git. Provide a fine-grained PAT (chakana-capital,
    Contents: Read-only) via CHAKANA_GH_TOKEN before building.

    Downstream (yachay): `requires = "khipu/0.1.0"` +
    find_package(khipu CONFIG REQUIRED) -> khipu::khipu.
    """

    name = "khipu"
    license = "proprietary"
    description = "Chakana Capital C++ feature engine (CRTP book + spec plugins)"
    settings = "os", "arch", "compiler", "build_type"

    # Runtime dependency closure (mirrors khipu/conanfile.py). pachamama +
    # databento-cpp come from this same index; arrow/openssl/nlohmann_json
    # from ConanCenter.
    requires = (
        "pachamama/0.1.0",
        "databento-cpp/0.57.0",
        "arrow/24.0.0",
        "openssl/3.6.2",
        "nlohmann_json/3.12.0",
    )

    def configure(self):
        # Arrow: khipu uses the Arrow C Data Interface + writes Parquet/CSV
        # (khipu_replay_spec). Needs Parquet + shared; everything else heavy
        # is OFF to keep the arrow build lean. (Matches khipu/conanfile.py.)
        self.options["arrow"].shared = True
        self.options["arrow"].parquet = True
        self.options["arrow"].with_thrift = True
        self.options["arrow"].compute = False
        self.options["arrow"].dataset_modules = False
        self.options["arrow"].with_flight_rpc = False
        self.options["arrow"].with_flight_sql = False
        self.options["arrow"].gandiva = False
        self.options["arrow"].with_s3 = False
        self.options["arrow"].with_gcs = False
        self.options["arrow"].with_hdfs = False
        self.options["arrow"].with_cuda = False
        self.options["arrow"].with_orc = False
        self.options["arrow"].with_substrait = False
        self.options["arrow"].with_csv = True
        self.options["arrow"].with_json = False
        self.options["databento-cpp"].shared = True
        self.options["openssl"].shared = True

    def build_requirements(self):
        self.test_requires("gtest/1.15.0")

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

    def layout(self):
        cmake_layout(self)

    def generate(self):
        CMakeDeps(self).generate()
        tc = CMakeToolchain(self)
        # Build the spec/regression .so plugins (khipu's product). Needs
        # libclang 17 + g++ + clang.cindex -- chakana-base >= 0.1.4 ships them.
        tc.cache_variables["KHIPU_BUILD_SPECS"] = True
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        if not self.conf.get("tools.build:skip_test", default=False):
            cmake.test()

    def package(self):
        inc_src = os.path.join(self.source_folder, "cpp", "include")
        inc_dst = os.path.join(self.package_folder, "include")
        copy(self, "*.h", src=inc_src, dst=inc_dst)
        copy(self, "*.hpp", src=inc_src, dst=inc_dst)

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "khipu")
        self.cpp_info.set_property("cmake_target_name", "khipu::khipu")
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = []
        self.cpp_info.system_libs = ["dl", "pthread"]
