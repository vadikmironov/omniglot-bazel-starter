import cpp_py_ext_module as tcpext


def main() -> None:
    print(tcpext.get_hello_world_string_py_wrapper(3))
