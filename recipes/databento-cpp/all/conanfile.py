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

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def requirements(self):
        # databento-cpp's deps (all on ConanCenter). databento links ALL of
        # these PUBLIC (its CMakeLists target_link_libraries(... PUBLIC ...))
        # and its INSTALLED public headers #include them:
        #   exceptions.hpp -> <httplib.h>, <nlohmann/json.hpp>
        #   (others)       -> <date/date.h>, <zstd.h>, <openssl/...>
        #
        # transitive_headers=True is the load-bearing trait: it tells Conan
        # these deps' headers are part of databento's OWN public interface, so
        # (a) Conan propagates their include dirs onto consumers, and (b) it
        # does NOT skip their binaries (header-only cpp-httplib would otherwise
        # be "binary: Skip", giving consumers "httplib.h: No such file").
        # With this, a consumer needs only find_package(databento) -- no
        # per-consumer knowledge of databento's deps, no include-path grafting.
        self.requires("openssl/3.6.2", transitive_headers=True, transitive_libs=True)
        self.requires("zstd/1.5.7", transitive_headers=True, transitive_libs=True)
        self.requires("nlohmann_json/3.12.0", transitive_headers=True)
        self.requires("cpp-httplib/0.46.1", transitive_headers=True)
        self.requires("date/3.0.4", transitive_headers=True, transitive_libs=True)

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
        # databento links ALL of these PUBLIC (transitive to consumers; see
        # its CMakeLists target_link_libraries(... PUBLIC ...)). Its installed
        # public headers #include <httplib.h>, <nlohmann/json.hpp>,
        # <date/date.h>, <zstd.h>. Declaring cpp_info.requires makes CMakeDeps
        # propagate every dep's include dirs + links onto databento::databento,
        # so a consumer needs NOTHING beyond find_package(databento). Without
        # this, the consumer's compile fails to find those headers.
        self.cpp_info.requires = [
            "date::date",
            "cpp-httplib::cpp-httplib",
            "nlohmann_json::nlohmann_json",
            "openssl::openssl",
            "zstd::zstd",
        ]
