"""Extrai do cadastro oficial de locais de votação (1º turno 2026) os nomes de
município e local, coordenadas e situação de agregação de cada seção.

Uso: python preparar_locais.py eleitorado_local_votacao_2026.zip dados/locais.csv.gz
Fonte: https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2026.zip
"""
import sys
import zipfile

import pandas as pd

COLS = ['SG_UF', 'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'DS_TIPO_SECAO_AGREGADA',
        'NR_SECAO_PRINCIPAL', 'NR_LOCAL_VOTACAO', 'NM_LOCAL_VOTACAO', 'DS_TIPO_LOCAL', 'NM_BAIRRO',
        'NR_LATITUDE', 'NR_LONGITUDE', 'QT_ELEITOR_SECAO', 'NR_TURNO']


def main(src, dest):
    z = zipfile.ZipFile(src)
    name = next(n for n in z.namelist() if n.endswith('_BRASIL.csv'))
    df = pd.read_csv(z.open(name), sep=';', encoding='latin1', usecols=COLS, dtype=str)
    df = df[df.NR_TURNO == '1'].drop(columns='NR_TURNO')
    for c in ['CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'NR_SECAO_PRINCIPAL', 'NR_LOCAL_VOTACAO', 'QT_ELEITOR_SECAO']:
        df[c] = pd.to_numeric(df[c]).astype('Int64')
    for c in ['NR_LATITUDE', 'NR_LONGITUDE']:
        df[c] = pd.to_numeric(df[c].str.replace(',', '.'), errors='coerce')
    df = df.drop_duplicates(['SG_UF', 'CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO'])
    df.to_csv(dest, index=False, compression='gzip')
    print(len(df), 'seções;', df.DS_TIPO_SECAO_AGREGADA.value_counts().to_dict())


if __name__ == '__main__':
    main(*sys.argv[1:3])
