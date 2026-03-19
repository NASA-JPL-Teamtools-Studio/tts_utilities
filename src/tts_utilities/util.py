def as_list(x):
    """
    Simple utility to ensure that items that need to be treated as list-like
    are in fact, lists.

    :param x: list-like object
    :type x: list-like
    """
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [x]
    if hasattr(x, '__iter__'):
        return list(x)
    return [x]
