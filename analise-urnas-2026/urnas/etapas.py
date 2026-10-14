"""Decomposição de cada atendimento do log em etapas, por hora local.

ociosidade   : "Aguardando digitação do identificador" → "Identificador do eleitor digitado pelo mesário"
               (urna livre esperando o próximo eleitor; ~0 quando há fila)
identificacao: identificador digitado → "Eleitor foi habilitado" (inclui digital ou liberação pelo mesário)
cabine       : habilitação → "O voto do eleitor foi computado" (o eleitor votando nos cargos)

Por hora local (0–23) guarda: atendimentos, soma e contagens por faixa de cada etapa, habilitações
biométricas, liberações pelo mesário e tentativas de digital. Nada sobre o conteúdo do voto.
"""
import io
import zipfile

from .decod import FormatoInesperado, _secs

FAIXAS_CABINE = (15, 20, 30, 45, 60, 90, 120)  # limites superiores em segundos; última faixa = 120+


def _faixa(v):
    for i, lim in enumerate(FAIXAS_CABINE):
        if v < lim:
            return i
    return len(FAIXAS_CABINE)


def parse_etapas(data, dia='04/10/2026'):
    z = zipfile.ZipFile(io.BytesIO(data))
    if 'logd.dat' not in z.namelist():
        raise FormatoInesperado('logd.dat ausente')
    raw = z.read('logd.dat').decode('latin1')
    H = 24
    out = {k: [0] * H for k in ('n', 'ocio_soma', 'ident_soma', 'cabine_soma', 'n_ocio', 'n_ident', 'bio', 'manual',
                                'tent', 'ocio_zero')}
    out['cabine_faixas'] = [[0] * (len(FAIXAS_CABINE) + 1) for _ in range(H)]
    cur = None
    for line in raw.splitlines():
        a = line.split('\t')
        if len(a) < 5 or a[3] != 'VOTA' or not a[0].startswith(dia):
            continue
        s = _secs(a[0][11:19])
        m = a[4]
        if m == 'Aguardando digitação do identificador do eleitor':
            cur = {'aguard': s, 'tent': 0}
        elif cur is None:
            continue
        elif m == 'Identificador do eleitor digitado pelo mesário' and 'id' not in cur:
            cur['id'] = s
        elif m.startswith('Solicita digital. Tentativa'):
            cur['tent'] += 1
        elif m == 'Tipo de habilitação do eleitor [biométrica]':
            cur['bio'] = True
        elif m.startswith('Mesário ') and m.endswith('habilitou o eleitor'):
            cur['manual'] = True
        elif m == 'Eleitor foi habilitado':
            cur['hab'] = s
        elif m == 'O voto do eleitor foi computado':
            h = s // 3600
            out['n'][h] += 1
            out['bio'][h] += bool(cur.get('bio'))
            out['manual'][h] += bool(cur.get('manual'))
            out['tent'][h] += cur['tent']
            if 'id' in cur:
                o = cur['id'] - cur['aguard']
                out['ocio_soma'][h] += o
                out['n_ocio'][h] += 1
                out['ocio_zero'][h] += o <= 5
                if 'hab' in cur:
                    out['ident_soma'][h] += cur['hab'] - cur['id']
                    out['n_ident'][h] += 1
            if 'hab' in cur:
                c = s - cur['hab']
                out['cabine_soma'][h] += c
                out['cabine_faixas'][h][_faixa(c)] += 1
            cur = None
    return out
