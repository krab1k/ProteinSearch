import mariadb
from pathlib import Path
import shutil
import sys
import time

sys.path.append('/usr/local/www/ProteinSearch')

from config import config


def main():
    conn = mariadb.connect(host=config['db']['host'], user=config['db']['user'], password=config['db']['password'],
                           database=config['db']['database'])
    c = conn.cursor()

    print('Removing old data from DB cache...', end='')
    query = ('SELECT * FROM queriesNearestNeighboursStats '
             'WHERE evaluationTime < 1000 AND added <= NOW() - INTERVAL 6 HOUR')
    c.execute(query)
    print('Done.')

    print('Removing old saved queries fom DB...', end='')
    c.execute('DELETE FROM savedQueries WHERE added <= NOW() - INTERVAL 1 WEEK')
    print('Done.')

    print('Removing old directories with query data...')
    c.execute('SELECT job_id from savedQueries WHERE added > NOW() - INTERVAL 1 WEEK')
    saved_jobs = {res[0] for res in (c.fetchall())}

    for folder_name in Path(config['dirs']['computations']).iterdir():
        full_path = Path(config['dirs']['computations'], folder_name)
        job_id = str(folder_name)[5:]
        if job_id in saved_jobs:
            print('Not removing: ', job_id, ' -- saved query')
            continue
        if time.time() - full_path.stat().st_mtime < 24 * 3600:
            print('Not removing: ', job_id, ' -- not old')
            continue

        shutil.rmtree(full_path)

    print('Done.')
    conn.commit()
    c.close()
    conn.close()


if __name__ == '__main__':
    main()
