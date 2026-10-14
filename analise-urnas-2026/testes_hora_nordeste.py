"""Nordeste: a associação entre votar tarde e a margem Lula − Flávio é específica das 17h?

Usa a distribuição dos votos computados por hora (logs) de cada seção. Se votos irregulares
fossem adicionados após o encerramento, a associação deveria saltar a partir das 17h. Se for
composição do eleitorado (quem vota mais tarde tende a votar diferente), ela deve crescer de
forma gradual ao longo do dia, já antes das 17h.
Saída: resultados/nordeste/teste_hora.json
"""
import glob, gzip, json
from pathlib import Path
import numpy as np, pandas as pd
from analisar import PERFIL, ols_fe
from analisar_nordeste import carregar

AQUI = Path(__file__).parent
d = carregar()
t = pd.DataFrame([json.loads(x) for f in glob.glob(str(AQUI / 'dados/tempos/tempos_*.jsonl.gz')) for x in gzip.open(f, 'rt')])
d = d.merge(t[['uf', 'cd_municipio', 'nr_zona', 'nr_secao', 'votos_por_hora', 'dur_med_antes', 'gap_med_antes',
               'tentativas_por_eleitor_antes']], on=['uf', 'cd_municipio', 'nr_zona', 'nr_secao'])
d = d[d.log_conciliado & (d.validos >= 20) & d[PERFIL].notna().all(axis=1) & d.pct_falha_bio.notna()
      & (d.corte_local_h == 17)].copy()
vh = np.array(d.votos_por_hora.tolist(), float)
tot = vh.sum(axis=1)
d = d[tot > 0].copy(); vh = vh[tot > 0]; tot = tot[tot > 0]
BLOCOS = [('8h–10h', 8, 10), ('10h–12h', 10, 12), ('12h–14h', 12, 14), ('14h–15h', 14, 15), ('15h–16h', 15, 16),
          ('16h–17h', 16, 17), ('17h–18h', 17, 18), ('18h ou mais', 18, 24)]
for nome, a, b in BLOCOS:
    d['h_' + nome] = 100 * vh[:, a:b].sum(axis=1) / tot
ref = 'h_10h–12h'
hcols = ['h_' + n for n, _, _ in BLOCOS if 'h_' + n != ref]
ctrl = ['pct_comparecimento', 'log_aptos', 'urna_UE2013', 'urna_UE2015', 'urna_UE2020', 'pct_falha_bio', 'pct_sem_cadastro']
d['ritmo_manha'] = vh[:, 8:12].sum(axis=1) / 4                      # votos/hora 8h–12h
d['log_dur'] = np.log(d.dur_med_antes.clip(lower=10))
d['tent'] = d.tentativas_por_eleitor_antes
res = {'secoes': int(len(d)), 'referencia': '10h–12h'}

def roda(nome, xs, fe):
    b, se, p, G, _ = ols_fe(d.margem.to_numpy(float), d[xs].to_numpy(float), d.validos.to_numpy(float), fe,
                            d.id_municipio.to_numpy())
    return [{'bloco': x[2:], 'coef': b[j], 'ep': se[j], 'p': p[j]} for j, x in enumerate(xs) if x in hcols]

res['por_hora'] = {
    'Dentro do município': roda('m', hcols + ctrl, d.id_municipio.to_numpy()),
    'Dentro do colégio + perfil': roda('c', hcols + ctrl + PERFIL, d.id_local.to_numpy()),
    'Colégio + perfil + ritmo da urna': roda('r', hcols + ctrl + PERFIL + ['ritmo_manha', 'log_dur', 'tent'], d.id_local.to_numpy()),
}
# salto em 17h: compara 17h–18h com 16h–17h no modelo principal
r = {x['bloco']: x for x in res['por_hora']['Dentro do colégio + perfil']}
res['salto_17h'] = {'coef_16_17': r['16h–17h']['coef'], 'coef_17_18': r['17h–18h']['coef']}
# limite superior do impacto: se toda a associação for dos votos tardios
late = d.pres_apos_corte.sum()
b = r['17h–18h']['coef']
res['impacto_maximo_votos_margem'] = float(late * b)
(AQUI / 'resultados/nordeste/teste_hora.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
for k, v in res['por_hora'].items():
    print(k); print(pd.DataFrame(v).round(4).to_string(index=False))
print(res['salto_17h'], res['impacto_maximo_votos_margem'], res['secoes'])
