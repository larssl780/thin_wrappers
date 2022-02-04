
"""A thin wrapper around pickleshare that is helpful for persistent caching of functions
    
Simple usage example:

from core_analytics.data_handling import file_based_caching as fcache

def test(a=2, b=3, refresh=False):
    ck = fcache.create_cache_key(locals(), fcache.current_function_name())
    
    datum = fcache.extract_cache_data(ck, refresh=refresh)

    if datum is None:
        rv = other_func(a, b)
        fcache.set_gp_cache(ck, datum)
        return rv

    else:
        return datum
    

"""
import inspect
import pickleshare


def set_gp_cache(key, value):
    """
    this could also check if value is different from existing and only write if it's not the same...
    """

    cache = pickleshare.PickleShareDB('py_function_cache')
    
    cache[key] = value


def extract_cache_data(cache_key, refresh=False):
    """
    convenient wrapper
    if refresh true or nothing in cache, function doesn't return anything, and the wrapping function can continue running
    """
    if refresh:
        return None
    cache = pickleshare.PickleShareDB('py_function_cache')
    if cache_key in cache.keys():
        return cache[cache_key]
    else:
        return None


def current_function_name(idx=1):

    failing = True

    while failing:
        try:
            rv = inspect.stack()[idx][3]
            failing = False
        except IndexError:
            failing = True
            print('Failing to read the function name!?')
    return rv


def create_cache_key(args, func_name=None, **kwargs):
    """Caller is responsible for checking path is not too long...
    It's not straightforward to programmatically check the length (we can't just cut of the path at element x, 
        since we could then run the risk of returning different rvs for different arguments...)
    """

    if func_name is None:
        func_name = current_function_name(2)
    path = func_name
    for key, el in args.items():
        if key != 'refresh':
            path += '|%s' % str(el)
    for value in kwargs.values():
        path += '|%s' % str(value)

    assert len(path) <= 255, "Path used for caching is likely too long, pls consider using session-based-caching instead (no cache key length restrictions!)"
    return path
