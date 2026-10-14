# Boletins de urna 2026 — biometria, horário e voto presidencial

Análise seção a seção do **1º turno de 2026 (Presidente)** a partir dos arquivos oficiais de urna do TSE
(boletim de urna + log de cada seção). Separa **ausência de cadastro biométrico** de **falha de reconhecimento**,
conta os **votos presidenciais confirmados após as 17h de Brasília** e testa se esses indicadores se associam ao
voto em nível nacional, estadual, municipal e por local de votação (colégio).

**Painel interativo:** https://claude.ai/artifact/T5F6oy1J5oHXMnyduSferr (também em `painel.html`).

> A unidade é a seção. O voto é secreto e o log não registra o candidato: nada aqui revela em quem votaram os
> eleitores sem biometria ou os que votaram depois das 17h. Associações entre seções não provam causa nem irregularidade.

## Cobertura e conferência

- **499.176** seções decodificadas de 499.248 seções principais do cadastro (o pacote do TSE traz só seções totalizadas). Zero falhas de leitura.
- Lidos 59 GB (só BU e log) dos 90 GB publicados, via HTTP Range, com tamanho e CRC32 de cada arquivo conferidos.
- Votos presidenciais: 100% das seções de RR batem campo a campo com o CSV oficial do BU; o total nacional bate com o arquivo oficial por município/zona a menos de 0,003% (diferença = seções ausentes do pacote + votos no nº 28, PRTB, que o oficial não conta como nominais).
- Log × BU: 496.901 seções (99,5%) conciliam exatamente (habilitações, votos presidenciais e biometria, considerando suspensões de eleitor). Só essas entram na medida de horário.
- Validação do “sem cadastro”: correlação de 0,90 entre a taxa de votantes sem biometria (BU) e a de aptos sem biometria no cadastro (perfil do eleitorado por seção).

## Resultados principais

| Indicador (Brasil) | Valor |
|---|---|
| Votantes sem biometria cadastrada | 6.940.334 (5,56% dos votantes) |
| Tinham biometria, liberados por dados pessoais (falha) | 8.342.249 (7,07% dos que tinham biometria) |
| Votos presidenciais confirmados após 17h de Brasília | 3.679.619 (2,95%) em 222.064 seções |
| … desses, de eleitores habilitados antes das 17h | 122.351 |

- **Sem cadastro** é muito desigual entre estados (ES 20,9%, MG 11,2%, PR 0,7%). A **falha** é mais homogênea (4–9%).
- **Votos após 17h** quase sempre vêm de quem foi habilitado depois das 17h (fila no encerramento) e se concentram no Nordeste e no Amazonas (AL 9,2%, SP 0,41%).

### Associação com a margem Lula − Flávio Bolsonaro

Coeficiente = p.p. de margem (votos válidos) por +1 p.p. no indicador; três indicadores no mesmo modelo; IC 95% com erro agrupado por município; 495.230 seções.

| Indicador | Brasil, sem ajuste | Mesmo colégio + perfil do eleitorado | Efeito do 10º ao 90º percentil (modelo ajustado) |
|---|---|---|---|
| Sem cadastro biométrico | 0,134 [-0,000; 0,269] | -0,160 [-0,189; -0,132] | -2,02 p.p. |
| Falha de reconhecimento | -0,209 [-0,379; -0,038] | -0,028 [-0,037; -0,019] | -0,26 p.p. |
| Votos após 17h | 2,525 [2,263; 2,788] | 0,078 [0,064; 0,091] | 0,77 p.p. |

Leitura: a associação bruta dos votos após 17h com o voto em Lula é quase toda geográfica (some ~97% quando se compara seções do mesmo colégio com o mesmo perfil). A ausência de cadastro troca de sinal com o ajuste. Os efeitos ajustados são estatisticamente detectáveis com meio milhão de seções, mas pequenos: no máximo ~2 p.p. de margem entre seções nos extremos da distribuição, compatíveis com diferenças de composição do eleitorado que os controles não capturam.

### Testes locais (com correção de Benjamini–Hochberg)

| Nível | Indicador | Testados | p < 0,05 | Esperado ao acaso | q < 0,05 |
|---|---|---|---|---|---|
| Município (modelo com colégio + perfil) | Sem cadastro | 2.329 | 369 | 116 | 88 |
| Município (modelo com colégio + perfil) | Falha | 2.329 | 218 | 116 | 20 |
| Município (modelo com colégio + perfil) | Após 17h | 2.328 | 346 | 116 | 74 |
| Colégio (correlação simples) | Sem cadastro | 35.440 | 3.038 | 1.772 | 9 |
| Colégio (correlação simples) | Falha | 35.478 | 2.304 | 1.774 | 0 |
| Colégio (correlação simples) | Após 17h | 31.106 | 1.936 | 1.555 | 1 |

Por colégio, praticamente nenhum teste sobrevive à correção para múltiplas comparações; por município, uma minoria (≈1–4%) sobrevive, a maioria na mesma direção do efeito nacional.

## Como reproduzir

```bash
pip install requests pandas numpy scipy
python testes.py                                  # decodificador contra 3 seções reais (RR)
python coletar.py --ufs TODAS --saida dados/secoes # ~60 GB lidos via HTTP Range, ~1h
python preparar_locais.py eleitorado_local_votacao_2026.zip dados/locais.csv.gz
python preparar_perfil.py --saida dados/perfil_secao.csv.gz
python analisar.py --secoes dados/secoes
python gerar_painel.py
```

## Arquivos

| Caminho | Conteúdo |
|---|---|
| `urnas/decod.py` | Decodificador do BU (ASN.1/DER) e parser do log |
| `coletar.py` | Coleta por UF via HTTP Range, conferência de CRC, decodificação paralela |
| `analisar.py` | Indicadores, agregados, regressões com efeitos fixos, testes locais |
| `dados/secoes_2026_1t.csv.gz` | Base por seção (BU + log + local + perfil) |
| `resultados/agregado_{brasil,uf,municipio,local}.*` | Somas e taxas por nível (numeradores/denominadores somados) |
| `resultados/regressoes_brasil.csv`, `regressoes_uf.csv` | Coeficientes, EP, IC e p de todos os modelos |
| `resultados/testes_municipio.csv.gz`, `testes_local.csv.gz` | Testes por município e por colégio com q-valores |
| `amostras/`, `testes.py` | BUs e logs reais do piloto (Alto Alegre–RR) e testes |

## Método e limites

- **Classificação biométrica** pelo próprio BU de 2026 (`detalhamentoComparecimento`, mapeamento do aplicativo Resultados do TSE): sem biometria cadastrada / habilitado pela digital / habilitado por dados pessoais apesar de ter biometria. Cada taxa tem seu denominador.
- **Horário**: urnas registram hora local; a votação vai das 8h às 17h de Brasília (8h–17h locais no exterior). Corte local = abertura típica do município no log + 9h (8h em 5.315 municípios, 7h em 336, 6h em 33, 9h em 4).
- **Modelo**: MQO ponderado por votos válidos; controles de comparecimento, log do eleitorado, modelo da urna; no modelo principal, efeito fixo de colégio e sexo, faixa etária e escolaridade do eleitorado da seção.
- **Limites**: falácia ecológica; ausência de cadastro é característica do eleitorado definida antes da eleição; falha de reconhecimento depende de idade, ocupação e condição das digitais; assinaturas digitais dos arquivos não foram verificadas; exterior não tem biometria e fica fora dos modelos.

Fontes: dadosabertos.tse.jus.br — `resultados-2026-arquivos-transmitidos-para-totalizacao`, `resultados-2026-boletim-de-urna`, `resultados-2026` (votação por município/zona), `eleitorado-2026` (locais de votação e perfil por seção).
