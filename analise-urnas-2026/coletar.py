"""Coleta e decodifica os arquivos de urna do 1º turno de 2026, UF por UF.

Lê apenas o BU (``-bu.dat``) e o log (``-log.jez``) de cada seção diretamente
do pacote oficial do TSE via HTTP Range, sem gravar os ZIPs (≈90 GB) em disco.
Cada entrada tem tamanho e CRC32 conferidos contra o diretório central do ZIP.

Uso:
    python coletar.py --ufs TODAS --saida dados/secoes
    python coletar.py --ufs RR AC --saida dados/secoes

Saída por UF: ``secoes_<UF>.jsonl.gz`` (uma linha por seção) e
``ocorrencias_<UF>.json`` (falhas de leitura, arquivos ausentes, contagens).
UFs já processadas são puladas (apague o arquivo para reprocessar).
"""
import argparse
import collections
import concurrent.futures as cf
import gzip
import io
import json
import os
import struct
import sys
import time
import zipfile
import zlib
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from urnas.decod import decode_bu, parse_log  # noqa: E402

BASE = 'https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_{uf}.zip'
UFS = ('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ').split()
WANTED = ('-bu.dat', '-log.jez')
GAP = 16 * 1024          # junta entradas separadas por até 16 KB numa única requisição
TASK_BYTES = 6 * 2**20   # tamanho alvo de cada tarefa
SLACK = 512              # folga para o campo "extra" do cabeçalho local

_session = None


def session():
    global _session
    if _session is None:
        _session = requests.Session()
        ca = '/root/.ccr/ca-bundle.crt'
        if os.path.exists(ca) and not os.environ.get('REQUESTS_CA_BUNDLE'):
            _session.verify = ca
    return _session


def get_range(url, a, b, tries=6):
    for i in range(tries):
        try:
            r = session().get(url, headers={'Range': f'bytes={a}-{b}'}, timeout=120)
            if r.status_code != 206:
                raise IOError(f'HTTP {r.status_code}')
            data = r.content
            if len(data) != min(b, SIZES[url] - 1) - a + 1:
                raise IOError('resposta incompleta')
            return data
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


SIZES = {}


class RemoteFile(io.RawIOBase):
    """Arquivo somente-leitura via HTTP Range, suficiente para zipfile ler o diretório central."""

    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.cache = {}

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b''
        block = 4 * 2**20
        out = bytearray()
        while n > 0:
            k = self.pos // block
            if k not in self.cache:
                self.cache[k] = get_range(self.url, k * block, min(self.size, (k + 1) * block) - 1)
            chunk = self.cache[k][self.pos - k * block:self.pos - k * block + n]
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def extract(raw, base, info):
    """Extrai uma entrada a partir de bytes brutos que começam em ``base``."""
    off = info['offset'] - base
    h = struct.unpack('<4s5H3L2H', raw[off:off + 30])
    if h[0] != b'PK\x03\x04':
        raise IOError('cabeçalho local inválido')
    start = off + 30 + h[-2] + h[-1]
    comp = raw[start:start + info['csize']]
    if len(comp) != info['csize']:
        raise IOError('entrada truncada')
    data = zlib.decompress(comp, -15) if info['method'] == 8 else comp
    if len(data) != info['size'] or zlib.crc32(data) != info['crc']:
        raise IOError('tamanho/CRC não confere')
    return data


def run_task(url, uf, sections):
    """sections: lista de (chave, {sufixo: info}). Baixa, confere e decodifica."""
    infos = sorted((i for _, files in sections for i in files.values()), key=lambda i: i['offset'])
    ranges, cur = [], None
    for i in infos:
        a, b = i['offset'], i['offset'] + 30 + len(i['name']) + SLACK + i['csize']
        if cur and a - cur[1] <= GAP:
            cur[1] = max(cur[1], b)
            cur[2].append(i)
        else:
            cur = [a, b, [i]]
            ranges.append(cur)
    blobs = {}
    for a, b, items in ranges:
        raw = get_range(url, a, min(b, SIZES[url] - 1))
        for i in items:
            blobs[i['name']] = extract(raw, a, i)
    rows, errs = [], []
    for key, files in sections:
        rec = {'uf': uf, 'arquivo': key}
        try:
            rec.update(decode_bu(blobs[files['-bu.dat']['name']]))
        except Exception as e:  # noqa: BLE001
            errs.append({'arquivo': key, 'etapa': 'bu', 'erro': f'{type(e).__name__}: {e}'})
            continue
        if '-log.jez' in files:
            try:
                rec.update(parse_log(blobs[files['-log.jez']['name']]))
                rec['log_ok'] = True
            except Exception as e:  # noqa: BLE001
                rec['log_ok'] = False
                errs.append({'arquivo': key, 'etapa': 'log', 'erro': f'{type(e).__name__}: {e}'})
        else:
            rec['log_ok'] = False
            errs.append({'arquivo': key, 'etapa': 'log', 'erro': 'log ausente no pacote'})
        rows.append(rec)
    return rows, errs, sum(b - a for a, b, _ in ranges)


def process_uf(uf, out_dir, workers):
    dest = out_dir / f'secoes_{uf}.jsonl.gz'
    if dest.exists():
        print(uf, 'já processada', flush=True)
        return
    url = BASE.format(uf=uf)
    r = session().head(url, timeout=60)
    r.raise_for_status()
    SIZES[url] = int(r.headers['Content-Length'])
    t0 = time.time()
    z = zipfile.ZipFile(RemoteFile(url, SIZES[url]))
    by_sec = collections.defaultdict(dict)
    suffixes = collections.Counter()
    for i in z.infolist():
        if '-' not in i.filename:
            suffixes[i.filename] += 1
            continue
        key, suf = i.filename.rsplit('-', 1)
        suf = '-' + suf
        suffixes[suf] += 1
        if suf in WANTED:
            if i.compress_type not in (0, 8):
                raise IOError(f'compressão {i.compress_type} não suportada')
            by_sec[key][suf] = {'name': i.filename, 'offset': i.header_offset, 'csize': i.compress_size,
                                'size': i.file_size, 'crc': i.CRC, 'method': i.compress_type}
    errs = [{'arquivo': k, 'etapa': 'pacote', 'erro': 'BU ausente no pacote'} for k, f in by_sec.items() if '-bu.dat' not in f]
    secs = sorted(((k, f) for k, f in by_sec.items() if '-bu.dat' in f), key=lambda kf: min(i['offset'] for i in kf[1].values()))
    tasks, cur, size = [], [], 0
    for k, f in secs:
        cur.append((k, f))
        size += sum(i['csize'] for i in f.values())
        if size >= TASK_BYTES:
            tasks.append(cur)
            cur, size = [], 0
    if cur:
        tasks.append(cur)
    print(f'{uf}: {len(secs)} seções, {len(tasks)} tarefas, pacote {SIZES[url] / 1e9:.2f} GB', flush=True)
    rows, nbytes, done = [], 0, 0
    with cf.ProcessPoolExecutor(workers, initializer=_init_sizes, initargs=(dict(SIZES),)) as ex:
        futs = [ex.submit(run_task, url, uf, t) for t in tasks]
        for f in cf.as_completed(futs):
            r_, e_, b_ = f.result()
            rows += r_
            errs += e_
            nbytes += b_
            done += 1
            if done % 50 == 0 or done == len(futs):
                el = time.time() - t0
                print(f'  {uf} {done}/{len(futs)} tarefas, {nbytes / 1e9:.2f} GB, {nbytes / 1e6 / el:.1f} MB/s', flush=True)
    rows.sort(key=lambda r: r['arquivo'])
    tmp = dest.with_suffix('.part')
    with gzip.open(tmp, 'wt', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    (out_dir / f'ocorrencias_{uf}.json').write_text(json.dumps({
        'uf': uf, 'url': url, 'bytes_pacote': SIZES[url], 'bytes_baixados': nbytes,
        'entradas_por_tipo': dict(suffixes), 'secoes_decodificadas': len(rows),
        'segundos': round(time.time() - t0, 1), 'ocorrencias': errs}, ensure_ascii=False, indent=1))
    tmp.replace(dest)
    print(f'{uf}: {len(rows)} seções gravadas, {len(errs)} ocorrências, {time.time() - t0:.0f}s', flush=True)


def _init_sizes(sizes):
    SIZES.update(sizes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ufs', nargs='+', default=['TODAS'])
    ap.add_argument('--saida', default='dados/secoes')
    ap.add_argument('--workers', type=int, default=24)
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    ufs = UFS if a.ufs == ['TODAS'] else [u.upper() for u in a.ufs]
    for uf in ufs:
        process_uf(uf, out, a.workers)


if __name__ == '__main__':
    main()
