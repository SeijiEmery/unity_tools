import os


def search_filesystem(search_paths, predicate, blacklist,
                      visited=None, recursion_depth_limit=None):
    if visited is None:
        visited = set()

    if type(search_paths) == str:
        search_paths = (search_paths,)

    unvisited = list()
    under_recursion_limit = \
        lambda x: True if recursion_depth_limit is None else \
        lambda x: x < recursion_depth_limit

    can_recurse = under_recursion_limit(0)
    for path in search_paths:
        if path in visited:
            continue
        if predicate(path):
            yield path
        elif can_recurse and os.path.isdir(path):
            unvisited.append((path, 1))

    while len(unvisited) > 0:
        search_path, depth = unvisited.pop()
        can_recurse = under_recursion_limit(depth)
        # print(type(search_path), search_path, depth, can_recurse)
        for file in os.listdir(search_path):
            # print("visiting '%s'" % search_path)
            path = os.path.join(search_path, file)
            if path in visited:
                # print("skippping '%s'" % path)
                continue
            if predicate(path):
                # print("returning '%s'" % path)
                yield path
            elif can_recurse and os.path.isdir(path) \
                    and not blacklist(file, path):
                unvisited.append((path, depth + 1))
