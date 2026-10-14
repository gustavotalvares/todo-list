"""Análise estatística seção a seção — 1º turno de 2026, Presidente.

Entrada: saídas de ``coletar.py`` (secoes_<UF>.jsonl.gz) e ``preparar_locais.py``.
Saída: ``dados/secoes_2026_1t.csv.gz`` (base por seção) e ``resultados/``.

Indicadores por seção (denominadores explícitos):
  pct_sem_cadastro  = votantes sem biometria cadastrada / comparecimento
  pct_falha_bio     = com biometria mas liberados por dados pessoais
                      / (habilitados por biometria + liberados por dados pessoais)
  pct_sem_reconh    = (sem cadastro + falha) / comparecimento
  pct_apos_corte    = confirmações do voto presidencial após 17h de Brasília
                      (equivalente local) / confirmações presidenciais no log

A unidade é a seção. Associações entre seções NÃO revelam em quem votaram os
eleitores de cada grupo (falácia ecológica) e não demonstram causa ou fraude.

Uso: python analisar.py --secoes DIR --locais locais.csv.gz
"""
import argparse
import glob
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).parent
RES = AQUI / 'resultados'
CORTES = (15, 16, 17, 18, 19)
INDICADORES = ['pct_sem_cadastro', 'pct_falha_bio', 'pct_apos_corte']
ROTULOS = {'pct_sem_cadastro': 'Sem cadastro biométrico (% dos votantes)',
           'pct_falha_bio': 'Falha de reconhecimento (% dos que tinham biometria)',
           'pct_apos_corte': 'Votos presidenciais após 17h de Brasília (% da seção)',
           'pct_sem_reconh': 'Liberados sem reconhecimento, qualquer motivo (%)'}


PERFIL = ['pct_feminino', 'pct_idade_16_24', 'pct_idade_45_59', 'pct_idade_60_69', 'pct_idade_70_mais',
          'pct_escol_ate_fund_incompleto', 'pct_escol_superior']


def anexar_perfil(df, perfil_path, locais_path):
    """Soma o perfil das seções agregadas à seção principal (o BU da principal inclui as agregadas)."""
    pf = pd.read_csv(perfil_path, dtype={'uf': str})
    loc = pd.read_csv(locais_path, dtype={'SG_UF': str}, usecols=['SG_UF', 'CD_MUNICIPIO', 'NR_ZONA', 'NR_SECAO',
                                                                   'NR_SECAO_PRINCIPAL'])
    loc.columns = ['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'principal']
    pf = pf.merge(loc, on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'], how='left')
    pf['nr_secao'] = np.where(pf.principal.fillna(-1) > 0, pf.principal, pf.nr_secao).astype(int)
    pcts = [c for c in pf.columns if c.startswith('pct_')]
    for c in pcts:
        pf[c] = pf[c] * pf.eleitores_perfil / 100
    g = pf.groupby(['uf', 'cd_municipio', 'nr_zona', 'nr_secao'])[['eleitores_perfil'] + pcts].sum()
    for c in pcts:
        g[c] = 100 * g[c] / g.eleitores_perfil
    return df.merge(g.reset_index(), on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'], how='left')


def carregar(secoes_dir, locais_path):
    rows = []
    for f in sorted(glob.glob(str(Path(secoes_dir) / 'secoes_*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for line in fh:
                r = json.loads(line)
                votos = r.pop('votos')
                for k, v in votos.items():
                    r[f'v_{k}'] = v
                rows.append(r)
    df = pd.DataFrame(rows)
    vcols = [c for c in df.columns if c.startswith('v_')]
    df[vcols] = df[vcols].fillna(0).astype(int)
    loc = pd.read_csv(locais_path, dtype={'SG_UF': str})
    loc = loc.rename(columns={'SG_UF': 'uf', 'CD_MUNICIPIO': 'cd_municipio', 'NR_ZONA': 'nr_zona',
                              'NR_SECAO': 'nr_secao'})
    df = df.merge(loc[['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'NM_MUNICIPIO', 'NM_LOCAL_VOTACAO',
                       'DS_TIPO_LOCAL', 'NR_LATITUDE', 'NR_LONGITUDE', 'QT_ELEITOR_SECAO']],
                  on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'], how='left')
    return df, vcols


def derivar(df):
    df['id_municipio'] = df.uf + '-' + df.cd_municipio.astype(str)
    df['id_local'] = df.id_municipio + '-' + df.nr_zona.astype(str) + '-' + df.nr_local.astype(str)
    df['com_biometria'] = df.hab_biometria + df.hab_biografia
    df['sem_reconhecimento'] = df.sem_biometria + df.hab_biografia
    with np.errstate(divide='ignore', invalid='ignore'):
        df['pct_sem_cadastro'] = 100 * df.sem_biometria / df.comparecimento
        df['pct_falha_bio'] = 100 * df.hab_biografia / df.com_biometria
        df['pct_sem_reconh'] = 100 * df.sem_reconhecimento / df.comparecimento
        df['pct_comparecimento'] = 100 * df.comparecimento / df.aptos

    # Horário: urnas usam o fuso local. A votação é unificada 8h–17h de Brasília
    # (no exterior, 8h–17h locais), então o corte local = abertura típica do
    # município + 9h. A abertura típica é a mediana de "Urna pronta para receber votos".
    def hora(s):
        return np.nan if not isinstance(s, str) else int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8])
    df['pronta_s'] = df.pronta.map(hora)
    abertura = df.groupby('id_municipio').pronta_s.median().div(3600).round()
    df['abertura_local_h'] = df.id_municipio.map(abertura)
    df['corte_local_h'] = df.abertura_local_h + 9
    df['log_conciliado'] = df.log_ok.fillna(False).astype(bool) & (
        df.log_presidente.fillna(-1) + df.log_nulo_suspensao_pres.fillna(0) == df.comparecimento)
    for nome, base in [('pres_apos_corte', 'pres_apos_{}h'), ('hab_apos_corte', 'hab_apos_{}h'),
                       ('pres_apos_corte_hab_antes', 'pres_apos_{}h_hab_antes'),
                       ('pres_apos_corte_mais_1h', None)]:
        df[nome] = np.nan
        for c in CORTES:
            m = df.corte_local_h == c
            if base:
                df.loc[m, nome] = df.loc[m, base.format(c)]
            elif c + 1 in CORTES:
                df.loc[m, nome] = df.loc[m, f'pres_apos_{c + 1}h']
    with np.errstate(divide='ignore', invalid='ignore'):
        df['pct_apos_corte'] = 100 * df.pres_apos_corte / df.log_presidente
    df.loc[~df.log_conciliado, 'pct_apos_corte'] = np.nan
    return df


def agregar(df, vcols, chave, cands):
    soma = ['aptos', 'comparecimento', 'sem_biometria', 'hab_biometria', 'hab_biografia', 'com_biometria',
            'validos', 'brancos', 'nulos'] + vcols
    g = df.groupby(chave, dropna=False)
    a = g[soma].sum()
    a['secoes'] = g.size()
    lc = df[df.log_conciliado].groupby(chave, dropna=False)
    a['secoes_log_conciliado'] = lc.size()
    a['pres_log'] = lc.log_presidente.sum()
    a['pres_apos_corte'] = lc.pres_apos_corte.sum()
    a['pres_apos_corte_hab_antes'] = lc.pres_apos_corte_hab_antes.sum()
    a['hab_apos_corte'] = lc.hab_apos_corte.sum()
    a = a.fillna(0)
    a['pct_comparecimento'] = 100 * a.comparecimento / a.aptos
    a['pct_sem_cadastro'] = 100 * a.sem_biometria / a.comparecimento
    a['pct_falha_bio'] = 100 * a.hab_biografia / a.com_biometria
    a['pct_sem_reconh'] = 100 * (a.sem_biometria + a.hab_biografia) / a.comparecimento
    a['pct_apos_corte'] = 100 * a.pres_apos_corte / a.pres_log
    for c in cands:
        a[f'pct_{c}'] = 100 * a[f'v_{c}'] / a.validos
    return a.drop(columns=[v for v in vcols if v[2:] not in cands]).reset_index()


# ---------- Regressão ponderada com efeitos fixos absorvidos e EP agrupado ----------

def demean(arr, groups, w):
    """Remove a média ponderada por grupo de cada coluna (transformação within)."""
    if groups is None:
        return arr - np.average(arr, axis=0, weights=w)
    codes, _ = pd.factorize(groups)
    sw = np.bincount(codes, weights=w)
    out = np.empty_like(arr)
    for j in range(arr.shape[1]):
        m = np.bincount(codes, weights=w * arr[:, j]) / sw
        out[:, j] = arr[:, j] - m[codes]
    return out


def ols_fe(y, X, w, fe, cluster):
    Z = demean(np.column_stack([y, X]), fe, w)
    yt, Xt = Z[:, 0], Z[:, 1:]
    sw = np.sqrt(w)
    XtW = Xt * w[:, None]
    bread = np.linalg.pinv(XtW.T @ Xt)
    beta = bread @ (XtW.T @ yt)
    e = yt - Xt @ beta
    codes, _ = pd.factorize(cluster)
    G = codes.max() + 1
    scores = np.zeros((G, Xt.shape[1]))
    np.add.at(scores, codes, XtW * e[:, None])
    n, k = Xt.shape
    adj = G / (G - 1) * (n - 1) / max(n - k, 1)
    V = adj * bread @ (scores.T @ scores) @ bread
    se = np.sqrt(np.diag(V))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), G - 1)
    r2w = 1 - np.sum(w * e ** 2) / np.sum(w * yt ** 2)
    _ = sw
    return beta, se, p, G, r2w


def bh(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    if ok.sum() == 0:
        return q
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    res = np.empty_like(pv)
    res[order] = np.minimum(ranked, 1)
    q[ok] = res
    return q


def amostra_modelo(df):
    m = (df.uf != 'ZZ') & df.log_conciliado & (df.validos >= 20) & (df.com_biometria > 0) & df.pct_apos_corte.notna() & df[PERFIL].notna().all(axis=1)
    return df[m].copy()


def controles(d):
    X = pd.DataFrame({'pct_comparecimento': d.pct_comparecimento, 'log_aptos': np.log(d.aptos.clip(lower=1))})
    for mdl in sorted(d.modelo_urna.fillna('ND').unique())[1:]:
        X[f'urna_{mdl}'] = (d.modelo_urna.fillna('ND') == mdl).astype(float)
    return X


SPEC_PRINCIPAL = 'EF de local + perfil do eleitorado'


def regressoes(d, cands):
    out = []
    ctrl = controles(d)
    X = pd.concat([d[INDICADORES], ctrl], axis=1)
    Xp = pd.concat([X, d[PERFIL]], axis=1)
    w = d.validos.to_numpy(float)
    specs = [('Sem efeitos fixos', None, X), ('EF de UF', d.uf.to_numpy(), X),
             ('EF de município', d.id_municipio.to_numpy(), X),
             ('EF de local de votação', d.id_local.to_numpy(), X),
             (SPEC_PRINCIPAL, d.id_local.to_numpy(), Xp)]
    ys = {f'pct_{c}': 100 * d[f'v_{c}'] / d.validos for c in cands}
    ys['margem_13_22'] = ys['pct_13'] - ys['pct_22']
    for yname, y in ys.items():
        for spec, fe, X in specs:
            b, se, p, G, r2 = ols_fe(y.to_numpy(float), X.to_numpy(float), w, fe, d.id_municipio.to_numpy())
            for j, var in enumerate(X.columns):
                if var not in INDICADORES:
                    continue
                out.append({'desfecho': yname, 'modelo': spec, 'variavel': var, 'coef_pp_por_pp': b[j],
                            'ep': se[j], 'ic95_inf': b[j] - 1.96 * se[j], 'ic95_sup': b[j] + 1.96 * se[j],
                            'p': p[j], 'n_secoes': len(d), 'clusters_municipio': G, 'r2_within': r2})
    return pd.DataFrame(out)


def regressoes_uf(d):
    out = []
    for uf, g in d.groupby('uf'):
        if g.id_municipio.nunique() < 5:
            continue
        X = pd.concat([g[INDICADORES], controles(g), g[PERFIL]], axis=1)
        X = X.loc[:, X.std() > 0]
        y = (100 * (g.v_13 - g.v_22) / g.validos).to_numpy(float)
        b, se, p, G, _ = ols_fe(y, X.to_numpy(float), g.validos.to_numpy(float), g.id_local.to_numpy(),
                                g.id_municipio.to_numpy())
        for j, var in enumerate(X.columns):
            if var in INDICADORES:
                out.append({'uf': uf, 'variavel': var, 'coef': b[j], 'ep': se[j], 'p': p[j], 'n_secoes': len(g),
                            'municipios': G})
    r = pd.DataFrame(out)
    r['q_bh'] = np.nan
    for v in INDICADORES:
        m = r.variavel == v
        r.loc[m, 'q_bh'] = bh(r.loc[m, 'p'])
    return r


def testes_por_grupo(d, grupo, min_secoes):
    """Inclinação simples (ponderada) da margem Lula−Flávio em cada indicador, dentro de cada grupo."""
    y_all = (100 * (d.v_13 - d.v_22) / d.validos).to_numpy(float)
    out = []
    for gid, idx in d.groupby(grupo).indices.items():
        if len(idx) < min_secoes:
            continue
        rec = {grupo: gid, 'secoes': len(idx)}
        y = y_all[idx]
        for v in INDICADORES:
            x = d[v].to_numpy(float)[idx]
            if np.nanstd(x) == 0 or np.nanstd(y) == 0:
                rec[f'r_{v}'] = np.nan
                rec[f'p_{v}'] = np.nan
                continue
            r, p = stats.pearsonr(x, y)
            rec[f'r_{v}'] = r
            rec[f'p_{v}'] = p
        out.append(rec)
    r = pd.DataFrame(out)
    for v in INDICADORES:
        r[f'q_{v}'] = bh(r[f'p_{v}'])
    return r


def regressoes_municipio(d, min_secoes=40, min_locais=5):
    out = []
    for mid, g in d.groupby('id_municipio'):
        if len(g) < min_secoes or g.id_local.nunique() < min_locais:
            continue
        X = pd.concat([g[INDICADORES], controles(g), g[PERFIL]], axis=1)
        X = X.loc[:, X.std() > 0]
        if not set(INDICADORES) <= set(X.columns):
            continue
        y = (100 * (g.v_13 - g.v_22) / g.validos).to_numpy(float)
        try:
            b, se, p, G, _ = ols_fe(y, X.to_numpy(float), g.validos.to_numpy(float), g.id_local.to_numpy(),
                                    g.id_local.to_numpy())
        except np.linalg.LinAlgError:
            continue
        rec = {'id_municipio': mid, 'municipio': g.NM_MUNICIPIO.iloc[0], 'secoes': len(g), 'locais': G}
        for j, var in enumerate(X.columns):
            if var in INDICADORES:
                rec[f'coef_{var}'], rec[f'ep_{var}'], rec[f'p_{var}'] = b[j], se[j], p[j]
        out.append(rec)
    r = pd.DataFrame(out)
    for v in INDICADORES:
        r[f'q_{v}'] = bh(r[f'p_{v}'])
        r[f'r_{v}'] = r[f'coef_{v}']  # sinal do efeito, para o resumo
    return r


def binned(d, cands, nbins=20):
    """Dispersão em faixas após remover médias de cada local de votação (comparação dentro do colégio)."""
    w = d.validos.to_numpy(float)
    fe = d.id_local.to_numpy()
    others = lambda v: pd.concat([d[[i for i in INDICADORES if i != v]], controles(d), d[PERFIL]], axis=1)
    res = {}

    def resid(a, C):
        A = demean(np.column_stack([a, C]), fe, w)
        Cw = A[:, 1:] * w[:, None]
        beta = np.linalg.pinv(Cw.T @ A[:, 1:]) @ (Cw.T @ A[:, 0])
        return A[:, 0] - A[:, 1:] @ beta

    for v in INDICADORES:
        C = others(v).to_numpy(float)
        x = resid(d[v].to_numpy(float), C)
        q = pd.qcut(pd.Series(x).rank(method='first'), nbins, labels=False).to_numpy()
        res[v] = {}
        for c in cands:
            y = resid((100 * d[f'v_{c}'] / d.validos).to_numpy(float), C)
            pts = []
            for b in range(nbins):
                m = q == b
                pts.append([float(np.average(x[m], weights=w[m])), float(np.average(y[m], weights=w[m]))])
            res[v][c] = pts
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--secoes', default='dados/secoes')
    ap.add_argument('--locais', default='dados/locais.csv.gz')
    ap.add_argument('--perfil', default='dados/perfil_secao.csv.gz')
    a = ap.parse_args()
    RES.mkdir(exist_ok=True)
    df, vcols = carregar(a.secoes, a.locais)
    df = derivar(df)
    df = anexar_perfil(df, a.perfil, a.locais)
    with np.errstate(divide='ignore', invalid='ignore'):
        df['pct_sem_cadastro_esperado'] = 100 - df.pct_biometria_cadastro
    nomes = pd.read_csv(AQUI / 'dados' / 'candidatos_presidente.csv', dtype={'nr_votavel': str})
    nomes = dict(zip(nomes.nr_votavel, nomes.nm_votavel))
    tot = df[vcols].sum()
    share = tot / df.validos.sum()
    cands = [c[2:] for c in share[share >= 0.02].sort_values(ascending=False).index]
    if '13' not in cands or '22' not in cands:
        raise SystemExit('Candidatos 13 e 22 esperados entre os principais.')

    base_cols = ['uf', 'NM_MUNICIPIO', 'cd_municipio', 'nr_zona', 'nr_secao', 'nr_local', 'NM_LOCAL_VOTACAO',
                 'DS_TIPO_LOCAL', 'NR_LATITUDE', 'NR_LONGITUDE', 'modelo_urna', 'aptos', 'comparecimento',
                 'sem_biometria', 'hab_biometria', 'hab_biografia', 'validos', 'brancos', 'nulos'] + sorted(
        vcols, key=lambda c: int(c[2:])) + [
        'abertura', 'encerramento', 'pronta', 'abertura_local_h', 'corte_local_h', 'log_ok', 'log_conciliado',
        'log_presidente', 'log_nulo_suspensao_pres', 'log_suspenso_sem_voto', 'pres_apos_corte',
        'pres_apos_corte_hab_antes', 'hab_apos_corte', 'pres_apos_corte_mais_1h', 'ultimo_voto_pres',
        'log_bio_mais_de_1_tentativa', 'log_mesario_habilitou', 'log_urnas_no_dia', 'eleitores_perfil',
        'pct_biometria_cadastro'] + PERFIL
    (AQUI / 'dados').mkdir(exist_ok=True)
    df[base_cols].to_csv(AQUI / 'dados' / 'secoes_2026_1t.csv.gz', index=False, compression='gzip')

    ag_br = agregar(df.assign(brasil='Brasil'), vcols, 'brasil', cands)
    ag_br_sem_zz = agregar(df[df.uf != 'ZZ'].assign(brasil='Brasil (sem exterior)'), vcols, 'brasil', cands)
    pd.concat([ag_br, ag_br_sem_zz]).to_csv(RES / 'agregado_brasil.csv', index=False)
    ag_uf = agregar(df, vcols, 'uf', cands)
    ag_uf.to_csv(RES / 'agregado_uf.csv', index=False)
    ag_mun = agregar(df, vcols, ['uf', 'cd_municipio', 'NM_MUNICIPIO'], cands)
    ag_mun.to_csv(RES / 'agregado_municipio.csv.gz', index=False, compression='gzip')
    ag_loc = agregar(df, vcols, ['uf', 'cd_municipio', 'NM_MUNICIPIO', 'nr_zona', 'nr_local', 'NM_LOCAL_VOTACAO'], cands)
    ag_loc.to_csv(RES / 'agregado_local.csv.gz', index=False, compression='gzip')

    d = amostra_modelo(df)
    reg = regressoes(d, cands)
    reg.to_csv(RES / 'regressoes_brasil.csv', index=False)
    reg_uf = regressoes_uf(d)
    reg_uf.to_csv(RES / 'regressoes_uf.csv', index=False)
    t_mun = regressoes_municipio(d)
    t_mun.to_csv(RES / 'testes_municipio.csv.gz', index=False, compression='gzip')
    t_loc = testes_por_grupo(d, 'id_local', 6)
    t_loc.to_csv(RES / 'testes_local.csv.gz', index=False, compression='gzip')
    bins = binned(d, ['13', '22'])

    def resumo_testes(t):
        r = {'grupos': int(len(t))}
        for v in INDICADORES:
            p = t[f'p_{v}'].dropna()
            q = t[f'q_{v}'].dropna()
            r[v] = {'testados': int(len(p)), 'p_menor_005': int((p < 0.05).sum()),
                    'esperado_sob_nulidade': round(0.05 * len(p), 1), 'q_bh_menor_005': int((q < 0.05).sum()),
                    'q005_r_positivo': int(((t[f'q_{v}'] < 0.05) & (t[f'r_{v}'] > 0)).sum()),
                    'q005_r_negativo': int(((t[f'q_{v}'] < 0.05) & (t[f'r_{v}'] < 0)).sum()),
                    'mediana_r': float(t[f'r_{v}'].median())}
        return r

    br = ag_br.iloc[0]
    qual = {
        'secoes_decodificadas': int(len(df)),
        'secoes_cadastro_principais_1t': None,
        'secoes_com_log': int(df.log_ok.fillna(False).sum()),
        'secoes_log_conciliado': int(df.log_conciliado.sum()),
        'secoes_amostra_modelo': int(len(d)),
        'abertura_local_por_municipio': {str(int(k)) if k == k else 'ND': int(v) for k, v in
                                         df.groupby('id_municipio').abertura_local_h.first().value_counts().items()},
        'modelos_urna': df.modelo_urna.fillna('ND').value_counts().to_dict(),
        'secoes_com_perfil': int(df.eleitores_perfil.notna().sum()),
        # validação: sem cadastro entre votantes vs. sem cadastro entre aptos (perfil)
        'corr_sem_cadastro_votantes_vs_aptos': float(df[['pct_sem_cadastro', 'pct_sem_cadastro_esperado']].corr().iloc[0, 1]),
    }
    resumo = {
        'candidatos': {c: nomes.get(c, c) for c in cands},
        'qualidade': qual,
        'brasil': {k: (float(v) if isinstance(v, (int, float, np.number)) else v) for k, v in br.items()},
        'testes_municipio': resumo_testes(t_mun),
        'testes_local': resumo_testes(t_loc),
        'binned_local': bins,
        'uf': ag_uf.to_dict(orient='records'),
        'regressoes': reg.to_dict(orient='records'),
        'regressoes_uf': reg_uf.to_dict(orient='records'),
        'distribuicao': {v: {str(p): float(df[v].quantile(p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)} for v in
                         INDICADORES + ['pct_sem_reconh']},
        'secoes_com_voto_apos_corte': int((df.pres_apos_corte > 0).sum()),
        'histograma_apos_corte': df.loc[df.log_conciliado, 'pres_apos_corte'].clip(upper=50).value_counts().sort_index().astype(int).to_dict(),
    }
    (RES / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: resumo[k] for k in ['candidatos', 'qualidade']}, ensure_ascii=False, indent=1, default=float))
    print(reg[reg.modelo.isin(['Sem efeitos fixos', SPEC_PRINCIPAL])].round(4).to_string())


if __name__ == '__main__':
    main()
