"""Relê só os logs das UFs pedidas e extrai o ritmo de votação (urnas/tempos.py).

Uso: python coletar_tempos.py --ufs AL BA CE MA PB PE PI RN SE --saida dados/tempos [--modo etapas]
O corte local de cada município vem de dados/secoes_2026_1t.csv.gz (abertura típica + 9h).
"""
import argparse
import concurrent.futures as cf
import gzip
import json
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import coletar as C  # noqa: E402
from urnas.etapas import parse_etapas  # noqa: E402
from urnas.tempos import parse_tempos  # noqa: E402

CORTES = {}
MODO = {'m': 'tempos'}


def _init(sizes, cortes, modo='tempos'):
    MODO['m'] = modo
    C.SIZES.update(sizes)
    CORTES.update(cortes)


def chave(nome):
    # o03220ba MMMMM ZZZZ SSSS
    return int(nome[8:13]), int(nome[13:17]), int(nome[17:21])


def task(url, uf, items):
    out, errs = [], []
    items = sorted(items, key=lambda i: i['offset'])
    ranges, cur = [], None
    for i in items:
        a, b = i['offset'], i['offset'] + 30 + len(i['name']) + C.SLACK + i['csize']
        if cur and a - cur[1] <= C.GAP:
            cur[1] = max(cur[1], b)
            cur[2].append(i)
        else:
            cur = [a, b, [i]]
            ranges.append(cur)
    for a, b, its in ranges:
        raw = C.get_range(url, a, min(b, C.SIZES[url] - 1))
        for i in its:
            mun, zona, sec = chave(i['name'])
            try:
                blob = C.extract(raw, a, i)
                r = parse_etapas(blob) if MODO['m'] == 'etapas' else parse_tempos(blob, CORTES.get((uf, mun), 17))
                r.update({'uf': uf, 'cd_municipio': mun, 'nr_zona': zona, 'nr_secao': sec})
                out.append(r)
            except Exception as e:  # noqa: BLE001
                errs.append({'arquivo': i['name'], 'erro': f'{type(e).__name__}: {e}'})
    return out, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ufs', nargs='+', required=True)
    ap.add_argument('--saida', default='dados/tempos')
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--modo', choices=['tempos', 'etapas'], default='tempos')
    a = ap.parse_args()
    out_dir = Path(a.saida)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = pd.read_csv(Path(__file__).parent / 'dados' / 'secoes_2026_1t.csv.gz',
                       usecols=['uf', 'cd_municipio', 'corte_local_h'])
    cortes = {(u, int(m)): int(c) for (u, m), c in base.dropna().groupby(['uf', 'cd_municipio']).corte_local_h.first().items()}
    for uf in a.ufs:
        dest = out_dir / f'{a.modo}_{uf}.jsonl.gz'
        if dest.exists():
            continue
        url = C.BASE.format(uf=uf)
        C.SIZES[url] = int(C.session().head(url, timeout=60).headers['Content-Length'])
        z = zipfile.ZipFile(C.RemoteFile(url, C.SIZES[url]))
        logs = [{'name': i.filename, 'offset': i.header_offset, 'csize': i.compress_size, 'size': i.file_size,
                 'crc': i.CRC, 'method': i.compress_type} for i in z.infolist() if i.filename.endswith('-log.jez')]
        tasks, curt, size = [], [], 0
        for i in sorted(logs, key=lambda i: i['offset']):
            curt.append(i)
            size += i['csize']
            if size >= C.TASK_BYTES:
                tasks.append(curt)
                curt, size = [], 0
        if curt:
            tasks.append(curt)
        t0 = time.time()
        rows, errs = [], []
        with cf.ProcessPoolExecutor(a.workers, initializer=_init, initargs=(dict(C.SIZES), cortes, a.modo)) as ex:
            for f in cf.as_completed([ex.submit(task, url, uf, t) for t in tasks]):
                r, e = f.result()
                rows += r
                errs += e
        with gzip.open(dest, 'wt') as fh:
            for r in rows:
                fh.write(json.dumps(r) + '\n')
        print(f'{uf}: {len(rows)} logs, {len(errs)} erros, {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
