from sys import stderr


def err(*args):
    print(*args, file=stderr)


def silent(*args):
    pass
