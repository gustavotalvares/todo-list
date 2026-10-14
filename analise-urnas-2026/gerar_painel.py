"""Gera o painel HTML (painel.html) a partir de resultados/resumo.json e dos agregados.

Uso: python gerar_painel.py
"""
import json
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
RES = AQUI / 'resultados'


def main():
    r = json.loads((RES / 'resumo.json').read_text())
    mun = pd.read_csv(RES / 'agregado_municipio.csv.gz')
    cols = ['uf', 'NM_MUNICIPIO', 'secoes', 'comparecimento', 'pct_sem_cadastro', 'pct_falha_bio', 'pct_apos_corte',
            'pres_apos_corte', 'pct_13', 'pct_22']
    mun = mun[cols].round(2)
    data = {
        'resumo': {k: r[k] for k in ['candidatos', 'qualidade', 'brasil', 'testes_municipio', 'testes_local',
                                     'binned_local', 'distribuicao', 'brasil_sem_zz', 'secoes_cadastro', 'secoes_com_voto_apos_corte',
                                     'histograma_apos_corte']},
        'uf': [{k: v for k, v in u.items() if not k.startswith('v_')} for u in r['uf']],
        'reg': [x for x in r['regressoes'] if x['desfecho'] in ('margem_13_22', 'pct_13', 'pct_22')],
        'reg_uf': r['regressoes_uf'],
        'mun': mun.values.tolist(),
    }
    data['resumo']['histograma_apos_corte'] = {str(int(float(k))): v for k, v in
                                               data['resumo']['histograma_apos_corte'].items()}
    tpl = (AQUI / 'painel_template.html').read_text()
    html = tpl.replace('/*__DADOS__*/null', json.dumps(data, ensure_ascii=False, separators=(',', ':'),
                                                       default=float).replace('NaN', 'null'))
    (AQUI / 'painel.html').write_text(html)
    print('painel.html', len(html) // 1024, 'KB')


if __name__ == '__main__':
    main()
