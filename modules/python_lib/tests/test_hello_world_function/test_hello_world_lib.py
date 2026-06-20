import unittest

import python_lib as tpl


class HelloWorldTest(unittest.TestCase):
    def test_hello_world_string(self) -> None:
        self.assertEqual(tpl.get_hello_world_string(), "Hello, World!")
        self.assertEqual(tpl.get_hello_world_string(1), "Hello, Star!")
        self.assertEqual(tpl.get_hello_world_string(3), "Hello, World!")
        self.assertNotEqual(tpl.get_hello_world_string(), "Not Hello, World!")


if __name__ == "__main__":
    unittest.main()
