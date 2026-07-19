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
        sha256 = "1409bc282d3bdb0826a9cc1fec9704f924264dbde282e2aa1e09027aed5d6df2",
        strip_prefix = "amazon-corretto-8.492.09.2-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/8.492.09.2/amazon-corretto-8.492.09.2-linux-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "b9a74845d1171eabd1482b43a759164efd529cf8317d7edc4484688b459c3a88",
        strip_prefix = "amazon-corretto-8.492.09.2-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/8.492.09.2/amazon-corretto-8.492.09.2-linux-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "4316bff4922d9799883e68f6b9d78a720663fd8f1664f74b005bb285eda0ca26",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.492.09.2/amazon-corretto-8.492.09.2-macosx-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "63cf32569fae961497091a77c763b3511b1e1650abc22a7e7a9ee38de8fc3567",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.492.09.2/amazon-corretto-8.492.09.2-macosx-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "eccce8d939f1abb9570812b09360a83eb4d0ec937e5bd2a78be158d8e6aeec2d",
        strip_prefix = "jdk1.8.0_492",
        urls = ["https://corretto.aws/downloads/resources/8.492.09.2/amazon-corretto-8.492.09.2-windows-x64-jdk.zip"],
        version = "8",
    ),
    # JDK 11 - https://github.com/corretto/corretto-11/releases
    struct(
        name = "remote_corretto_jdk11_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "8ee5fba821463363dc76a18049e338d12c74752430a743aa405af126a62218da",
        strip_prefix = "amazon-corretto-11.0.31.11.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/11.0.31.11.1/amazon-corretto-11.0.31.11.1-linux-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "70f6ff3668f27d1052f9e26c7a00d601774a556a49e6e9e7faa9d510ae1d0dbe",
        strip_prefix = "amazon-corretto-11.0.31.11.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/11.0.31.11.1/amazon-corretto-11.0.31.11.1-linux-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "e31cc1fd9b42bf40ec0682a027c024599ac1d84bf2447ab1f32b4caa94c08faa",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.31.11.1/amazon-corretto-11.0.31.11.1-macosx-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "ce278c17516502934179faff7e6d64aac0bab0e48633c792b59b70893b56a0e6",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.31.11.1/amazon-corretto-11.0.31.11.1-macosx-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "462f2a455d8f8da1a3a839a0f3de10c7a5fe6f7d230cf995e144a769382f4afe",
        strip_prefix = "jdk11.0.31_11",
        urls = ["https://corretto.aws/downloads/resources/11.0.31.11.1/amazon-corretto-11.0.31.11.1-windows-x64-jdk.zip"],
        version = "11",
    ),
    # JDK 17 - https://github.com/corretto/corretto-17/releases
    struct(
        name = "remote_corretto_jdk17_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "1b9f75b5a2f740ab3305577858e2fc87dad827b60678d4573234d6357be59fa8",
        strip_prefix = "amazon-corretto-17.0.19.10.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/17.0.19.10.1/amazon-corretto-17.0.19.10.1-linux-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "d0f1b880445691425511c3aa62cb89889f03a71c2a43597a3df174fc01d3f3a0",
        strip_prefix = "amazon-corretto-17.0.19.10.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/17.0.19.10.1/amazon-corretto-17.0.19.10.1-linux-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "3ba2ab957f60e33c6164d7330b1f6c9f48b5ffd60e4cc9bbcc67def319c29a29",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.19.10.1/amazon-corretto-17.0.19.10.1-macosx-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "6d3b3e367e1a77b9867bc1b5aa925b1f05d76a0ec62b075e375fa91fdcea0e93",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.19.10.1/amazon-corretto-17.0.19.10.1-macosx-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "ab748d9814d99a848916b54b36ae0f1d104493e61a19e1887072b4db9802c6ac",
        strip_prefix = "jdk17.0.19_10",
        urls = ["https://corretto.aws/downloads/resources/17.0.19.10.1/amazon-corretto-17.0.19.10.1-windows-x64-jdk.zip"],
        version = "17",
    ),
    # JDK 21 - https://github.com/corretto/corretto-21/releases
    # Note: Linux uses 21.0.11.10.1, macOS/Windows use 21.0.11.10.1
    struct(
        name = "remote_corretto_jdk21_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "bc419602d71d819bce147239fbdc48bfbc900fa1d60693537fb9a22bd6b86475",
        strip_prefix = "amazon-corretto-21.0.11.10.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/21.0.11.10.1/amazon-corretto-21.0.11.10.1-linux-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "5b4dc8817df13f88f9bfc434e5d018adb535889ff2fe0ccf758bcebcc216f394",
        strip_prefix = "amazon-corretto-21.0.11.10.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/21.0.11.10.1/amazon-corretto-21.0.11.10.1-linux-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "c6c9ba09ef0ae741aa04cfbd5ef8a6b75dd2d26034a1de0808ee7976a04446ea",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.11.10.1/amazon-corretto-21.0.11.10.1-macosx-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "fb08b09af67ca930d6868405263259d5e43faab89216f6886780e544fd700f00",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.11.10.1/amazon-corretto-21.0.11.10.1-macosx-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "5d63fdb5a19393081919afc0daa4ce82a7fadcced569981a995529caed28fb14",
        strip_prefix = "jdk21.0.11_10",
        urls = ["https://corretto.aws/downloads/resources/21.0.11.10.1/amazon-corretto-21.0.11.10.1-windows-x64-jdk.zip"],
        version = "21",
    ),
    # JDK 25 - https://github.com/corretto/corretto-25/releases
    # Note: Linux uses 25.0.3.9.1, macOS/Windows use 25.0.3.9.1
    struct(
        name = "remote_corretto_jdk25_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "8b1fd78bbd1f188f3884f580be674727174635252c0d4d6dfa7cd15de51879ce",
        strip_prefix = "amazon-corretto-25.0.3.9.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/25.0.3.9.1/amazon-corretto-25.0.3.9.1-linux-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "00486fa402136f8d40512b101c645dd4db9be2b5535171530ad241cd96c1223d",
        strip_prefix = "amazon-corretto-25.0.3.9.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/25.0.3.9.1/amazon-corretto-25.0.3.9.1-linux-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "614107ed76e9fb86d62d8cf2686a9cc4b3a11c019502ca3ba605fc5d51f4d7bb",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.3.9.1/amazon-corretto-25.0.3.9.1-macosx-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "0cfef7feb0f4d7d352881b08d527c22840b8fb5eaaa7552b25619edb449d6d94",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.3.9.1/amazon-corretto-25.0.3.9.1-macosx-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "3404a8be08f0fdbbd24c9bbdda79ba1ded87b264a833247b2124ac45da1c16e0",
        strip_prefix = "jdk25.0.3_9",
        urls = ["https://corretto.aws/downloads/resources/25.0.3.9.1/amazon-corretto-25.0.3.9.1-windows-x64-jdk.zip"],
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
