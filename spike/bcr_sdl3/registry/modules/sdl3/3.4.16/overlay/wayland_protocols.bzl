"""Client code for the Wayland protocol XML files SDL ships in wayland-protocols/.

SDL loads libwayland-client at runtime, so the protocol tables (wayland.xml
included) are compiled into SDL itself, as SDL's CMake build does. The list
of protocols is whatever the SDL source tree contains: the BUILD file globs
wayland-protocols/*.xml and passes it here.
"""

_OUT_DIR = "generated/wayland-protocols"

def wayland_protocol_sources(xmls):
    """Declares the wayland-scanner genrules for `xmls`.

    Returns a struct with `srcs` (the generated *-protocol.c files) and `hdrs`
    (the generated *-client-protocol.h files); both live under generated/wayland-protocols.
    """
    srcs = []
    hdrs = []
    for xml in xmls:
        protocol = xml.removeprefix("wayland-protocols/").removesuffix(".xml")
        src = "%s/%s-protocol.c" % (_OUT_DIR, protocol)
        hdr = "%s/%s-client-protocol.h" % (_OUT_DIR, protocol)
        native.genrule(
            name = "%s_wayland_protocol_source" % protocol,
            srcs = [xml],
            outs = [src],
            cmd = "$(location @wayland//:wayland_scanner) private-code < $(location %s) > $@" % xml,
            tools = ["@wayland//:wayland_scanner"],
        )
        native.genrule(
            name = "%s_wayland_protocol_header" % protocol,
            srcs = [xml],
            outs = [hdr],
            cmd = "$(location @wayland//:wayland_scanner) client-header < $(location %s) > $@" % xml,
            tools = ["@wayland//:wayland_scanner"],
        )
        srcs.append(src)
        hdrs.append(hdr)
    return struct(srcs = srcs, hdrs = hdrs, include_dir = _OUT_DIR)
