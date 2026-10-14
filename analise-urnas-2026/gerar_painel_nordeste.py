"""Gera painel_nordeste.html a partir de resultados/nordeste/resumo.json.

Uso: python gerar_painel_nordeste.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
NE = ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE']


def main():
    r = json.loads((AQUI / 'resultados' / 'nordeste' / 'resumo.json').read_text())
    d = pd.read_csv(AQUI / 'dados' / 'secoes_2026_1t.csv.gz', low_memory=False,
                    usecols=['uf', 'hab_biometria', 'comparecimento', 'log_mesario_habilitou', 'log_conciliado',
                             'pres_apos_corte', 'log_presidente'])
    d = d[d.uf.isin(NE)]
    c = d[d.log_conciliado.astype(bool)]
    ritmo = pd.read_csv(AQUI / 'resultados' / 'nordeste' / 'ritmo_secao.csv.gz')
    r['bio_dia'] = 100 * d.hab_biometria.sum() / d.comparecimento.sum()
    r['manual_dia'] = 100 * d.log_mesario_habilitou.sum() / d.comparecimento.sum()
    r['p90_apos'] = float(np.percentile(100 * c.pres_apos_corte / c.log_presidente, 90))
    r['gap_min'] = float(ritmo.gap_min_depois.min())
    r['ritmo'].pop('secoes_rajada_top', None)
    th = AQUI / 'resultados' / 'nordeste' / 'teste_hora.json'
    if th.exists():
        r['teste_hora'] = json.loads(th.read_text())
    tpl = (AQUI / 'painel_nordeste_template.html').read_text()
    css = re.search(r'<style>.*?</style>', (AQUI / 'painel_template.html').read_text(), re.S).group(0)
    html = tpl.replace('/*__CSS__*/', css).replace(
        '/*__DADOS__*/null', json.dumps(r, ensure_ascii=False, separators=(',', ':'), default=float).replace('NaN', 'null'))
    (AQUI / 'painel_nordeste.html').write_text(html)
    print('painel_nordeste.html', len(html) // 1024, 'KB')


if __name__ == '__main__':
    main()
