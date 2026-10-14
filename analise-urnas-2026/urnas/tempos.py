"""Ritmo de votação a partir do log da urna (um registro por seção).

Para cada atendimento: habilitação → voto computado. Mede volume por hora local,
duração dos atendimentos e intervalos entre votos computados, separando antes e
depois do corte local (17h de Brasília). Não lê nem infere o voto de ninguém.
"""
import io
import statistics
import zipfile

from .decod import FormatoInesperado, _secs


def _q(vals, p):
    if not vals:
        return None
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(p * len(vals)))]


def parse_tempos(data, corte_h, dia='04/10/2026'):
    z = zipfile.ZipFile(io.BytesIO(data))
    if 'logd.dat' not in z.namelist():
        raise FormatoInesperado('logd.dat ausente')
    raw = z.read('logd.dat').decode('latin1')
    corte = corte_h * 3600
    por_hora = [0] * 24
    dur_antes, dur_depois, gap_antes, gap_depois = [], [], [], []
    tent_antes = tent_depois = n_antes = n_depois = 0
    manual_depois = bio_depois = 0
    rajada_depois = 0  # votos computados a < 20 s do anterior, após o corte
    hab = None
    tent = 0
    manual = bio = False
    ultimo = None
    pronta = encerr = None
    for line in raw.splitlines():
        a = line.split('\t')
        if len(a) < 5 or a[3] != 'VOTA' or not a[0].startswith(dia):
            continue
        s = _secs(a[0][11:19])
        m = a[4]
        if m == 'Urna pronta para receber votos' and pronta is None:
            pronta = s
        elif m == 'Aguardando digitação do identificador do eleitor':
            hab, tent, manual, bio = None, 0, False, False
        elif m.startswith('Solicita digital. Tentativa'):
            tent += 1
        elif m == 'Tipo de habilitação do eleitor [biométrica]':
            bio = True
        elif m.startswith('Mesário ') and m.endswith('habilitou o eleitor'):
            manual = True
        elif m == 'Eleitor foi habilitado':
            hab = s
        elif m == 'O voto do eleitor foi computado':
            por_hora[s // 3600] += 1
            depois = s >= corte
            if hab is not None:
                (dur_depois if depois else dur_antes).append(s - hab)
            if ultimo is not None:
                g = s - ultimo
                (gap_depois if depois else gap_antes).append(g)
                if depois and g < 20:
                    rajada_depois += 1
            ultimo = s
            if depois:
                n_depois += 1
                tent_depois += tent
                manual_depois += manual
                bio_depois += bio
            else:
                n_antes += 1
                tent_antes += tent
            hab = None
        elif m == 'Procedimento de encerramento confirmado':
            encerr = s
    med = lambda v: statistics.median(v) if v else None  # noqa: E731
    return {
        'votos_por_hora': por_hora,
        'computados_antes': n_antes, 'computados_depois': n_depois,
        'dur_med_antes': med(dur_antes), 'dur_med_depois': med(dur_depois),
        'dur_p90_antes': _q(dur_antes, .9), 'dur_p90_depois': _q(dur_depois, .9),
        'gap_med_antes': med(gap_antes), 'gap_med_depois': med(gap_depois),
        'gap_min_depois': min(gap_depois) if gap_depois else None,
        'rajada_depois': rajada_depois,
        'tentativas_por_eleitor_antes': tent_antes / n_antes if n_antes else None,
        'tentativas_por_eleitor_depois': tent_depois / n_depois if n_depois else None,
        'manual_depois': manual_depois, 'bio_depois': bio_depois,
        'pronta_s': pronta, 'encerramento_s': encerr,
    }
