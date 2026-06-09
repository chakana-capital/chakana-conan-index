from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout


class PythonRequires(ConanFile):
    """python_requires carrier for the shared pachamama base recipe.

    A python_requires recipe is itself a ConanFile (so it can be exported
    to the cache / served from the index), but it ships no binaries:
    package_type = "python-require". Its only payload is the PachamamaBase
    class below, which the in-tree recipe (pachamama/conanfile.py) and the
    published recipe (recipes/pachamama/all/conanfile.py) both subclass.
    """

    name = "pachamama-base"
    version = "1.0"
    package_type = "python-require"


class PachamamaBase:
    """SINGLE SOURCE OF TRUTH for pachamama's Conan build/package logic.

    Plain mixin class (does NOT inherit ConanFile). Both consumers do:

        class Pachamama(python_requires["pachamama-base"].module.PachamamaBase,
                        ConanFile):
            ...

    so the ConanFile machinery comes from ConanFile (later in the MRO)
    while every method below is inherited unchanged. The consumers add
    ONLY what differs:

      * the in-tree recipe adds exports_sources (builds from the checkout);
      * the published recipe adds source() (token-auth tarball fetch).

    NOTE on inheritance (Conan 2.x): a bare `requires` class attribute on a
    python_requires mixin does NOT reliably propagate to the subclass, so
    the dependency closure is expressed as a requirements() method, which
    inherits cleanly through the MRO.
    """

    license = "proprietary"
    description = "Chakana Capital data storage + acquisition C++ control plane"
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        # The C++ runtime dependency closure. Versions pinned to match the
        # cache already built in chakana-base; nlohmann_json/3.12.0 is what
        # databento-cpp/0.57.0 itself pins, so there is no version conflict.
        #
        # databento-cpp's PUBLIC headers (<databento/exceptions.hpp> etc.)
        # leak date/cpp-httplib/zstd/openssl into their include surface, but
        # the databento-cpp/0.57.0 recipe declares those as
        # transitive_headers=True public requirements (with cpp_info.requires),
        # so Conan's CMakeDeps propagates all of them to databento::databento
        # automatically. No direct cpp-httplib require (or any other
        # transitive-dep shim) is needed here.
        self.requires("databento-cpp/0.57.0")
        self.requires("protobuf/5.27.0")
        self.requires("nlohmann_json/3.12.0")

    def build_requirements(self):
        # gtest is a TEST-only dependency: the C++ suite links
        # GTest::gtest_main, but nothing in the installed package surface
        # needs it. Keep it out of the runtime requires so consumers of
        # pachamama don't drag in gtest.
        self.test_requires("gtest/1.15.0")
        # protoc (host tool) comes from the protobuf package. When
        # cross-building we'd want it in the build context explicitly; for
        # the native chakana-base build the regular requires entry already
        # exposes protoc, but declaring it as a tool_requires keeps codegen
        # working under two-profile builds.
        self.tool_requires("protobuf/5.27.0")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        # The pybind11 native catalog extension is a Python-extension
        # concern, not part of the installable C++ control-plane package,
        # and the hermetic build image has no Python dev headers /
        # pybind11. Skip it for the Conan build; the dev `cmake -S . -B`
        # flow keeps it ON by default.
        tc.cache_variables["PACHAMAMA_BUILD_PYTHON_NATIVE"] = False
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        # Run the C++ test suite as part of the build so a broken
        # protobuf 3.12 -> 5.27 jump (or any dep-source regression) is
        # caught at package-build time, not silently shipped.
        if not self.conf.get("tools.build:skip_test", default=False):
            cmake.test()

    def package(self):
        # pachamama's CMake already declares the full
        # install(TARGETS ... EXPORT PachamamaTargets) + PachamamaConfig
        # machinery; just drive it.
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        # Match the existing CMake export: find_package name "Pachamama",
        # namespace "Pachamama::". A consumer doing
        # find_package(Pachamama CONFIG REQUIRED) +
        # target_link_libraries(... Pachamama::pachamama_consumer) keeps
        # working unchanged whether they get pachamama from a sibling
        # install or from Conan.
        self.cpp_info.set_property("cmake_file_name", "Pachamama")
        self.cpp_info.set_property("cmake_target_name", "Pachamama::pachamama_consumer")

        # The installed runtime libraries. pachamama_consumer itself is
        # header-only (INTERFACE), so the load-bearing libs here are the
        # control plane .sos that ship under lib/.
        self.cpp_info.libs = ["pachamama_control", "pachamama_control_proto"]
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libdirs = ["lib"]
        self.cpp_info.bindirs = ["bin"]

        # Consumer-facing target needs librt (shm_open / shm_unlink) +
        # pthread, mirroring cpp/CMakeLists.txt's pachamama_consumer
        # INTERFACE link.
        self.cpp_info.system_libs = ["rt", "pthread"]
