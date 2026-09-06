`setup_linux` fetched a version-pinned `libtinfo5` .deb by URL:

```
wget -c .../pool/universe/n/ncurses/libtinfo5_6.3-2ubuntu0.2_amd64.deb
HTTP request sent, awaiting response... 404 Not Found
```

Ubuntu rotated `6.3-2ubuntu0.2` out of the pool in favour of `0.3`, so the
download 404s and every Linux job fails in setup, before Bazel starts. It is
currently intermittent only because `security.ubuntu.com` round-robins across
mirrors mid-sync; it becomes universal once that settles.

This is the second time the pin has gone stale — #43 bumped it from
`0.1` to `0.2` for the same reason.

## Why delete rather than bump

Nothing needs the package. `DT_NEEDED` for every tool CI uses:

| binary | needs |
| --- | --- |
| `clang-tidy`, `clang-format`, `llvm-cov` | libm, libz, libstdc++, libgcc_s, libc |
| `ld.lld` | the same, plus libxml2 |
| hermetic GCC 15.2.0, xPack GCC, remote clang | no libtinfo |
| `lldb-dap`, `lldb-mcp` | `libtinfo.so.6` — shipped by the runner image, and CI does not use lldb |

Older LLVM releases linked `libtinfo.so.5`, which is where the step came from;
22.1.8 does not. A successful install of an unnecessary package looks exactly
like a necessary one, so it went unnoticed.

Bumping the pin would buy a few months and recur. Deleting removes the pin, the
`wget` on the critical path of every Linux job, and the failure mode.
