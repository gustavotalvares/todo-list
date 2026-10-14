"""Resume o perfil do eleitorado por seção (TSE, 2026) em covariáveis por seção.

Uso: python preparar_perfil.py --saida dados/perfil_secao.csv.gz [--cache DIR]
Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitor_secao/perfil_eleitor_secao_2026_<UF>.zip

Covariáveis (proporções do eleitorado apto da seção, cadastro de jul/2026):
  pct_feminino, faixas etárias, escolaridade baixa/superior e
  pct_biometria_cadastro (eleitores com biometria cadastrada).
"""
import argparse
import subprocess
import zipfile
from pathlib import Path

import pandas as pd

URL = 'https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitor_secao/perfil_eleitor_secao_2026_{uf}.zip'
UFS = 'AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ'.split()
KEY = ['SG_UF', 'CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO']
USE = KEY + ['DS_GENERO', 'CD_FAIXA_ETARIA', 'CD_GRAU_ESCOLARIDADE', 'QT_ELEITORES', 'QT_ELEITORES_BIOMETRIA']


def faixa(cd):
    # CD_FAIXA_ETARIA codifica o intervalo como AABB (ex.: 3034 = 30 a 34; 1600 = 16 anos)
    if cd < 0:
        return 'idade_invalida'
    ini = cd // 100
    if ini < 25:
        return 'idade_16_24'
    if ini < 45:
        return 'idade_25_44'
    if ini < 60:
        return 'idade_45_59'
    if ini < 70:
        return 'idade_60_69'
    return 'idade_70_mais'


def resumir(path):
    z = zipfile.ZipFile(path)
    name = next(n for n in z.namelist() if n.endswith('.csv'))
    parts = []
    for ch in pd.read_csv(z.open(name), sep=';', encoding='latin1', usecols=USE, chunksize=2_000_000,
                          dtype={'SG_UF': str}):
        ch['CD_MUNICIPIO'] = pd.to_numeric(ch.CD_MUNICIPIO)
        q = ch.QT_ELEITORES
        f = pd.DataFrame({k: ch[k] for k in KEY})
        f['eleitores'] = q
        f['biometria_cadastro'] = ch.QT_ELEITORES_BIOMETRIA
        f['feminino'] = q * (ch.DS_GENERO == 'FEMININO')
        fx = ch.CD_FAIXA_ETARIA.map(faixa)
        for k in ['idade_16_24', 'idade_25_44', 'idade_45_59', 'idade_60_69', 'idade_70_mais']:
            f[k] = q * (fx == k)
        # 1 analfabeto, 2 lê e escreve, 3 fund. incompleto | 8 superior completo
        f['escol_ate_fund_incompleto'] = q * ch.CD_GRAU_ESCOLARIDADE.isin([1, 2, 3])
        f['escol_superior'] = q * (ch.CD_GRAU_ESCOLARIDADE == 8)
        parts.append(f.groupby(KEY).sum())
    s = pd.concat(parts).groupby(level=KEY).sum()
    out = pd.DataFrame(index=s.index)
    out['eleitores_perfil'] = s.eleitores
    for c in s.columns.drop('eleitores'):
        out['pct_' + c] = 100 * s[c] / s.eleitores
    return out.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida', default='dados/perfil_secao.csv.gz')
    ap.add_argument('--cache', default='/tmp/perfil')
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    res = []
    for uf in UFS:
        p = cache / f'perfil_{uf}.zip'
        if not p.exists():
            subprocess.run(['curl', '-sS', '--retry', '5', '-o', str(p) + '.part', URL.format(uf=uf)], check=True)
            Path(str(p) + '.part').rename(p)
        r = resumir(p)
        p.unlink()
        print(uf, len(r), 'seções', flush=True)
        res.append(r)
    df = pd.concat(res).rename(columns={'SG_UF': 'uf', 'CD_MUNICIPIO': 'cd_municipio', 'NR_ZONA': 'nr_zona',
                                        'NR_SECAO': 'nr_secao'})
    df.round(3).to_csv(a.saida, index=False, compression='gzip')


if __name__ == '__main__':
    main()
