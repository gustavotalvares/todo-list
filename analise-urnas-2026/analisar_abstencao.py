"""Nordeste: seções com muitos votos após 17h têm abstenção diferente das demais?

Abstenção = (aptos − comparecimento) / aptos. Se votos fossem lançados em nome de ausentes no fim
do dia, essas seções teriam abstenção anormalmente baixa e o excesso de comparecimento viria sem
digital (eleitor ausente não põe o dedo no leitor).
Saída: resultados/nordeste/abstencao.json
"""
import glob, gzip, json
from pathlib import Path
import numpy as np, pandas as pd
from analisar import PERFIL, ols_fe
from analisar_nordeste import carregar

AQUI = Path(__file__).parent
OUT = AQUI / 'resultados' / 'nordeste'
d = carregar()
d = d[d.log_conciliado & (d.aptos > 0) & (d.corte_local_h == 17)].copy()
d['abstencao'] = 100 * (d.aptos - d.comparecimento) / d.aptos
d['grupo'] = pd.cut(d.pct_apos_corte, [-1, 0, 10, 30, 101], labels=['Sem votos após 17h', 'Até 10%', '10–30%', '30%+'])
res = {'secoes': int(len(d))}

# 1. Descrição por grupo (abstenção agregada = soma de ausentes / soma de aptos)
g = d.groupby('grupo', observed=True)
res['por_grupo'] = [{'grupo': k, 'secoes': int(len(x)), 'aptos_medio': float(x.aptos.mean()),
                     'abstencao': float(100 * (x.aptos - x.comparecimento).sum() / x.aptos.sum()),
                     'abstencao_mediana_secao': float(x.abstencao.median()),
                     'pct_secoes_abst_menor_10': float(100 * (x.abstencao < 10).mean()),
                     'pct_idade_70_mais': float(np.average(x.pct_idade_70_mais.fillna(0), weights=x.aptos)),
                     'pct_idade_16_24': float(np.average(x.pct_idade_16_24.fillna(0), weights=x.aptos))}
                    for k, x in g]

# 2. Regressões: abstenção ~ % de votos após 17h (e faixas), do bruto ao mesmo colégio + perfil
m = d[d[PERFIL].notna().all(axis=1) & d.pct_falha_bio.notna()].copy()
for lab in ['Até 10%', '10–30%', '30%+']:
    m['g_' + lab] = (m.grupo == lab).astype(float)
ctrl = ['log_aptos', 'urna_UE2013', 'urna_UE2015', 'urna_UE2020']
specs = [('Nordeste, sem ajuste', None, []), ('Dentro do município', m.id_municipio.to_numpy(), []),
         ('Dentro do colégio', m.id_local.to_numpy(), []), ('Colégio + perfil', m.id_local.to_numpy(), PERFIL)]
w = m.aptos.to_numpy(float)
res['regressao_continua'], res['regressao_faixas'] = [], []
for nome, fe, extra in specs:
    for kind, xs in [('continua', ['pct_apos_corte']), ('faixas', ['g_Até 10%', 'g_10–30%', 'g_30%+'])]:
        X = xs + ctrl + extra
        b, se, p, G, _ = ols_fe(m.abstencao.to_numpy(float), m[X].to_numpy(float), w, fe, m.id_municipio.to_numpy())
        for j, x in enumerate(xs):
            res['regressao_' + kind].append({'modelo': nome, 'variavel': x.replace('g_', ''), 'coef': b[j], 'ep': se[j],
                                            'ic_inf': b[j] - 1.96 * se[j], 'ic_sup': b[j] + 1.96 * se[j], 'p': p[j]})

# 3. Limite para "votos de ausentes": quantos votos após 17h não passaram pela digital
e = pd.DataFrame([json.loads(x) for f in glob.glob(str(AQUI / 'dados/etapas/etapas_*.jsonl.gz')) for x in gzip.open(f, 'rt')])
e = e.merge(d[['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'grupo', 'aptos', 'comparecimento']],
            on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'])
lim = []
for k, x in e.groupby('grupo', observed=True):
    n = np.array(x.n.tolist())[:, 17:].sum()
    bio = np.array(x.bio.tolist())[:, 17:].sum()
    man = np.array(x.manual.tolist())[:, 17:].sum()
    lim.append({'grupo': k, 'votos_apos': float(n), 'pct_digital': float(100 * bio / n) if n else None,
                'sem_digital': float(n - bio), 'liberados_mesario': float(man),
                'sem_digital_pct_dos_aptos': float(100 * (n - bio) / x.aptos.sum())})
res['limite_ausentes'] = lim
(OUT / 'abstencao.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
print(pd.DataFrame(res['por_grupo']).round(2).to_string())
print(pd.DataFrame(res['regressao_continua']).round(4).to_string())
print(pd.DataFrame(res['regressao_faixas']).round(3).to_string())
print(pd.DataFrame(lim).round(2).to_string())
