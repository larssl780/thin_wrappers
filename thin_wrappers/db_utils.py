import pdb # NOQA F401
import copy
import os
import sqlite3
import pandas as pd 

__alchemy_installed = True
try:
    from sqlalchemy import create_engine, inspect
    # from sqlalchemy.engine.reflection import Inspector
except:
    __alchemy_installed = False


def db_exists(db='xxx.sqlite'):
    return os.path.isfile(db)


def create_db_engine(db='xxx.sqlite', check_exists=True):
    # if we don't do this, the code will create an empty db with the given name
    if check_exists:
        assert db_exists(db), "The database '%s' does NOT exist!" % db
    engine = create_engine('sqlite:///%s' % db)
    return engine


def table_exists(table_name, db='xxx.sqlite'):
    if __alchemy_installed:
        engine = create_db_engine(db)
        return engine_has_table(engine, table_name)
        
    else:
        raise NotImplementedError("Can't do this yet without sqlalchemy")


def read_sql_query(query, db='xxx.sqlite', verbose=False, force_no_alchemy=False, return_array=False, return_single_value=False, **kwargs):
    """
    return array will return a list if the query if for just one column (avoid a bunch of extra stuff at the point of calling the func)
    """
    if verbose:
        print('Trying to get %s' % db)

    if (__alchemy_installed and not force_no_alchemy) and not (return_array or return_single_value):
        engine = create_db_engine(db)
        try:
            ds = pd.read_sql_query(query, engine, **kwargs)
        except Exception as e:
            if 'no such column' in str(e):
                # pdb.set_trace()
                msg = "Query '%s' failed because of missing column:" % query
                for tbl in engine.table_names():
                    if tbl in query.split(' '):
                        # print(tbl)
                        raise Exception(msg + '%s' % (schema(tbl, db)))
            raise Exception(str(e))
            # pdb.set_trace()
    else:
        # this is actually faster than sqlalchemy, probably lots of overhead + sanity checks?
        return _convert_query_result_to_df(query, db, return_array=return_array, return_single_value=return_single_value)
        

    return ds


def item_exists(item, col, table, db, cursor=None):
    query = "select * from %s where %s in ('%s')" % (table, col, item)
    res = query_response(query, db, cursor=cursor)
    return res is not None


def sql_like_query(col_name='', table='', query='', db_name=''):
    """
    # query would be like 'select * from data where name = '''
    """
    query = "select * from %s where %s LIKE '%%%s%%'" % (
        table, col_name, query)
    return read_sql_query(query, db_name)


def query_response(query, db, cursor=None):
    close_cursor = True
    if cursor is None:
        conn = sqlite3.connect(db)
        crs = conn.cursor()
    else:
        crs = cursor
        close_cursor = False

    crs.execute(query)
    res = crs.fetchone()

    if close_cursor:
        crs.close()
    return res


def _convert_query_result_to_df(query, db, return_array=False, return_single_value=False, verbose=False):
    conn = sqlite3.connect(db)
    crs = conn.cursor()
    if verbose:
        print(query)
    crs.execute(query)
    res = crs.fetchall()
    if not len(res):
        raise Exception("Nothing returned for '%s'" % query)
    cols = [x[0] for x in crs.description]

    if (len(cols) == 1) and (return_array or return_single_value):
        crs.close()
        if return_single_value:
            if len(res[0]) > 1:
                raise Exception("There are more than 1 value!")
            return res[0][0]
        else:
            return [x[0] for x in res]
    else:
        df_in = {}
        for i in range(len(cols)):
            df_in[cols[i]] = [x[i] for x in res]

    crs.close()
    return pd.DataFrame(df_in, columns=cols)


def engine_has_table(engine, table_name):
    insp = inspect(engine)
    tables = insp.get_table_names()
    return table_name in tables
def read_sql_table(table_name, db='xxx.sqlite', force_no_alchemy=False, check_exists=True):
    """
    wrapper around pandas function
    force_no_alchemy is there for debug reasons
    """
    
    if __alchemy_installed and not force_no_alchemy:
        engine = create_db_engine(db, check_exists=check_exists)
        
        
        if not engine_has_table(engine, table_name):
            print("Table '%s' not found in %s!" % (table_name, db))
            return pd.DataFrame()
        else:
            ds = pd.read_sql_table(table_name, engine)
            return ds
    else:
        query = 'select * from %s' % table_name
        return _convert_query_result_to_df(query, db)


def schema(table_name='', db_name=''):
    df = read_sql_query("select * from %s limit 5" % table_name, db=db_name)
    cols = df.columns

    rv = []
    i = 0

    def fixer(x):
        return str(type(x)).replace("<class '", '').replace("'>", '')

    for c in cols:
        cts = list(set(list(map(fixer, df[c]))))
        if len(cts) == 1:
            
            rv.append('[%d]:%s:%s' % (i, c, cts[0]))
        else:
            rv.append('[%d]:%s:%s' % (i, c, ','.join(cts)))
        i += 1
    return rv


def sqlite_schema(table_name='', db_name=''):
    _db = sqlite3.connect(db_name)
    cur = _db.cursor()
    res = cur.execute("PRAGMA table_info('%s')" % table_name).fetchall()
    out = []
    for el in res:
        out.append([el[0], el[1], el[2]])
    return pd.DataFrame(out, columns=['col_nr', 'col_name', 'col_type'])


def sanity_check_table(table_name='', db_name=''):
    """
    are columns designated as real actually reals? This will stop eg. db.read_sql_table from working
    """
    df = sqlite_schema(table_name, db_name)
    pot_floats = df[df['col_type'] == 'REAL']
    raw = read_sql_query("select * from %s" % table_name, db_name)
    all_ok = True
    for col in pot_floats['col_name']:
        try:
            raw[col].astype(float, copy=False)
        except:
            print('%s has potential issues, bro' % col)
            all_ok = False
    if all_ok:
        print("Everything checked out!")



def tables_in_db(db='xxx.sqlite'):
    return read_sql_query("select name from sqlite_master where type = 'table'", db=db)['name'].tolist()


def write_db_table(table_name, df, if_exists='replace', db='xxx.sqlite'):
    """
    if exists can be replace or append (or fail)
    """
    with sqlite3.connect(db) as cnx:
        df.to_sql(table_name, cnx, if_exists=if_exists, index=False)


def copy_table(from_table_name='', to_table_name=None, from_db_name='', to_db_name='', if_exists='replace', col=None, vals=[], write_to_db=True):
    """
    if we specify col, we select those col values in vals and copy those across
    """
    df = read_sql_table(from_table_name, from_db_name)
    if not (col is None):
        df = df.query('%s in @vals' % (col))
    if to_table_name is None:
        to_table_name = copy.deepcopy(from_table_name)
    if write_to_db:
        write_db_table(to_table_name, df, if_exists=if_exists, db=to_db_name)
    else:
        print('Would have written this to the db')
        return df


def vacuum_db(db_name):
    """
    when you drop a table or columns from a table in sqlite, no memory is freed up (more memory might even be used).
    The vacuum command deals with that
    """
    assert len(db_name), "Please provide a database name!"
    os.system('sqlite3 %s "VACUUM;"' % db_name)


def number_of_records(table_name, db_name):
    df = read_sql_query("select * from %s limit 1" % table_name, db=db_name)
    return read_sql_query("select count(%s) from %s" % (df.columns[0], table_name), db_name, return_single_value=True)


class connection():
    def __init__(self, db_path=''):
        if len(db_path):
            self._connection = sqlite3.connect(db_path)
        else:
            raise Exception("No db_path provided!")
        self._db_path = db_path

    @property
    def db_name(self):
        return os.path.basename(self._db_path)

    @property
    def db_path(self):
        return self._db_path

    @db_path.setter
    def db_path(self, value):
        if not len(value):
            raise Exception("You have to provide the path to the database!")
        self._connection.close()
        self._db_path = value
        self._connection = sqlite3.connect(self._db_path)

    @property
    def connection(self):
        return self._connection

    def execute(self, query):
        crs = self.connection.execute(query)
        res = crs.fetchall()
        crs.close()
        cols = [x[0] for x in crs.description]
        return pd.DataFrame(res, columns=cols)

    @property
    def tables(self):
        raw = self.execute(
            "select name from sqlite_master where type = 'table'")

        return raw.name.values

    def __repr__(self):
        return ">>%s<<" % self.db_name
