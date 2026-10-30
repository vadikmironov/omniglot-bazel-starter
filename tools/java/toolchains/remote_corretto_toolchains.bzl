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
        sha256 = "0115aad5747b262c7ae0e7f3ae1fc20933f3950843cfa365b49eca7be0c84a90",
        strip_prefix = "amazon-corretto-8.512.09.1-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/8.512.09.1/amazon-corretto-8.512.09.1-linux-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "2f2df938886e61c80010ed5af0ea6504ca685280a3b807c5c59ed3ca4fb95be4",
        strip_prefix = "amazon-corretto-8.512.09.1-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/8.512.09.1/amazon-corretto-8.512.09.1-linux-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "30c7edb7134712148cc323d4ccfc816758e7f1e4bb8aa1287795872fa5eca610",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.512.09.1/amazon-corretto-8.512.09.1-macosx-aarch64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "adfbe1c7a47ee98fe70f8028087614c93c137a2a54d8b010313104ef0325b656",
        strip_prefix = "amazon-corretto-8.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/8.512.09.1/amazon-corretto-8.512.09.1-macosx-x64.tar.gz"],
        version = "8",
    ),
    struct(
        name = "remote_corretto_jdk8_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "9c8d155623ad7d257e5ecf57452022ee12a7fef839195e8fb963e85d69598a7e",
        strip_prefix = "jdk1.8.0_512",
        urls = ["https://corretto.aws/downloads/resources/8.512.09.1/amazon-corretto-8.512.09.1-windows-x64-jdk.zip"],
        version = "8",
    ),
    # JDK 11 - https://github.com/corretto/corretto-11/releases
    struct(
        name = "remote_corretto_jdk11_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "ada21539d4959e8946b20b55a2c868a006d4b993be0633c576e3d38c8b9d0c1c",
        strip_prefix = "amazon-corretto-11.0.33.0.10-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/11.0.33.0.10/amazon-corretto-11.0.33.0.10-linux-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "f368ac379f3b20e266080e80fcc1f5e8567d044a4f895c8786220cab5b580c15",
        strip_prefix = "amazon-corretto-11.0.33.0.10-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/11.0.33.0.10/amazon-corretto-11.0.33.0.10-linux-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "94dfe3dce2a508a5e0e3c67c75feb2ad580531c0dfd66ef46db17e0a8b08a338",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.33.0.10/amazon-corretto-11.0.33.0.10-macosx-aarch64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "96a4ffe772ffc62bdc7892720ff23935b6b888d8b05273dadf191f2e0410bd04",
        strip_prefix = "amazon-corretto-11.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/11.0.33.0.10/amazon-corretto-11.0.33.0.10-macosx-x64.tar.gz"],
        version = "11",
    ),
    struct(
        name = "remote_corretto_jdk11_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "1a65d64b7837bb7439f4e3973531e50c9c52da737385066d771b52d2db461d80",
        strip_prefix = "jdk11.0.33_0",
        urls = ["https://corretto.aws/downloads/resources/11.0.33.0.10/amazon-corretto-11.0.33.0.10-windows-x64-jdk.zip"],
        version = "11",
    ),
    # JDK 17 - https://github.com/corretto/corretto-17/releases
    struct(
        name = "remote_corretto_jdk17_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "33412bba53b912b21528150df7cf60c161d10fc3b7dae89cd5383d8f3c0362c0",
        strip_prefix = "amazon-corretto-17.0.21.0.11-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/17.0.21.0.11/amazon-corretto-17.0.21.0.11-linux-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "8f9a2ddb131ec5317419f2b0769240fe22ce27f8a0ae43f5346d53e1c8aec6a0",
        strip_prefix = "amazon-corretto-17.0.21.0.11-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/17.0.21.0.11/amazon-corretto-17.0.21.0.11-linux-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "3cd5a2bdd380a5654aa1ef5eda3032f60021e8e48a0bdd552e8e39b032705732",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.21.0.11/amazon-corretto-17.0.21.0.11-macosx-aarch64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "dca4175d94d404533c4230eff1a64cc3ae9f3919bfdf35902c64bfd4d3bcb70e",
        strip_prefix = "amazon-corretto-17.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/17.0.21.0.11/amazon-corretto-17.0.21.0.11-macosx-x64.tar.gz"],
        version = "17",
    ),
    struct(
        name = "remote_corretto_jdk17_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "59d6514305f6fab3b18955fb17185562f0a0bbf20e1466eda33a5429f3b31618",
        strip_prefix = "jdk17.0.21_0",
        urls = ["https://corretto.aws/downloads/resources/17.0.21.0.11/amazon-corretto-17.0.21.0.11-windows-x64-jdk.zip"],
        version = "17",
    ),
    # JDK 21 - https://github.com/corretto/corretto-21/releases
    struct(
        name = "remote_corretto_jdk21_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "0985275871a6e064324f46f52c5cd89d45013c830e10a41539f6fd7f450808e9",
        strip_prefix = "amazon-corretto-21.0.13.0.11-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/21.0.13.0.11/amazon-corretto-21.0.13.0.11-linux-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "f3330bf440b8f4514b7b279b6145d4b4493dea9dda5f3a702b49c53c41bec1e4",
        strip_prefix = "amazon-corretto-21.0.13.0.11-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/21.0.13.0.11/amazon-corretto-21.0.13.0.11-linux-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "f4ee9236ffc3ddcd37da877e04a1ab74b3d3376cf9e4287b5426f4749cc869a9",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.13.0.11/amazon-corretto-21.0.13.0.11-macosx-aarch64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "12cf7651ba1f2fd04357d5277b0d58a78a7df5d672bc7cfc085ccb0d60c4bc8c",
        strip_prefix = "amazon-corretto-21.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/21.0.13.0.11/amazon-corretto-21.0.13.0.11-macosx-x64.tar.gz"],
        version = "21",
    ),
    struct(
        name = "remote_corretto_jdk21_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "2245721d8cec120ebddf60a6981a13baa89d82997dab621a0ee6a5849beee233",
        strip_prefix = "jdk21.0.13_0",
        urls = ["https://corretto.aws/downloads/resources/21.0.13.0.11/amazon-corretto-21.0.13.0.11-windows-x64-jdk.zip"],
        version = "21",
    ),
    # JDK 25 - https://github.com/corretto/corretto-25/releases
    struct(
        name = "remote_corretto_jdk25_linux_aarch64",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:aarch64"],
        sha256 = "8dc8e5379959c0814e99785b53657c35800b74950fc9fa39738d26153b62ef6c",
        strip_prefix = "amazon-corretto-25.0.5.0.10-linux-aarch64",
        urls = ["https://corretto.aws/downloads/resources/25.0.5.0.10/amazon-corretto-25.0.5.0.10-linux-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_linux",
        target_compatible_with = ["@platforms//os:linux", "@platforms//cpu:x86_64"],
        sha256 = "1d89b4194f20ee513f4dd9fc2aadd038de3c713c37fd444d77566b3da7b0ee65",
        strip_prefix = "amazon-corretto-25.0.5.0.10-linux-x64",
        urls = ["https://corretto.aws/downloads/resources/25.0.5.0.10/amazon-corretto-25.0.5.0.10-linux-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos_aarch64",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:aarch64"],
        sha256 = "0da6df8bf4f849939951089e1d10f9fea5df82a7da9f66434f6c2b31c497fe75",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.5.0.10/amazon-corretto-25.0.5.0.10-macosx-aarch64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_macos",
        target_compatible_with = ["@platforms//os:macos", "@platforms//cpu:x86_64"],
        sha256 = "e580a91b30fe723f3bdefcc297722d6e373a52d9a427748bcc38cdd3237ada15",
        strip_prefix = "amazon-corretto-25.jdk/Contents/Home",
        urls = ["https://corretto.aws/downloads/resources/25.0.5.0.10/amazon-corretto-25.0.5.0.10-macosx-x64.tar.gz"],
        version = "25",
    ),
    struct(
        name = "remote_corretto_jdk25_windows",
        target_compatible_with = ["@platforms//os:windows", "@platforms//cpu:x86_64"],
        sha256 = "4da11ba50a52e4fe7e99f30c3103e5e41314d5dcabe6fe768ff9f68e55466139",
        strip_prefix = "jdk25.0.5_0",
        urls = ["https://corretto.aws/downloads/resources/25.0.5.0.10/amazon-corretto-25.0.5.0.10-windows-x64-jdk.zip"],
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
