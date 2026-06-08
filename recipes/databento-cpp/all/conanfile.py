from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.files import get, copy
import os


class DatabentoCppConan(ConanFile):
    name = "databento-cpp"
    license = "Apache-2.0"
    homepage = "https://github.com/databento/databento-cpp"
    description = "Official C++ client for Databento (DBN decode + historical/live)"
    topics = ("databento", "market-data", "dbn", "trading")
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    # databento-cpp's REQUIRED find_package deps (all on conancenter). The
    # DATABENTO_USE_EXTERNAL_* toggles below make databento consume THESE
    # instead of git-fetching them itself -- so the build is fully declared,
    # reproducible, and offline-friendly (no FetchContent).
    requires = (
        "openssl/3.6.2",
        "zstd/1.5.7",
        "nlohmann_json/3.12.0",
        "cpp-httplib/0.46.1",
        "date/3.0.4",
    )

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def source(self):
        # Pinned source (url + sha256) from conandata.yml -- verified on fetch.
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        # Out-of-source build: databento-cpp's CMakeLists hard-fails on an
        # in-source build (PROJECT_SOURCE_DIR == PROJECT_BINARY_DIR ->
        # FATAL_ERROR). cmake_layout separates build/ from the source tree.
        cmake_layout(self)

    def generate(self):
        CMakeDeps(self).generate()
        tc = CMakeToolchain(self)
        # Use the Conan-provided deps, not databento's FetchContent fallbacks.
        tc.cache_variables["DATABENTO_USE_EXTERNAL_JSON"] = True
        tc.cache_variables["DATABENTO_USE_EXTERNAL_HTTPLIB"] = True
        tc.cache_variables["DATABENTO_USE_EXTERNAL_DATE"] = True
        tc.cache_variables["DATABENTO_ENABLE_EXAMPLES"] = False
        tc.cache_variables["DATABENTO_ENABLE_TESTING"] = False
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "LICENSE", self.source_folder,
             os.path.join(self.package_folder, "licenses"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "databento")
        self.cpp_info.set_property("cmake_target_name", "databento::databento")
        self.cpp_info.libs = ["databento"]
