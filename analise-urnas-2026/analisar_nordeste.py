"""Nordeste isolado, com foco nos votos presidenciais após 17h de Brasília.

Usa dados/secoes_2026_1t.csv.gz (BU + log + perfil) e, se existir, dados/tempos/
(ritmo de votação extraído dos logs por coletar_tempos.py).
Saída: resultados/nordeste/*.csv e resultados/nordeste/resumo.json

A: descrição por UF, município e colégio
B: o que explica votar após as 17h (variáveis operacionais e de perfil)
C: associação com a margem Lula − Flávio, do bruto ao mesmo colégio + perfil
D: dose-resposta por faixas de votos após 17h
E: testes por município (BH)
F: ritmo da votação antes e depois das 17h (se houver dados de tempos)
"""
import glob
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analisar import PERFIL, bh, demean, ols_fe

AQUI = Path(__file__).parent
OUT = AQUI / 'resultados' / 'nordeste'
NE = ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE']
FAIXAS = [(-0.01, 0, '0%'), (0, 5, 'até 5%'), (5, 10, '5–10%'), (10, 20, '10–20%'), (20, 30, '20–30%'), (30, 101, '30%+')]


def carregar():
    d = pd.read_csv(AQUI / 'dados' / 'secoes_2026_1t.csv.gz', low_memory=False)
    d = d[d.uf.isin(NE)].copy()
    d['id_municipio'] = d.uf + '-' + d.cd_municipio.astype(str)
    d['id_local'] = d.id_municipio + '-' + d.nr_zona.astype(str) + '-' + d.nr_local.astype(str)
    d['log_conciliado'] = d.log_conciliado.astype(bool)
    d['com_biometria'] = d.hab_biometria + d.hab_biografia
    d['pct_sem_cadastro'] = 100 * d.sem_biometria / d.comparecimento
    d['pct_falha_bio'] = 100 * d.hab_biografia / d.com_biometria
    d['pct_comparecimento'] = 100 * d.comparecimento / d.aptos
    d['pct_apos_corte'] = np.where(d.log_conciliado, 100 * d.pres_apos_corte / d.log_presidente, np.nan)
    d['margem'] = 100 * (d.v_13 - d.v_22) / d.validos
    d['pct_13'] = 100 * d.v_13 / d.validos
    d['pct_22'] = 100 * d.v_22 / d.validos
    d['log_aptos'] = np.log(d.aptos.clip(lower=1))
    d['idade_60_mais'] = d.pct_idade_60_69 + d.pct_idade_70_mais
    for m in ['UE2013', 'UE2015', 'UE2020']:
        d[f'urna_{m}'] = (d.modelo_urna == m).astype(float)
    return d


def agg(g):
    s = g[['comparecimento', 'sem_biometria', 'hab_biografia', 'com_biometria', 'validos', 'v_13', 'v_22']].sum()
    c = g[g.log_conciliado]
    return pd.Series({
        'secoes': len(g), 'comparecimento': s.comparecimento,
        'pres_log': c.log_presidente.sum(), 'pres_apos': c.pres_apos_corte.sum(),
        'pres_apos_hab_antes': c.pres_apos_corte_hab_antes.sum(),
        'pres_apos_mais_1h': c.pres_apos_corte_mais_1h.sum(),
        'pct_apos': 100 * c.pres_apos_corte.sum() / c.log_presidente.sum() if len(c) else np.nan,
        'secoes_com_apos': int((c.pres_apos_corte > 0).sum()),
        'secoes_apos_30': int((c.pres_apos_corte / c.log_presidente >= .3).sum()),
        'pct_sem_cadastro': 100 * s.sem_biometria / s.comparecimento,
        'pct_falha_bio': 100 * s.hab_biografia / s.com_biometria,
        'pct_13': 100 * s.v_13 / s.validos, 'pct_22': 100 * s.v_22 / s.validos,
    })


def modelo(d, y, xs, fe, cluster):
    X = d[xs].to_numpy(float)
    b, se, p, G, r2 = ols_fe(d[y].to_numpy(float), X, d.validos.to_numpy(float), fe, d[cluster].to_numpy())
    return [{'variavel': v, 'coef': b[j], 'ep': se[j], 'ic_inf': b[j] - 1.96 * se[j], 'ic_sup': b[j] + 1.96 * se[j],
             'p': p[j]} for j, v in enumerate(xs)], r2


def residualizar(d, cols, fe, ctrl):
    w = d.validos.to_numpy(float)
    C = demean(d[ctrl].to_numpy(float), fe, w)
    Cw = C * w[:, None]
    P = np.linalg.pinv(Cw.T @ C)
    out = {}
    for c in cols:
        a = demean(d[[c]].to_numpy(float), fe, w)[:, 0]
        out[c] = a - C @ (P @ (Cw.T @ a))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = carregar()
    m = d[d.log_conciliado & (d.validos >= 20) & d[PERFIL].notna().all(axis=1) & d.pct_falha_bio.notna()].copy()
    res = {'secoes': int(len(d)), 'secoes_modelo': int(len(m))}

    # A. Descrição
    por_uf = d.groupby('uf').apply(agg, include_groups=False)
    por_uf.loc['Nordeste'] = agg(d)
    por_uf.reset_index().to_csv(OUT / 'por_uf.csv', index=False)
    res['por_uf'] = por_uf.reset_index().to_dict(orient='records')
    mun = d.groupby(['uf', 'NM_MUNICIPIO']).apply(agg, include_groups=False).reset_index()
    mun.to_csv(OUT / 'por_municipio.csv', index=False)
    res['municipios_top'] = mun[mun.secoes >= 30].nlargest(25, 'pct_apos').to_dict(orient='records')
    loc = d.groupby(['uf', 'NM_MUNICIPIO', 'nr_zona', 'nr_local', 'NM_LOCAL_VOTACAO']).apply(agg, include_groups=False).reset_index()
    loc.to_csv(OUT / 'por_local.csv.gz', index=False, compression='gzip')
    res['locais_top'] = loc[loc.secoes >= 5].nlargest(25, 'pct_apos').to_dict(orient='records')

    # B. Determinantes de votar após 17h (mesmo colégio e mesmo município)
    det_x = ['log_aptos', 'pct_comparecimento', 'pct_falha_bio', 'pct_sem_cadastro', 'urna_UE2013', 'urna_UE2015',
             'urna_UE2020', 'idade_60_mais', 'pct_idade_16_24', 'pct_escol_ate_fund_incompleto', 'pct_escol_superior',
             'pct_feminino']
    res['determinantes'] = {}
    for nome, fe in [('mesmo município', m.id_municipio.to_numpy()), ('mesmo colégio', m.id_local.to_numpy())]:
        rows, r2 = modelo(m, 'pct_apos_corte', det_x, fe, 'id_municipio')
        res['determinantes'][nome] = {'coef': rows, 'r2_within': r2}
    # padronizado: efeito de 1 desvio-padrão (dentro do município) em p.p. de votos após 17h
    sd = {v: float(np.std(demean(m[[v]].to_numpy(float), m.id_municipio.to_numpy(), m.validos.to_numpy(float))[:, 0]))
          for v in det_x}
    for r in res['determinantes']['mesmo município']['coef']:
        r['efeito_1dp'] = r['coef'] * sd[r['variavel']]

    # C. Associação com o voto
    ind = ['pct_apos_corte', 'pct_falha_bio', 'pct_sem_cadastro']
    ctrl = ['pct_comparecimento', 'log_aptos', 'urna_UE2013', 'urna_UE2015', 'urna_UE2020']
    specs = [('Nordeste, sem ajuste', None, []), ('Dentro da UF', m.uf.to_numpy(), []),
             ('Dentro do município', m.id_municipio.to_numpy(), []),
             ('Dentro do colégio', m.id_local.to_numpy(), []),
             ('Colégio + perfil', m.id_local.to_numpy(), PERFIL)]
    res['associacao'] = []
    for yv in ['margem', 'pct_13', 'pct_22']:
        for nome, fe, extra in specs:
            rows, r2 = modelo(m, yv, ind + ctrl + extra, fe, 'id_municipio')
            for r in rows:
                if r['variavel'] in ind:
                    res['associacao'].append({'desfecho': yv, 'modelo': nome, **r})
    pd.DataFrame(res['associacao']).to_csv(OUT / 'associacao.csv', index=False)
    res['associacao_uf'] = []
    for uf, g in m.groupby('uf'):
        rows, _ = modelo(g, 'margem', ind + ctrl + PERFIL, g.id_local.to_numpy(), 'id_municipio')
        r = next(x for x in rows if x['variavel'] == 'pct_apos_corte')
        res['associacao_uf'].append({'uf': uf, **r, 'n': len(g)})
    q = bh([r['p'] for r in res['associacao_uf']])
    for r, qq in zip(res['associacao_uf'], q):
        r['q'] = qq

    # D. Dose-resposta (bruto e dentro do colégio + perfil)
    rs = residualizar(m, ['margem', 'pct_apos_corte'], m.id_local.to_numpy(), ['pct_falha_bio', 'pct_sem_cadastro'] + ctrl + PERFIL)
    m['margem_res'] = rs['margem']
    m['faixa'] = pd.cut(m.pct_apos_corte, [f[0] for f in FAIXAS] + [101], labels=[f[2] for f in FAIXAS])
    w = m.validos
    dose = []
    for lab, g in m.groupby('faixa', observed=True):
        ww = w[g.index]
        dose.append({'faixa': lab, 'secoes': len(g), 'margem_bruta': float(np.average(g.margem, weights=ww)),
                     'margem_mesmo_colegio': float(np.average(g.margem_res, weights=ww)),
                     'ep_mesmo_colegio': float(np.sqrt(np.average((g.margem_res - np.average(g.margem_res, weights=ww)) ** 2, weights=ww) / len(g)))})
    res['dose_resposta'] = dose

    # E. Municípios
    out = []
    for mid, g in m.groupby('id_municipio'):
        if len(g) < 40 or g.id_local.nunique() < 5 or g.pct_apos_corte.std() == 0:
            continue
        xs = [c for c in ind + ctrl + PERFIL if g[c].std() > 0]
        if len(g) - g.id_local.nunique() - len(xs) < 15:  # graus de liberdade insuficientes
            continue
        try:
            rows, _ = modelo(g, 'margem', xs, g.id_local.to_numpy(), 'id_local')
        except np.linalg.LinAlgError:
            continue
        r = next(x for x in rows if x['variavel'] == 'pct_apos_corte')
        if not np.isfinite(r['ep']) or r['ep'] < 1e-6:
            continue
        out.append({'municipio': g.NM_MUNICIPIO.iloc[0], 'uf': g.uf.iloc[0], 'secoes': len(g),
                    'pct_apos': float(100 * g.pres_apos_corte.sum() / g.log_presidente.sum()), **r})
    tm = pd.DataFrame(out)
    tm['q'] = bh(tm.p)
    tm.to_csv(OUT / 'testes_municipio.csv', index=False)
    res['testes_municipio'] = {'testados': int(len(tm)), 'p_005': int((tm.p < .05).sum()),
                               'esperado': round(.05 * len(tm), 1), 'q_005': int((tm.q < .05).sum()),
                               'q_005_pos': int(((tm.q < .05) & (tm.coef > 0)).sum()),
                               'q_005_neg': int(((tm.q < .05) & (tm.coef < 0)).sum()),
                               'significativos': tm[tm.q < .05].sort_values('q').to_dict(orient='records')}

    # F. Ritmo da votação
    tf = sorted(glob.glob(str(AQUI / 'dados' / 'tempos' / 'tempos_*.jsonl.gz')))
    if tf:
        t = pd.DataFrame([json.loads(x) for f in tf for x in gzip.open(f, 'rt')])
        t = t.merge(d[['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'log_conciliado', 'pres_apos_corte', 'log_presidente',
                       'comparecimento', 'modelo_urna', 'corte_local_h']], on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'])
        t = t[t.log_conciliado]
        vh = np.array(t.votos_por_hora.tolist())
        t['pct_apos'] = 100 * t.pres_apos_corte / t.log_presidente
        grupos = {'Sem votos após 17h': t.pct_apos == 0, 'Até 10% após 17h': (t.pct_apos > 0) & (t.pct_apos <= 10),
                  '10–30% após 17h': (t.pct_apos > 10) & (t.pct_apos < 30), '30%+ após 17h': t.pct_apos >= 30}
        ritmo = {}
        for nome, msk in grupos.items():
            g = t[msk]
            ritmo[nome] = {
                'secoes': int(msk.sum()),
                'votos_por_hora_media': (vh[msk.to_numpy()].mean(axis=0)).round(2).tolist(),
                'dur_med_antes': float(g.dur_med_antes.median()), 'dur_med_depois': float(g.dur_med_depois.median()) if g.dur_med_depois.notna().any() else None,
                'gap_med_antes': float(g.gap_med_antes.median()), 'gap_med_depois': float(g.gap_med_depois.median()) if g.gap_med_depois.notna().any() else None,
                'tent_antes': float(g.tentativas_por_eleitor_antes.mean()),
                'comparecimento_medio': float(g.comparecimento.mean()),
                'ue2013_2015': float(g.modelo_urna.isin(['UE2013', 'UE2015']).mean() * 100),
            }
        dep = t[t.computados_depois > 0]
        tot_dep = dep.computados_depois.sum()
        res['ritmo'] = {
            'grupos': ritmo,
            'secoes_com_tempos': int(len(t)),
            'votos_apos': int(tot_dep),
            'pct_bio_apos': float(100 * dep.bio_depois.sum() / tot_dep),
            'pct_manual_apos': float(100 * dep.manual_depois.sum() / tot_dep),
            'votos_rajada_apos': int(dep.rajada_depois.sum()),
            'secoes_rajada_5mais': int((dep.rajada_depois >= 5).sum()),
            'secoes_gap_min_abaixo_20s': int((dep.gap_min_depois < 20).sum()),
            'dur_mediana_apos_vs_antes': float((dep.dur_med_depois - dep.dur_med_antes).median()),
            'gap_mediano_apos_vs_antes': float((dep.gap_med_depois - dep.gap_med_antes).median()),
            'secoes_dur_mediana_apos_menor_30s': int((dep.dur_med_depois < 30).sum()),
            'secoes_com_votos_apos': int(len(dep)),
        }
        cols = ['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'pct_apos', 'computados_depois', 'dur_med_antes',
                'dur_med_depois', 'gap_med_antes', 'gap_med_depois', 'gap_min_depois', 'rajada_depois',
                'manual_depois', 'bio_depois', 'tentativas_por_eleitor_antes', 'tentativas_por_eleitor_depois']
        t[cols].to_csv(OUT / 'ritmo_secao.csv.gz', index=False, compression='gzip')
        res['ritmo']['secoes_rajada_top'] = t.nlargest(15, 'rajada_depois')[cols].to_dict(orient='records')

    (OUT / 'resumo.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ['secoes', 'secoes_modelo', 'testes_municipio']}, ensure_ascii=False, default=float)[:1500])


if __name__ == '__main__':
    main()
