import pytest
import pathlib
import sys
import db_utils as db
import requests
import io
import zipfile
import tempfile
import pandas as pd
import os
HERE = pathlib.Path(__file__).resolve().parent



# insert at 1, 0 is the script path (or '' in REPL)
# temporary hack until package is published and we can inherit from there:

sys.path.insert(1, '%s/thin_wrappers' % HERE.parent)




def headers():
    return {'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A',
            }


def download_data():
    url = 'https://eforexcel.com/wp/wp-content/uploads/2017/07/100-CC-Records.zip'
    res = requests.get(url, headers=headers())
    filebytes = io.BytesIO(res.content)
    tmp = zipfile.ZipFile(filebytes)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    with open(temp.name, 'wb') as fp:
        fp.write(tmp.read('100 CC Records.csv'))
    datum = pd.read_csv(temp.name, encoding='cp1252')
    return datum


def test_database():
    """Test that it works writig data to an sqlite db and then read it.
    """
    df = download_data()

    db.write_db_table('dummy', df, 'replace', 'test_db.sqlite')

    assert os.path.exists('test_db.sqlite'), "Did not find database?!"

    n_records = len(df)
    from_db = db.read_sql_table('dummy', 'test_db.sqlite')
    assert len(
        from_db) == n_records, "Number of records does not match between database and data!"
    db.write_db_table('dummy', df, 'append', 'test_db.sqlite')
    from_db = db.read_sql_table('dummy', 'test_db.sqlite')
    assert len(from_db) == (
        2 * n_records), "Number of records does not match between database and data!"


if __name__ == '__main__':
    pytest.main([__file__])
