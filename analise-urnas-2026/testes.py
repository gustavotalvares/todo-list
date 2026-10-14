"""Testes do decodificador com BUs e logs reais (Alto Alegre–RR, zona 3).

Valores esperados conferidos no piloto contra o decodificador do aplicativo
Resultados do TSE e contra o CSV oficial do boletim de urna.
Uso: python testes.py
"""
from pathlib import Path

from urnas.decod import FormatoInesperado, decode_bu, parse_log

A = Path(__file__).parent / 'amostras'
ESPERADO = {  # seção: (comparecimento, sem cadastro, biometria, biografia, Lula, Flávio)
    13: (213, 5, 200, 8, 48, 147),
    155: (234, 1, 227, 6, 48, 171),
    241: (192, 13, 174, 5, 30, 149),
}


def main():
    for sec, (comp, sem, bio, biog, lula, flavio) in ESPERADO.items():
        raw = (A / f'o03220rr030500003{sec:04d}-bu.dat').read_bytes()
        d = decode_bu(raw)
        assert (d['cd_municipio'], d['nr_zona'], d['nr_secao']) == (3050, 3, sec)
        assert (d['comparecimento'], d['sem_biometria'], d['hab_biometria'], d['hab_biografia']) == (comp, sem, bio, biog)
        assert d['votos']['13'] == lula and d['votos']['22'] == flavio
        assert d['validos'] + d['brancos'] + d['nulos'] == comp
        try:
            decode_bu(raw[:-1])
        except (FormatoInesperado, IndexError):
            pass
        else:
            raise AssertionError('BU truncado foi aceito')
        lg = parse_log((A / f'o03220rr030500003{sec:04d}-log.jez').read_bytes())
        assert lg['log_presidente'] + lg['log_nulo_suspensao_pres'] == comp
        assert lg['log_habilitados'] - lg['log_suspenso_sem_voto'] == comp
        assert lg['log_hab_biometrica_efetiva'] == bio
        assert lg['pres_apos_16h'] == 0  # RR (UTC−4): 16h local = 17h de Brasília
        assert lg['pronta'].startswith('07:0')
    print('ok: 3 seções conferem (BU, log, biometria, votos)')


if __name__ == '__main__':
    main()
