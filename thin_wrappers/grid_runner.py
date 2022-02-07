import numpy as np
from tqdm.contrib.concurrent import process_map
"""This code is copied from the scipy.optimizer module with minimal modifications
"""


class _Brute_Wrapper(object):
    """
    Object to wrap user cost function for optimize.brute, allowing picklability
    """

    def __init__(self, f, args):
        self.f = f
        self.args = [] if args is None else args

    def __call__(self, x):
        # flatten needed for one dimensional case.
        return self.f(np.asarray(x).flatten(), *self.args)


def build_grid_from_slice_tuple(ranges, Ns=20):
    N = len(ranges)
    if N > 40:
        raise ValueError("Brute Force not possible with more "
                         "than 40 variables.")
    lrange = list(ranges)
    for k in range(N):
        if type(lrange[k]) is not type(slice(None)):
            if len(lrange[k]) < 3:
                lrange[k] = tuple(lrange[k]) + (complex(Ns),)
            lrange[k] = slice(*lrange[k])
    if (N == 1):
        lrange = lrange[0]

    grid = np.mgrid[lrange]

    # obtain an array of parameters that is iterable by a map-like callable
    inpt_shape = grid.shape
    if (N > 1):
        grid = np.reshape(grid, (inpt_shape[0], np.prod(inpt_shape[1:]))).T

    return grid


def grid_evaluator(func, ranges=None, args=(), Ns=20, full_output=True, finish=None, disp=False, workers=1, grid=None, chunksize=20, wrap_func=True):

    if wrap_func:
        wrapped_func = _Brute_Wrapper(func, args)
    else:
        wrapped_func = func

    # iterate over input arrays, possibly in parallel
    if grid is None:
        grid = build_grid_from_slice_tuple(ranges)

    # TODO: chunksize could be set dynamically
    Jout = process_map(wrapped_func, grid,
                       max_workers=workers, chunksize=chunksize)
    return grid, Jout
