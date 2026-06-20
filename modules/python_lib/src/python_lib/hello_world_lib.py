DEFAULT_LEVEL = 0


def get_hello_world_string(level: int = DEFAULT_LEVEL) -> str:
    if level == 1:
        return "Hello, Star!"
    elif level == 2:
        return "Hello, Superstar!"
    else:
        return "Hello, World!"
