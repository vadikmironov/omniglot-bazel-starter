"""
Helper module extension to configure all remote Amazon Corretto JDKs at once.
"""

load("@bazel_tools//tools/build_defs/repo:utils.bzl", "maybe")
load("@rules_java//toolchains:remote_java_repository.bzl", "remote_java_repository")

# Amazon Corretto JDK configurations
# Update these entries from the respective GitHub releases pages:
# - JDK 8: https://github.com/corretto/corretto-8/releases
# - JDK 11: https://github.com/corretto/corretto-11/releases
# - JDK 17: https://github.com/corretto/corretto-17/releases
# - JDK 21: https://github.com/corretto/corretto-21/releases
# - JDK 25: https://github.com/corretto/corretto-25/releases

_REMOTE_CORRETTO_JDK_CONFIGS_LIST = [
    # JDK 8 - https://github.com/corretto/corretto-8/releases
    struct(
        name = "remote_corretto_jdk8_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "13c732b6f7ed1d024fa896b45de74f24bb5eacd9c7ceab8f2aee69c4260325e8",
        strip_prefix = "amazon-corretto-8.472.08.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/8.472.08.1/amazon-corretto-8.472.08.1-linux-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "f5df7b2bd46bff618b504d61acd68de7dd2f8a0e158f71bf672486d290e6b763",
        strip_prefix = "amazon-corretto-8.472.08.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/8.472.08.1/amazon-corretto-8.472.08.1-linux-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "c95ea0715560d9dc20cdd52a839972f96b2ca0a1f6c0e1f55121518bb3d703f6",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.472.08.1/amazon-corretto-8.472.08.1-macosx-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "81f00539702a58491fd819d13f654253ab523dc45881b3c38e204756e3974339",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.472.08.1/amazon-corretto-8.472.08.1-macosx-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "3dcfcf807e3f7d5b06322b1fa9638a6adc66a1d4963f3d5db385594140268a83",
        strip_prefix = "jdk1.8.0_472",
        urls = ["https://corretto.aws/downloads/resources/8.472.08.1/amazon-corretto-8.472.08.1-windows-x64-jdk.zip"],
        version = "8",
    ),
    # JDK 11 - https://github.com/corretto/corretto-11/releases
    struct(
        name = "remote_corretto_jdk11_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "941b8dfd624aea81b0e9ca3d07b44b37c5d2999af9105e35b180a853a31771c4",
        strip_prefix = "amazon-corretto-11.0.29.7.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/11.0.29.7.1/amazon-corretto-11.0.29.7.1-linux-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "279c6d3124f8b0251b16297b16687fe8b3946410b05ed27de1259b5e5cea02ba",
        strip_prefix = "amazon-corretto-11.0.29.7.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/11.0.29.7.1/amazon-corretto-11.0.29.7.1-linux-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "3fcf93300022d20f6a460221cba0a4c7337679b777699409f2db4d20ae9b69b5",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.29.7.1/amazon-corretto-11.0.29.7.1-macosx-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "8082372d91e6c131c1cfc0159897f1e0a308aff00ea8232a52bfb37e8c07c9df",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.29.7.1/amazon-corretto-11.0.29.7.1-macosx-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "33471ed251e1b59d29e75ea4c12027f00f94eae90ed8e584dbe4bf3291f5ac2c",
        strip_prefix = "jdk11.0.29_7",
        urls = ["https://corretto.aws/downloads/resources/11.0.29.7.1/amazon-corretto-11.0.29.7.1-windows-x64-jdk.zip"],
        version = "11",
    ),
    # JDK 17 - https://github.com/corretto/corretto-17/releases
    struct(
        name = "remote_corretto_jdk17_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "31b08051e647044da8ea201744becdbc76e05b807d45e68636f765e15fd830ae",
        strip_prefix = "amazon-corretto-17.0.17.10.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/17.0.17.10.1/amazon-corretto-17.0.17.10.1-linux-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "ce991faba33be89046b03518e2c971f892a279570bc09f700b363282db1ac552",
        strip_prefix = "amazon-corretto-17.0.17.10.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/17.0.17.10.1/amazon-corretto-17.0.17.10.1-linux-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "61483f311a03c44dace8a7b2564aa3ed05f847b0c0c890dc390a4b9bf53342cb",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.17.10.1/amazon-corretto-17.0.17.10.1-macosx-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "e0c0454f3e17a98d0f1fc1263c6d213e45549f2600b174900bff4b31de5a4c23",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.17.10.1/amazon-corretto-17.0.17.10.1-macosx-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "2503f1dc9bd6f50d6a68ad20c282ad092751fc1cd7e993680e6e151119a9a4bf",
        strip_prefix = "jdk17.0.17_10",
        urls = ["https://corretto.aws/downloads/resources/17.0.17.10.1/amazon-corretto-17.0.17.10.1-windows-x64-jdk.zip"],
        version = "17",
    ),
    # JDK 21 - https://github.com/corretto/corretto-21/releases
    # Note: Linux uses 21.0.9.11.1, macOS/Windows use 21.0.9.10.1
    struct(
        name = "remote_corretto_jdk21_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "c324b1d502dcd9375e2290a9b8da20345b972ba8a9b95bd3305faec2a5611139",
        strip_prefix = "amazon-corretto-21.0.9.11.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/21.0.9.11.1/amazon-corretto-21.0.9.11.1-linux-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "e00963dffc5ab6bf1970b302772bafa40d0065700e13b152bf25d6e2a31c3aa5",
        strip_prefix = "amazon-corretto-21.0.9.11.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/21.0.9.11.1/amazon-corretto-21.0.9.11.1-linux-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "b6400ac47dd93a98e5191dc8b3e87a412390ecdc0b42a1b6105069f3c76a290c",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.9.10.1/amazon-corretto-21.0.9.10.1-macosx-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "4ba0214d8166f88b78e102b8d99411666a6551be4382dd2e3c347d8752c13a54",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.9.10.1/amazon-corretto-21.0.9.10.1-macosx-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "77226707f66b0c19a5baeb2c176ff5cc1c7d0f2a9f67f52354ce2901a53b9240",
        strip_prefix = "jdk21.0.9_10",
        urls = ["https://corretto.aws/downloads/resources/21.0.9.10.1/amazon-corretto-21.0.9.10.1-windows-x64-jdk.zip"],
        version = "21",
    ),
    # JDK 25 - https://github.com/corretto/corretto-25/releases
    # Note: Linux uses 25.0.1.9.1, macOS/Windows use 25.0.1.8.1
    struct(
        name = "remote_corretto_jdk25_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "a705c0613d3ede002ed1e172d30bf6041070f9eb091515f96aed7b9832c5fc54",
        strip_prefix = "amazon-corretto-25.0.1.9.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/25.0.1.9.1/amazon-corretto-25.0.1.9.1-linux-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "8c1c0da1de121ce3570c5c84f92bf13cbc5a294a1fb0bb694dfa7e408d0af228",
        strip_prefix = "amazon-corretto-25.0.1.9.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/25.0.1.9.1/amazon-corretto-25.0.1.9.1-linux-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "8ae7d9b2292bca1f78ba736572c0e8129eb4f5914d6d63015c31529da16cf458",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.1.8.1/amazon-corretto-25.0.1.8.1-macosx-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "0d83fa831649d69d91ddee2fd8ee9f576b76b6502e6609c5d9d540fbc4340c32",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.1.8.1/amazon-corretto-25.0.1.8.1-macosx-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "f183944b2e0b857f6f8617a272e74aac2f444080df5f159bcc4443c416fa8eb6",
        strip_prefix = "jdk25.0.1_8",
        urls = ["https://corretto.aws/downloads/resources/25.0.1.8.1/amazon-corretto-25.0.1.8.1-windows-x64-jdk.zip"],
        version = "25",
    ),
]

def _remote_corretto_toolchains_impl(_):
    for config in _REMOTE_CORRETTO_JDK_CONFIGS_LIST:
        maybe(
            remote_java_repository,
            name = config.name,
            prefix = "remote_corretto",
            version = config.version,
            target_compatible_with = config.target_compatible_with,
            sha256 = config.sha256,
            strip_prefix = config.strip_prefix,
            urls = config.urls,
        )

remote_corretto_toolchains = module_extension(
    implementation = _remote_corretto_toolchains_impl,
)
