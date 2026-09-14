"""Client code for the Wayland protocol XML files SDL ships in wayland-protocols/.

SDL loads libwayland-client at runtime, so the protocol tables (wayland.xml
included) are compiled into SDL itself, as SDL's CMake build does. The list
of protocols is whatever the SDL source tree contains: the BUILD file globs
wayland-protocols/*.xml and passes it here.

The headers are generated at the package root: SDL includes them with
quotes, and Bazel searches the package's output directory for quoted
includes before any include path, so SDL's own wayland-client-protocol.h
(from its newer wayland.xml) wins over the one the wayland module exports.
"""

def wayland_protocol_sources(xmls):
    """Declares the wayland-scanner genrules for `xmls`.

    Returns a struct with `srcs` (the generated *-protocol.c files) and `hdrs`
    (the generated *-client-protocol.h files).
    """
    srcs = []
    hdrs = []
    for xml in xmls:
        protocol = xml.removeprefix("wayland-protocols/").removesuffix(".xml")
        src = "%s-protocol.c" % protocol
        hdr = "%s-client-protocol.h" % protocol
        native.genrule(
            name = "%s_wayland_protocol_source" % protocol,
            srcs = [xml],
            outs = [src],
            cmd = "$(location @wayland//:wayland_scanner) private-code < $(location %s) > $@" % xml,
            tools = ["@wayland//:wayland_scanner"],
            # Keeps `...` from analysing the scanner elsewhere; the Wayland
            # backend is Linux-only anyway.
            target_compatible_with = ["@platforms//os:linux"],
        )
        native.genrule(
            name = "%s_wayland_protocol_header" % protocol,
            srcs = [xml],
            outs = [hdr],
            cmd = "$(location @wayland//:wayland_scanner) client-header < $(location %s) > $@" % xml,
            tools = ["@wayland//:wayland_scanner"],
            # Keeps `...` from analysing the scanner elsewhere; the Wayland
            # backend is Linux-only anyway.
            target_compatible_with = ["@platforms//os:linux"],
        )
        srcs.append(src)
        hdrs.append(hdr)
    return struct(srcs = srcs, hdrs = hdrs)
