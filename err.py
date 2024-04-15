from sys import stderr


def err(*args):
    print(*args, file=stderr)
