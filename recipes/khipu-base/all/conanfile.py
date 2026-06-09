import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import copy


class PythonRequires(ConanFile):
    """python_requires carrier for the shared khipu base recipe.

    A python_requires recipe is itself a ConanFile (so it can be exported
    to the cache / served from the index), but it ships no binaries:
    package_type = "python-require". Its only payload is the KhipuBase
    class below, which the in-tree recipe (khipu/conanfile.py) and the
    published recipe (recipes/khipu/all/conanfile.py) both subclass.
    """

    name = "khipu-base"
    version = "1.0"
    package_type = "python-require"


class KhipuBase:
    """SINGLE SOURCE OF TRUTH for khipu's Conan build/package logic.

    This is a plain mixin class (it does NOT inherit ConanFile). Both
    consumers do:

        class Khipu(python_requires["khipu-base"].module.KhipuBase, ConanFile):
            ...

    so the real ConanFile machinery comes from ConanFile (later in the
    MRO) while every method below is inherited unchanged. The consumers
    add ONLY what differs between them:

      * the in-tree recipe adds exports_sources (builds from the checkout);
      * the published recipe adds source() (token-auth tarball fetch).

    Everything else -- the dependency closure, arrow option pinning, the
    spec-toolchain build, and the toolchain-shipping package()/
    package_info() -- lives here once. Keeping it here is the whole point:
    before this split, the in-tree and published khipu recipes drifted
    (the published one still shipped headers-only after the in-tree one
    grew the spec toolchain).

    NOTE on inheritance (Conan 2.x wrinkle): a bare `requires` class
    attribute declared on a python_requires mixin does NOT reliably
    propagate to the subclass, so the dependency closure is expressed as a
    requirements() method instead, which inherits cleanly through the MRO.
    """

    # --- shared identity ---------------------------------------------------
    license = "proprietary"
    description = "Chakana Capital C++ feature engine (CRTP book + spec plugins)"
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        # Runtime dependency closure (was a `requires` class attr; moved to
        # requirements() so it inherits through python_requires reliably).
        #
        # pachamama's consumer headers leak into khipu's INTERFACE include
        # surface (khipu/io/shm_source.hpp pulls in pachamama's control.h +
        # ring/*). databento-cpp's public headers similarly leak date /
        # cpp-httplib / zstd / openssl; the databento-cpp recipe declares
        # those transitive_headers so CMakeDeps propagates them.
        self.requires("pachamama/0.1.0")
        self.requires("databento-cpp/0.57.0")
        self.requires("arrow/24.0.0")
        self.requires("openssl/3.6.2")
        # khipu_replay_spec parses spec.json with nlohmann/json. Under Conan
        # the replay-spec target doesn't link databento, so require + link
        # nlohmann_json directly. 3.12.0 is exactly what databento-cpp/0.57.0
        # pins, so no version conflict.
        self.requires("nlohmann_json/3.12.0")

    def configure(self):
        # Arrow: khipu uses the Arrow C Data Interface (ArrowChunkSink) and
        # writes Parquet on the driver side (khipu_replay_spec). It needs
        # Parquet ON and shared libs (the target names khipu links,
        # Arrow::arrow_shared / Parquet::parquet_shared, only exist when
        # arrow/*:shared=True). Everything else heavy + optional is OFF to
        # keep the arrow build lean -- khipu touches none of it.
        self.options["arrow"].shared = True
        self.options["arrow"].parquet = True
        self.options["arrow"].with_thrift = True  # required by parquet
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
        # khipu_replay_spec writes CSV (arrow/csv/{api,writer}.h) on the
        # driver side, so the CSV module must stay ON.
        self.options["arrow"].with_csv = True
        self.options["arrow"].with_json = False
        # databento-cpp + openssl shared so the runtime closure matches the
        # spec .so model (everything PIC + shared).
        self.options["databento-cpp"].shared = True
        self.options["openssl"].shared = True

    def build_requirements(self):
        # gtest is TEST-only: the C++ suite links GTest::gtest_main but
        # nothing in khipu's installed surface needs it. Keep it out of the
        # runtime requires so downstream consumers (yachay) don't drag in
        # gtest.
        self.test_requires("gtest/1.15.0")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        # Build the spec/regression .so plugins as part of the package: they
        # ARE khipu's product (the dlopen-able engines yachay replays). The
        # codegen needs libclang 17 + a `g++` on PATH + the clang.cindex
        # Python binding -- all provided by chakana-base >= 0.1.4.
        tc.cache_variables["KHIPU_BUILD_SPECS"] = True
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        # Run the C++ test suite as part of the build so a dep-source
        # regression (FetchContent -> Conan, system Arrow -> Conan Arrow) is
        # caught at package-build time, not silently shipped.
        if not self.conf.get("tools.build:skip_test", default=False):
            cmake.test()

    def package(self):
        # Khipu's core engine is a header-only INTERFACE library. We ship
        # two things downstream:
        #
        #  (a) the engine HEADERS (cpp/include) -- khipu::khipu, and
        #  (b) the SPEC-COMPILATION TOOLCHAIN: the codegen + the
        #      khipu_add_spec() CMake machinery + the feature headers, so a
        #      consumer (yachay) can compile ITS OWN spec.json files into
        #      .sos stamped with khipu's spec_hash / build_hash. khipu is
        #      the engine + the spec CAPABILITY; the spec INSTANCES live
        #      with the consumer (the spec-ownership split, 2026-06-09).
        #
        # The package mirrors the source layout under the package root so a
        # single KHIPU_TOOLCHAIN_ROOT (= the package folder) makes
        # khipu_spec.cmake's ${root}/tools/codegen + ${root}/cpp/include
        # resolve unchanged.
        pf = self.package_folder
        sf = self.source_folder
        # (a) engine + feature headers, preserving the cpp/include/ tree.
        copy(self, "*.h",   src=os.path.join(sf, "cpp", "include"),
             dst=os.path.join(pf, "cpp", "include"))
        copy(self, "*.hpp", src=os.path.join(sf, "cpp", "include"),
             dst=os.path.join(pf, "cpp", "include"))
        # also mirror into include/ for plain header consumers (khipu::khipu).
        copy(self, "*.h",   src=os.path.join(sf, "cpp", "include"),
             dst=os.path.join(pf, "include"))
        copy(self, "*.hpp", src=os.path.join(sf, "cpp", "include"),
             dst=os.path.join(pf, "include"))
        # (b) the codegen tool + the CMake spec machinery.
        copy(self, "khipu_codegen.py",
             src=os.path.join(sf, "tools", "codegen"),
             dst=os.path.join(pf, "tools", "codegen"))
        copy(self, "khipu_spec.cmake",       src=os.path.join(sf, "cmake"),
             dst=os.path.join(pf, "lib", "cmake", "khipu"))
        copy(self, "khipu_regression.cmake", src=os.path.join(sf, "cmake"),
             dst=os.path.join(pf, "lib", "cmake", "khipu"))
        # A thin build-module that fixes KHIPU_TOOLCHAIN_ROOT to the package
        # folder, then includes khipu_spec.cmake -- so a consumer's
        # find_package(khipu) auto-exposes khipu_add_spec() pointed at the
        # PACKAGED toolchain (not the consumer's tree).
        module_dir = os.path.join(pf, "lib", "cmake", "khipu")
        os.makedirs(module_dir, exist_ok=True)
        with open(os.path.join(module_dir, "khipu-tools.cmake"), "w") as fh:
            fh.write(
                "# Auto-included by find_package(khipu). Points the spec\n"
                "# toolchain at this khipu package, then loads khipu_add_spec().\n"
                "get_filename_component(_khipu_pkg_root\n"
                '    "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)\n'
                'set(KHIPU_TOOLCHAIN_ROOT "${_khipu_pkg_root}" CACHE PATH\n'
                '    "Root of the khipu spec-compilation toolchain")\n'
                'include("${CMAKE_CURRENT_LIST_DIR}/khipu_spec.cmake")\n'
                'include("${CMAKE_CURRENT_LIST_DIR}/khipu_regression.cmake"\n'
                "        OPTIONAL)\n"
            )

    def package_info(self):
        # Khipu's consumable target: the header-only engine. namespace
        # khipu::, file name "khipu".
        self.cpp_info.set_property("cmake_file_name", "khipu")
        self.cpp_info.set_property("cmake_target_name", "khipu::khipu")
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = []
        self.cpp_info.system_libs = ["dl", "pthread"]
        # Auto-include the spec toolchain on find_package(khipu): this makes
        # khipu_add_spec() available in the consumer, wired to the PACKAGED
        # codegen + features (via khipu-tools.cmake -> KHIPU_TOOLCHAIN_ROOT).
        #
        # cmake_build_modules is ONLY honored when its containing directory
        # is also in cpp_info.builddirs -- CMakeDeps emits the include()
        # from the builddirs scan. Declaring the property without builddirs
        # silently does nothing ("Unknown CMake command khipu_add_spec").
        module_subdir = os.path.join("lib", "cmake", "khipu")
        self.cpp_info.builddirs = [module_subdir]
        self.cpp_info.set_property(
            "cmake_build_modules",
            [os.path.join(module_subdir, "khipu-tools.cmake")])
