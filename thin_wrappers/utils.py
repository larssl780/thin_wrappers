import os
import io
import pandas as pd
import sys
import tempfile
import webbrowser
from functools import lru_cache
import zipfile
import requests
import datetime
import bisect
import re
import numpy as np
import plotly.express as pex
try:
    import numpy_ext as npext
except ImportError:
    npext = None
import functools
try:
    # these are used with rolling apply if one wants concurrency, not used by default
    from joblib import Parallel, delayed
except ImportError:
    Parallel = None
    delayed = None
    pass


def year_frac(dt1, dt2):
    if isinstance(dt1, str):
        dt1 = pd.to_datetime(dt1)
    elif isinstance(dt1, pd.Timestamp):
        dt1 = dt1.normalize()
    if isinstance(dt2, str):
        dt2 = pd.to_datetime(dt2)
    elif isinstance(dt2, pd.Timestamp):
        dt2 = dt2.normalize()
    return (dt2 - dt1) / np.timedelta64(1, 'Y')


def query_yes_no(question, default="yes"):
    """(this is copied from somewhere, )
    Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    """
    valid = {"yes": "yes", "y": "yes", "ye": "yes",
             "no": "no", "n": "no"}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while 1:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return default
        elif choice in valid.keys():
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def display_sortable_table(df, title='', header_size=1, filename=None, sort_on_col=None, ascending=True, file_post_process_func=None, autosort=False, display=True):
    """
    if filename is set, we also write the stuff to file
    """

    df = df.copy()
    if autosort:
        n = len(df.columns) + 1
        df['__'] = range(len(df))
        sort_on_col = n
    boilerplate = '<html><head><script type="text/javascript" language="javascript" src="https://code.jquery.com/jquery-3.5.1.js"></script>'
    boilerplate += '<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.22/css/jquery.dataTables.css">'
    boilerplate += '<script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.22/js/jquery.dataTables.js"></script>'
    boilerplate += '<script type="text/javascript" class="init">'
    boilerplate += '$(document).ready( function () {'
    if sort_on_col is None:
        boilerplate += "$('#dummy').DataTable();"
    else:
        if not ascending:
            boilerplate += "$('#dummy').DataTable({'order':[[%d, 'desc']]});" % sort_on_col
        else:
            boilerplate += "$('#dummy').DataTable({'order':[[%d, 'asc']]});" % sort_on_col
    boilerplate += '} );'
    boilerplate += '</script></head>'
    _buffer = io.StringIO()
    _buffer.write(boilerplate)
    with pd.option_context('display.max_colwidth', -1):
        df.to_html(_buffer, index=False)

    _buffer.seek(0)
    tmp = _buffer.read()
    tmp = tmp.replace('<table border="1" class="dataframe">',
                      '<table border="1" id="dummy" class="display">')
    tmp += '</html>'
    _buffer.seek(0)

    _buffer.write(tmp)
    _buffer.seek(0)
    raw = _buffer.read()
    if title is not None:
        raw = '<h%d>%s</h%d>%s' % (header_size, title, header_size, raw)
    if filename is not None and isinstance(filename, str):
        res = 'yes'
        if os.path.exists(filename):
            res = query_yes_no(
                "%s exists, do you want to overwrite?" % filename, default='no')
        if res == 'yes':
            with open(filename, 'w') as f:
                f.write(raw)
            print("wrote file to '%s'" % filename)

        if file_post_process_func is not None:
            file_post_process_func(filename)

    if display:
        try:
            if not len(title):
                prefix = None
            else:
                prefix = title
            tmp = tempfile.NamedTemporaryFile(
                suffix='.html', prefix=prefix, delete=False, mode='w')

            tmp.write(raw)

            return open_path_in_browser(tmp.name)
        except:
            print("Not able to fire up browser, are you running in colab per chance?")


def open_path_in_browser(path):
    return webbrowser.open('file://' + path)


def download_and_save_zipped_excel_data_to_file(url='', tab_name='', refresh=False):
    """Returns the file name of the temp file we've written the data to

    """

    res = get_request_from_session(url=url, refresh=refresh)
    filebytes = io.BytesIO(res.content)
    tmp = zipfile.ZipFile(filebytes)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')

    existing = tmp.namelist()
    if tab_name not in existing:
        raise Exception("File = '%s' not found among existing files (%s)" % (
            tab_name, ','.join(existing)))
    with open(temp.name, 'wb') as fp:
        fp.write(tmp.read(tab_name))

    return temp.name


def get_request_from_session(session=None, url='', refresh=False, headers=None):
    """
    don't want the session object as part o fthe cache key
    """

    if refresh:
        _get_request_from_session.cache_clear()

    return _get_request_from_session(session=session, url=url, headers=headers)


@lru_cache(maxsize=None)
def _get_request_from_session(session=None, url=None, headers=None):
    if session is None:
        return requests.get(url, headers=headers)
    else:
        return session.get(url, headers=headers)


def uk_holidays(refresh=False):
    if refresh:
        _uk_holidays.cache_clear()
    return _uk_holidays()


@lru_cache(maxsize=None)
def _uk_holidays():
    """gov.uk address here (doesn't go back very far in time): https://www.gov.uk/bank-holidays.json
    """
    url = 'https://raw.githubusercontent.com/ministryofjustice/govuk-bank-holidays/main/govuk_bank_holidays/bank-holidays.json'

    data = requests.get(url).json()
    dates = pd.to_datetime([x['date']
                            for x in data['england-and-wales']['events']])
    return dates


def date_range(start_date, end_date, cal='uk', closed=None, refresh=False):
    if cal != 'uk':
        raise NotImplementedError("Only uk calendar implemented so far!")

    return pd.bdate_range(start_date, end_date, holidays=uk_holidays(refresh=refresh), freq='C', closed=closed)


def serial_date_to_datetime(ordinal, epoch=datetime.datetime(1900, 1, 1), as_time_stamps=True):
    if ordinal > 59:
        ordinal -= 1  # Excel leap year bug, 1900 is not a leap year!
    inDays = int(ordinal)
    frac = ordinal - inDays
    inSecs = int(round(frac * 86400.0))

    if as_time_stamps:
        return pd.to_datetime(epoch + datetime.timedelta(days=inDays - 1, seconds=inSecs))
    return epoch + datetime.timedelta(days=inDays - 1, seconds=inSecs)


def interpolate(a, b, sort=False, return_first_lower=True):
    # if b is in list a, return its idx, else return idx of element smaller than b
    if sort is True:
        a.sort()
    if b in a:
        return a.index(b)
    elif return_first_lower:
        return bisect.bisect_left(a, b) - 1
    else:
        return bisect.bisect_left(a, b)


def find_all_indicies(line='', tag='', case=False, use_regex=True):
    """
    sometimes when you're searching for eg. html tags it can be cumbersome to escape everything in regex
    """
    if use_regex:
        if not case:
            return [m.start() for m in re.finditer(tag, line, re.IGNORECASE)]
        else:
            return [m.start() for m in re.finditer(tag, line)]
    else:
        raise NotImplementedError("Could try re.escape(*) here maybe?")


def big_fmt(val):
    """
    format with thousandsd separator
    """
    if pd.isnull(val):
        return 'n/a'

    if isinstance(val, str):
        return val

    return '{:,}'.format(int(round(val, 0))).strip()


def value_is_numeric_type(X):
    X = np.asanyarray(X)

    if (X.dtype.char in np.typecodes['AllFloat']) or (X.dtype.char in np.typecodes['Integer']):  # noqa: E501
        return True
    return False


def strictly_increasing(L):
    """Copied from accepted answer to this: 
    https://stackoverflow.com/questions/4983258/python-how-to-check-list-monotonicity
    """

    return all(x < y for x, y in zip(L, L[1:]))


def strictly_decreasing(L):
    return all(x > y for x, y in zip(L, L[1:]))


def non_increasing(L):
    return all(x >= y for x, y in zip(L, L[1:]))


def non_decreasing(L):
    return all(x <= y for x, y in zip(L, L[1:]))


def monotonic(L):
    return non_increasing(L) or non_decreasing(L)


def syncsort(a, b):
    """
    sorts a in ascending order (and b will tag along, so each element of b is still associated with the right element in a)

    """
    a, b = (list(t) for t in zip(*sorted(zip(a, b))))
    return a, b


def string_col_to_unique_components(df, col_name, separator='|'):
    """If you have a column stored as strings, eg. 'player1|player2|player3'
    returns a flat array with unique values
    """
    return np.unique(df[col_name].str.split(separator, expand=True).values.ravel())


def rolling_window(a, window):
    """
    this is built-in in later versions of numpy
    """
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)


def plot_df(df, plot_these=None, normalize=True, title=None, yaxis_title=None):
    """
    plotly express is awkward when it comes to plotting very basic stuff, for some reason

    assume the df has a proper datetime index (any way to check?)
    if plot_these is None, plot all but the index, m'kay?
    """
    idx_name = df.index.name

    df = df.copy()
    # convert to long format:
    if plot_these is None:
        vv = list(set(df.columns) - set([idx_name]))
    else:
        vv = plot_these
    if normalize:
        df.dropna(inplace=True)
        # have to drop na , otherwise we risk dividing by na
        df = df / df.iloc[0, :]

    df_long = df.reset_index().melt(id_vars=[idx_name], value_vars=vv)
    if title is None:
        fig = pex.line(df_long, x=idx_name, y='value', color='variable')

    else:
        fig = pex.line(df_long, x=idx_name, y='value',
                       color='variable', title=title)

    if yaxis_title is not None:
        fig.update_layout(yaxis_title=yaxis_title)
    fig.show()


def rolling_apply(func, window, *arrays, n_jobs=1, **kwargs):
    if npext is not None:
        return np.ext.rolling_apply(func, window, *arrays, n_jobs=n_jobs, **kwargs)
    
    return _rolling_apply(func, window, *arrays, n_jobs=n_jobs, **kwargs)


def _rolling_apply(func, window, *arrays, n_jobs=1, **kwargs):
    """
    numpy_ext requires numpt 1.20 something
    this code is copied from numpy_ext
    Useful for doing rolling window calcs involving multiple cols on a dataframe

    For example, rolling 10-day window on off and def rating in nba:

    def rollinator(poss, rtg):
        return np.dot(poss, rtg)/poss.sum()

    rwb['off_L10'] = rolling_apply(rollinator, 10, rwb.POSS, rwb.OFF_RATING)

    You CAN'T do this simply using the built-in rolling()... (obv this might change in the future)
    Doesn't seem to work with multi-dimensional output?

    Roll a fixed-width window over an array or a group of arrays, producing slices.
    Apply a function to each slice / group of slices, transforming them into a value.
    Perform computations in parallel, optionally.
    Return a new np.ndarray with the resulting values.
    Parameters
    ----------
    func : Callable
        The function to apply to each slice or a group of slices.
    window : int
        Window size.
    *arrays : list
        List of input arrays.
    n_jobs : int, optional
        Parallel tasks count for joblib. If 1, joblib won't be used. Default is 1.
    **kwargs : dict
        Input parameters (passed to func, must be named).
    Returns
    -------
    np.ndarray
    Examples
    --------
    >>> arr = np.array([1, 2, 3, 4, 5])
    >>> rolling_apply(sum, 2, arr)
    array([nan,  3.,  5.,  7.,  9.])
    >>> arr2 = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
    >>> func = lambda a1, a2, k: (sum(a1) + max(a2)) * k
    >>> rolling_apply(func, 2, arr, arr2, k=-1)
    array([  nan,  -5.5,  -8.5, -11.5, -14.5])
    """
    if not any(isinstance(window, t) for t in [int, np.integer]):
        raise TypeError(f'Wrong window type ({type(window)}) int expected')

    window = int(window)

    if max(len(x.shape) for x in arrays) != 1:
        raise ValueError('Wrong array shape. Supported only 1D arrays')

    if len({array.size for array in arrays}) != 1:
        raise ValueError('Arrays must be the same length')

    def _apply_func_to_arrays(idxs):
        return func(*[array[idxs[0]:idxs[-1] + 1] for array in arrays], **kwargs)

    array = arrays[0]
    rolls = rolling(
        array if len(arrays) == n_jobs == 1 else np.arange(len(array)),
        window=window,
        skip_na=True
    )

    if n_jobs == 1:
        if len(arrays) == 1:
            arr = list(map(functools.partial(func, **kwargs), rolls))
        else:
            arr = np.asarray(list(map(_apply_func_to_arrays, rolls)))
    else:
        f = delayed(_apply_func_to_arrays)
        arr = Parallel(n_jobs=n_jobs)(f(idxs[[0, -1]]) for idxs in rolls)

    try:
        return prepend_na(arr, n=window - 1)
    except:
        return prepend_na(arr.ravel(), n=window - 1)


def rolling(
    array,
    window,
    skip_na=False,
    as_array=False
):
    """
    used with rolling_apply. code copied from numpy_ext 
    Roll a fixed-width window over an array.
    The result is either a 2-D array or a generator of slices, controlled by `as_array` parameter.
    Parameters
    ----------
    array : np.ndarray
        Input array.
    window : int
        Size of the rolling window.
    skip_na : bool, optional
        If False, the sequence starts with (window-1) windows filled with nans. If True, those are omitted.
        Default is False.
    as_array : bool, optional
        If True, return a 2-D array. Otherwise, return a generator of slices. Default is False.
    Returns
    -------
    np.ndarray or Generator[np.ndarray, None, None]
        Rolling window matrix or generator
    Examples
    --------
    >>> rolling(np.array([1, 2, 3, 4, 5]), 2, as_array=True)
    array([[nan,  1.],
           [ 1.,  2.],
           [ 2.,  3.],
           [ 3.,  4.],
           [ 4.,  5.]])
    Usage with numpy functions
    >>> arr = rolling(np.array([1, 2, 3, 4, 5]), 2, as_array=True)
    >>> np.sum(arr, axis=1)
    array([nan,  3.,  5.,  7.,  9.])
    """
    if not any(isinstance(window, t) for t in [int, np.integer]):
        raise TypeError(f'Wrong window type ({type(window)}) int expected')

    window = int(window)

    if array.size < window:
        raise ValueError('array.size should be bigger than window')

    def rows_gen():
        if not skip_na:
            prepend_func = prepend_na
            if np.issubdtype(array.dtype, np.datetime64):

                def prepend_func(arr, n):
                    return np.hstack((np.repeat(np.datetime64('NaT'), n), arr))

            yield from (prepend_func(array[:i + 1], (window - 1) - i) for i in np.arange(window - 1))

        starts = np.arange(array.size - (window - 1))
        yield from (array[start:end] for start, end in zip(starts, starts + window))

    return np.array([row for row in rows_gen()]) if as_array else rows_gen()


def prepend_na(array, n):
    """
    used with rolling_apply
    Return a copy of array with nans inserted at the beginning.

    Parameters
    ----------
    array : np.ndarray
        Input array.
    n : int
        Number of elements to insert.

    Returns
    -------
    np.ndarray
        New array with nans added at the beginning.

    Examples
    --------
    >>> prepend_na(np.array([1, 2]), 2)
    array([nan, nan,  1.,  2.])
    """
    return np.hstack(
        (
            nans(n, array[0].dtype) if len(array) and hasattr(
                array[0], 'dtype') else nans(n),
            array
        )
    )


def nans(shape, dtype=np.float64):
    """
    Return a new array of a given shape and type, filled with np.nan values.

    Parameters
    ----------
    shape : int or tuple of ints
        Shape of the new array, e.g., (2, 3) or 2.
    dtype: data-type, optional

    Returns
    -------
    np.ndarray
        Array of np.nans of the given shape.

    Examples
    --------
    >>> nans(3)
    array([nan, nan, nan])
    >>> nans((2, 2))
    array([[nan, nan],
           [nan, nan]])
    >>> nans(2, np.datetime64)
    array(['NaT', 'NaT'], dtype=datetime64)
    """
    if np.issubdtype(dtype, np.integer):
        dtype = np.float
    arr = np.empty(shape, dtype=dtype)
    arr.fill(np.nan)
    return arr
