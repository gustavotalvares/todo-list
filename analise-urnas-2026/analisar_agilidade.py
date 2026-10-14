"""Nordeste: o "ganho de agilidade" depois das 17h é fila, perfil ou sinal de votos fabricados?

Entrada: dados/etapas/etapas_<UF>.jsonl.gz (coletar_tempos.py --modo etapas) + base por seção.
Saída: resultados/nordeste/agilidade.json e agilidade_secao.csv.gz

Assinaturas esperadas:
  fila      → ociosidade cai para perto de zero; cabine e identificação parecidas com a tarde
  perfil    → cabine encurta aos poucos ao longo da tarde, também em seções sem fila
  fabricado → cabine muito curta (< 20–30 s), menos digital, mais liberação pelo mesário, só após 17h
"""
import glob
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analisar import PERFIL, ols_fe
from analisar_nordeste import carregar

AQUI = Path(__file__).parent
OUT = AQUI / 'resultados' / 'nordeste'
GRUPOS = [('Sem votos após 17h', -1, 0), ('Até 10%', 0, 10), ('10–30%', 10, 30), ('30%+', 30, 101)]
HORAS = list(range(8, 21))
LIM = (15, 20, 30, 45, 60, 90, 120)


def main():
    d = carregar()
    e = pd.DataFrame([json.loads(x) for f in glob.glob(str(AQUI / 'dados/etapas/etapas_*.jsonl.gz')) for x in gzip.open(f, 'rt')])
    d = d.merge(e, on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'])
    d = d[d.log_conciliado & (d.corte_local_h == 17)].copy()
    d['grupo'] = pd.cut(d.pct_apos_corte, [g[1] for g in GRUPOS] + [101], labels=[g[0] for g in GRUPOS])
    A = {k: np.array(d[k].tolist(), float) for k in ['n', 'ocio_soma', 'ident_soma', 'cabine_soma', 'n_ocio', 'n_ident',
                                                    'bio', 'manual', 'tent']}
    F = np.array(d.cabine_faixas.tolist(), float)  # seções × 24 × 8
    res = {'secoes': int(len(d)), 'grupos': {}}

    def perfil_horario(msk):
        n = A['n'][msk].sum(axis=0)
        sdiv = lambda a, b: np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)  # noqa: E731
        f = F[msk].sum(axis=0)
        out = {}
        for h in HORAS:
            out[h] = {
                'atendimentos': float(n[h]),
                'ociosidade_s': float(sdiv(A['ocio_soma'][msk].sum(0), A['n_ocio'][msk].sum(0))[h]),
                'identificacao_s': float(sdiv(A['ident_soma'][msk].sum(0), A['n_ident'][msk].sum(0))[h]),
                'cabine_s': float(sdiv(A['cabine_soma'][msk].sum(0), n)[h]),
                'pct_biometria': float(100 * sdiv(A['bio'][msk].sum(0), n)[h]),
                'pct_mesario': float(100 * sdiv(A['manual'][msk].sum(0), n)[h]),
                'tentativas': float(sdiv(A['tent'][msk].sum(0), n)[h]),
                'pct_cabine_menos_20s': float(100 * f[h, :2].sum() / f[h].sum()) if f[h].sum() else None,
                'pct_cabine_menos_30s': float(100 * f[h, :3].sum() / f[h].sum()) if f[h].sum() else None,
            }
        return out

    for nome, _, _ in GRUPOS:
        msk = (d.grupo == nome).to_numpy()
        res['grupos'][nome] = {'secoes': int(msk.sum()), 'por_hora': perfil_horario(msk)}

    # Comparação dentro da própria seção (seções com > 10% após 17h): 14h–17h vs. após 17h
    alta = (d.pct_apos_corte > 10).to_numpy()

    def janela(a, b, key):
        return A[key][:, a:b].sum(axis=1)

    rows = pd.DataFrame({
        'n_tarde': janela(14, 17, 'n'), 'n_apos': janela(17, 24, 'n'),
        'cab_tarde': janela(14, 17, 'cabine_soma') / np.maximum(janela(14, 17, 'n'), 1),
        'cab_apos': janela(17, 24, 'cabine_soma') / np.maximum(janela(17, 24, 'n'), 1),
        'ident_tarde': janela(14, 17, 'ident_soma') / np.maximum(janela(14, 17, 'n_ident'), 1),
        'ident_apos': janela(17, 24, 'ident_soma') / np.maximum(janela(17, 24, 'n_ident'), 1),
        'ocio_tarde': janela(14, 17, 'ocio_soma') / np.maximum(janela(14, 17, 'n_ocio'), 1),
        'ocio_apos': janela(17, 24, 'ocio_soma') / np.maximum(janela(17, 24, 'n_ocio'), 1),
        'bio_tarde': 100 * janela(14, 17, 'bio') / np.maximum(janela(14, 17, 'n'), 1),
        'bio_apos': 100 * janela(17, 24, 'bio') / np.maximum(janela(17, 24, 'n'), 1),
        'curta_apos': 100 * F[:, 17:, :2].sum(axis=(1, 2)) / np.maximum(F[:, 17:, :].sum(axis=(1, 2)), 1),
        'curta_tarde': 100 * F[:, 14:17, :2].sum(axis=(1, 2)) / np.maximum(F[:, 14:17, :].sum(axis=(1, 2)), 1),
    }, index=d.index)
    d = d.join(rows)
    h = d[alta & (d.n_apos >= 10) & (d.n_tarde >= 30)].copy()
    res['dentro_da_secao'] = {
        'secoes': int(len(h)),
        'mediana': {k: float(h[k].median()) for k in rows.columns if k not in ('n_tarde', 'n_apos')},
        'pct_secoes_cabine_mais_rapida': float(100 * (h.cab_apos < h.cab_tarde).mean()),
        'pct_secoes_ocio_menor': float(100 * (h.ocio_apos < h.ocio_tarde).mean()),
    }
    # quanto da redução do intervalo entre votos vem de cada etapa (média ponderada)
    w = h.n_apos
    dif = {k: float(np.average(h[f'{k}_apos'] - h[f'{k}_tarde'], weights=w)) for k in ['ocio', 'ident', 'cab']}
    res['decomposicao_s'] = dif
    # seções suspeitas pela assinatura de votos fabricados
    susp = h[(h.cab_apos < 0.5 * h.cab_tarde) & (h.bio_apos < h.bio_tarde - 20)]
    res['secoes_assinatura_suspeita'] = {
        'criterio': 'cabine após 17h < metade da cabine 14h–17h E biometria após 17h 20+ p.p. abaixo',
        'n': int(len(susp)),
        'lista': susp[['uf', 'NM_MUNICIPIO', 'nr_zona', 'nr_secao', 'n_apos', 'cab_tarde', 'cab_apos', 'bio_tarde',
                       'bio_apos', 'curta_apos', 'margem']].round(1).to_dict(orient='records'),
    }
    res['secoes_cabine_curta_apos_30pct'] = int((h.curta_apos >= 30).sum())

    # A aceleração se associa à margem? (mesmo colégio + perfil, só seções com > 10% após 17h)
    h['acel_cabine'] = h.cab_tarde - h.cab_apos
    h['queda_bio'] = h.bio_tarde - h.bio_apos
    m = h[(h.validos >= 20) & h[PERFIL].notna().all(axis=1) & h.pct_falha_bio.notna()]
    ctrl = ['pct_apos_corte', 'pct_comparecimento', 'log_aptos', 'urna_UE2013', 'urna_UE2015', 'urna_UE2020',
            'pct_falha_bio', 'pct_sem_cadastro']
    out = []
    for nome, fe in [('Dentro do município', m.id_municipio.to_numpy()), ('Dentro do colégio', m.id_local.to_numpy())]:
        xs = ['acel_cabine', 'queda_bio'] + ctrl + PERFIL
        b, se, p, G, _ = ols_fe(m.margem.to_numpy(float), m[xs].to_numpy(float), m.validos.to_numpy(float), fe,
                                m.id_municipio.to_numpy())
        for j, x in enumerate(xs[:2]):
            out.append({'modelo': nome, 'variavel': x, 'coef': b[j], 'ep': se[j], 'p': p[j], 'secoes': len(m)})
    res['acel_vs_margem'] = out
    sd = {'acel_cabine': float(m.acel_cabine.std()), 'queda_bio': float(m.queda_bio.std())}
    res['acel_vs_margem_dp'] = sd

    d[['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'pct_apos_corte', 'n_tarde', 'n_apos', 'cab_tarde', 'cab_apos',
       'ident_tarde', 'ident_apos', 'ocio_tarde', 'ocio_apos', 'bio_tarde', 'bio_apos', 'curta_tarde', 'curta_apos']] \
        .round(2).to_csv(OUT / 'agilidade_secao.csv.gz', index=False, compression='gzip')
    (OUT / 'agilidade.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))

    for nome in res['grupos']:
        ph = pd.DataFrame(res['grupos'][nome]['por_hora']).T
        print('\n==', nome, res['grupos'][nome]['secoes'])
        print(ph.round(1).to_string())
    print(json.dumps({k: res[k] for k in ['dentro_da_secao', 'decomposicao_s', 'secoes_cabine_curta_apos_30pct',
                                          'acel_vs_margem', 'acel_vs_margem_dp']}, indent=1, default=float))
    print('suspeitas', res['secoes_assinatura_suspeita']['n'])
    print(pd.DataFrame(res['secoes_assinatura_suspeita']['lista']).head(20).to_string())


if __name__ == '__main__':
    main()
