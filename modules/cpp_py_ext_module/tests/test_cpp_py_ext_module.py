import unittest

import cpp_py_ext_module as tcpext


class HelloWorldTest(unittest.TestCase):
    def test_hello_world_string(self) -> None:
        self.assertEqual(tcpext.get_hello_world_string_py_wrapper(), "Hello, World!")
        self.assertEqual(tcpext.get_hello_world_string_py_wrapper(1), "Hello, Star!")
        self.assertEqual(tcpext.get_hello_world_string_py_wrapper(3), "Hello, World!")
        self.assertNotEqual(tcpext.get_hello_world_string_py_wrapper(), "Not Hello, World!")

    def test_invocation_count(self) -> None:
        initial_count = tcpext.get_invocation_count()
        self.assertIsInstance(initial_count, int)
        self.assertGreaterEqual(initial_count, 0)

        for _ in range(5):
            tcpext.get_hello_world_string_py_wrapper()

        new_count = tcpext.get_invocation_count()
        self.assertEqual(new_count, initial_count + 5)


if __name__ == "__main__":
    unittest.main()
