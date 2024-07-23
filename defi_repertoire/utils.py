def flatten(matrix):
    flat_list = []
    for row in matrix:
        flat_list += row
    return flat_list


def uniqBy(l, attr):
    seen = {}
    for obj in l:
        if obj[attr] not in seen:
            seen[obj[attr]] = obj
    return list(seen.values())
