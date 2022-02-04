

import pytest

import pathlib
import sys


import os
import requests
import tempfile
import zipfile
import io
import pandas as pd
import time


HERE = pathlib.Path(__file__).resolve().parent



# insert at 1, 0 is the script path (or '' in REPL)
# temporary hack until package is published and we can inherit from there:

sys.path.insert(1, '%s/thin_wrappers' % HERE.parent)
import file_based_caching as fcache  # NOQA: E402

def headers():
    return {'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A',
            }


def dummy_function(refresh=False):
    """This downloads a zipped csv file and returns the data stored in the csv file
    """
    ck = fcache.create_cache_key(locals(), fcache.current_function_name())

    datum = fcache.extract_cache_data(ck, refresh=refresh)

    if datum is None:
        # res = requests.get('http://ipv4.download.thinkbroadband.com/5MB.zip')
        
        url = 'https://eforexcel.com/wp/wp-content/uploads/2017/07/100-CC-Records.zip'

        res = requests.get(url, headers=headers())

        filebytes = io.BytesIO(res.content)
        tmp = zipfile.ZipFile(filebytes)
        temp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')

        with open(temp.name, 'wb') as fp:
            fp.write(tmp.read('100 CC Records.csv'))

        datum = pd.read_csv(temp.name, encoding='cp1252')
        fcache.set_gp_cache(ck, datum)
        return datum
    return datum


def test_cache():
    """Test that the caching function writes to the file first time we call it, 
    and also that we rewrite the file when we ask it to.
    """
    dummy_function(refresh=False)
    assert os.path.exists(
        'py_function_cache/dummy_function'), "Did not find cached data?!"

    mtime = os.path.getmtime('py_function_cache/dummy_function')
    time.sleep(5)
    dummy_function(refresh=True)
    mmtime = os.path.getmtime('py_function_cache/dummy_function')
    assert mmtime > mtime, "Cached data hasn't been refreshed!? (orig mtime = '%s', new mtime = '%s')" % (pd.to_datetime(mtime, unit='s'), pd.to_datetime(mmtime, unit='s'))



if __name__ == '__main__':
    pytest.main([__file__])
