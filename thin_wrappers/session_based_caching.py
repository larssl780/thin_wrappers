
import sys
import functools
if sys.version_info >= (3, 0):
    global cache_storage 
    cache_storage = {}
import inspect

# would be nice to have generic names, ie user could set the name of the global variable in his session
# the global variable is only global in the current session, ie. you can't get to the data from a different terminal session for example
# we could maybe use __file__ (ie. pass that in from the calling library, and then name the global variable by that?)
# another idea is to clean out the cache once we recache a function when its signature changes (because then the old data is never used again anyway)


def extract_cache_data(cache_key, refresh):
    """
    convenient wrapper
    if refresh true or nothing in cache, function doesn't return anything, and the wrapping function can continue running
    """
    if not refresh:
        # pdb.set_trace()
        tmp = read_from_gp_cache(cache_key)
        if tmp.get('success', False):
            return tmp['rv']
        else:
            # obviously this isn't foolproof:
            return None


def check_storage():
    
    global cache_storage
    cache_storage = {}
    

def delete_from_cache(cache_key):
    if cache_key in cache_storage:
        del cache_storage[cache_key]
    else:
        print('Nothing to delete')


def read_from_gp_cache(cache_key, dump_all=False):
    """
    the beautiful idea here is that we cache things in global variables. This is very useful in an ipython session, 
    since then, even if you reload this library (eg. after adding new code), the global variables will stay untouched, so you 
    don't need to recalculate them. You can burn through memory of course, but just be careful where you use it and you'll be fine.
    gp is for general purpose

    """

    try:
        type(cache_storage)
    except:
        cache_storage()

    if dump_all:
        return cache_storage
    if cache_key in cache_storage:
        return {'success': True, 'rv': cache_storage[cache_key]}
    else:
    
        return {'success': False}

    

def current_storage():
    try:
        check_storage()
        

    except NameError:
        global cache_storage
        cache_storage = {}
    
    return cache_storage   


def create_cache_key(args, func_name=None, **kwargs):
    """ prolly better with a nested structure, but for now, use a string key
    the purpose of the keyword args are this:
    typically you would use locals() for args, but then we can top up with any keyword we want (for example 
    we pass in as_of_date=None, and then if it's set to None we use today's date, and in this way we get the function
    to update when we want it to, eg. when we call it next day)
    """
    if func_name is None:
        func_name = current_function_name(2)
    path = func_name
    for key, el in args.items():
        if key not in ['refresh', 'session']:
            path += '|%s' % str(el)
    for value in kwargs.values():
        path += '|%s' % str(value)    
    return path


def set_gp_cache(cache_key, cache_val, overwrite=False):
    
    if path_exists(cache_storage, cache_key) and (not overwrite):
        return None
    else:
        cache_storage[cache_key] = cache_val


def path_exists(dataDict, path):
    return not getFromDict(dataDict, path) is None


def getFromDict(dataDict, path, def_val=None):
    try:
        return functools.reduce(lambda d, k: d[k], path, dataDict)
    except (IndexError, KeyError):
        return def_val


def setInDict(dataDict, path, value):
    getFromDict(dataDict, path[:-1])[path[-1]] = value


def current_function_name(idx=1):

    # pdb.set_trace()
    failing = True

    while failing:
        try:
            rv = inspect.stack()[idx][3]
            failing = False
        except IndexError:
            failing = True
            print('Failing to read the function name!?')
    return rv