"""Leitura dos arquivos de urna do TSE (eleições 2026, 1º turno).

- BU (``*-bu.dat``): DER/ASN.1. O mapeamento de campos segue o decodificador
  publicado no aplicativo Resultados do TSE (chunk 369.*.js), já conferido no
  piloto contra o leitor oficial.
- Log (``*-log.jez``): ZIP contendo ``logd.dat`` (texto latin-1, separado por TAB).

Não verifica assinaturas digitais. Estruturas inesperadas levantam exceção para
que a seção seja registrada como ocorrência, e nunca preenchida por suposição.
"""
import io
import zipfile

CARGO_PRESIDENTE = 1
TIPO_NOMINAL, TIPO_BRANCO, TIPO_NULO = 1, 2, 3


class FormatoInesperado(ValueError):
    pass


def tlv(data, offset=0):
    tag = data[offset]
    offset += 1
    if tag & 31 == 31:
        raise FormatoInesperado('tag longa')
    length = data[offset]
    offset += 1
    if length & 128:
        size = length & 127
        if size == 0:
            raise FormatoInesperado('comprimento indefinido')
        length = int.from_bytes(data[offset:offset + size], 'big')
        offset += size
    end = offset + length
    if end > len(data):
        raise FormatoInesperado('DER truncado')
    return (tag, data[offset:end]), end


def children(value):
    out, i = [], 0
    while i < len(value):
        node, i = tlv(value, i)
        out.append(node)
    return out


def num(node):
    if node[0] not in (2, 10, 128, 129, 130):
        raise FormatoInesperado(f'tag numérica inesperada {node[0]}')
    return int.from_bytes(node[1], 'big', signed=True)


def nonneg(node):
    v = num(node)
    if v < 0:
        raise FormatoInesperado('inteiro negativo')
    return v


def text(node):
    return node[1].decode('ascii', errors='replace')


def decode_bu(data):
    root, end = tlv(data)
    if root[0] != 48 or end != len(data):
        raise FormatoInesperado('envelope')
    env = children(root[1])
    fase = num(env[1])
    octets = [n for n in env if n[0] == 4]
    if len(octets) != 1:
        raise FormatoInesperado('conteúdo do envelope')
    content, end = tlv(octets[0][1])
    inner = children(content[1])
    if len(inner) < 9 or inner[3][0] != 48:
        raise FormatoInesperado('entidade BU')

    ident = children(inner[3][1])
    mz = children(ident[0][1])
    d = {
        'fase': fase,
        'cd_municipio': nonneg(mz[0]),
        'nr_zona': nonneg(mz[1]),
        'nr_local': nonneg(ident[1]),
        'nr_secao': nonneg(ident[2]),
        'emissao_bu': text(inner[4]),
    }

    urna = children(inner[2][1])
    d['tipo_urna'] = num(urna[0])  # 1 = apurada (urna eletrônica)
    d['versao_urna'] = text(urna[1]) if urna[1][0] == 27 else None
    try:
        corresp = children(children(urna[2][1])[1][1])
        d['nr_urna'] = nonneg(corresp[0])
    except (FormatoInesperado, IndexError):
        d['nr_urna'] = None

    if inner[5][0] != 160:
        raise FormatoInesperado('dados de abertura/encerramento ausentes')
    datas = children(inner[5][1])
    d['abertura'] = text(datas[0])
    d['encerramento'] = text(datas[1])

    d['comparecimento'] = nonneg(inner[6])
    det = inner[7]
    if det[0] != 161:
        raise FormatoInesperado('detalhamento de comparecimento ausente')
    sem_bio, bio, biografia = map(nonneg, children(det[1]))
    if sem_bio + bio + biografia != d['comparecimento']:
        raise FormatoInesperado('detalhamento não soma o comparecimento')
    d['sem_biometria'] = sem_bio          # sem biometria cadastrada
    d['hab_biometria'] = bio              # habilitado pela digital
    d['hab_biografia'] = biografia        # tinha biometria, liberado por dados pessoais

    found = []
    for e in children(inner[8][1]):
        a = children(e[1])
        aptos = nonneg(a[1])
        for result in children(a[4][1]):
            rr = children(result[1])
            for cargo in children(rr[2][1]):
                cc = children(cargo[1])
                if num(cc[0]) != CARGO_PRESIDENTE:
                    continue
                votos, branco, nulo = {}, 0, 0
                for vote in children(cc[2][1]):
                    vv = children(vote[1])
                    kind, qty = num(vv[0]), nonneg(vv[1])
                    if kind == TIPO_NOMINAL:
                        cand = str(nonneg(children(vv[2][1])[1]))
                        if cand in votos:
                            raise FormatoInesperado('candidato duplicado')
                        votos[cand] = qty
                    elif kind == TIPO_BRANCO:
                        branco += qty
                    elif kind == TIPO_NULO:
                        nulo += qty
                    else:
                        raise FormatoInesperado(f'tipo de voto presidencial {kind}')
                found.append((num(a[0]), aptos, nonneg(rr[1]), votos, branco, nulo))
    if len(found) != 1:
        raise FormatoInesperado('cargo presidencial ausente ou duplicado')
    d['cd_eleicao'], d['aptos'], comp_pres, d['votos'], d['brancos'], d['nulos'] = found[0]
    d['validos'] = sum(d['votos'].values())
    if d['validos'] + d['brancos'] + d['nulos'] != d['comparecimento'] or comp_pres != d['comparecimento']:
        raise FormatoInesperado('votos presidenciais não conciliam comparecimento')
    return d


def _secs(hms):
    return int(hms[0:2]) * 3600 + int(hms[3:5]) * 60 + int(hms[6:8])


# Cortes locais candidatos (horas). O corte efetivo de cada seção é escolhido
# depois, a partir do horário de abertura observado no município (abertura + 9h).
CORTES = (15, 16, 17, 18, 19)


def parse_log(data, dia='04/10/2026'):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    if 'logd.dat' not in names:
        raise FormatoInesperado('logd.dat ausente')
    raw = z.read('logd.dat').decode('latin1')

    out = {
        'log_habilitados': 0, 'log_hab_biometrica': 0, 'log_computados': 0,
        'log_presidente': 0, 'log_mesario_habilitou': 0,
        'log_suspenso_sem_voto': 0, 'log_nulo_suspensao_pres': 0,
        'log_hab_biometrica_efetiva': 0,  # biométricas cujo eleitor não saiu sem votar
        'log_hab_com_tentativa': 0,      # habilitado após ao menos uma solicitação de digital
        'log_bio_mais_de_1_tentativa': 0,  # sucesso biométrico com 2+ tentativas
        'log_regressoes_horario': 0, 'log_eventos_excepcionais': 0,
        'log_urnas_no_dia': 0, 'log_outros_arquivos': len(names) - 1,
        'pronta': None, 'encerramento_log': None,
        'primeiro_voto_pres': None, 'ultimo_voto_pres': None,
        'modelo_urna': None,
    }
    for c in CORTES:
        out[f'pres_apos_{c}h'] = 0           # confirmações presidenciais após c:00:00 local
        out[f'hab_apos_{c}h'] = 0            # eleitores habilitados após o corte
        out[f'pres_apos_{c}h_hab_antes'] = 0  # habilitado antes, confirmou depois

    urnas = set()
    last = None
    cur = None
    for line in raw.splitlines():
        a = line.split('\t')
        if len(a) < 5:
            continue
        if a[3] == 'GAP' and a[4].startswith('Identificação do Modelo de Urna: '):
            out['modelo_urna'] = a[4].rsplit(' ', 1)[-1]
        if a[3] != 'VOTA' or not a[0].startswith(dia):
            continue
        t = a[0][11:19]
        s = _secs(t)
        m = a[4]
        urnas.add(a[2])
        if last is not None and s < last:
            out['log_regressoes_horario'] += 1
        last = s

        if m == 'Urna pronta para receber votos':
            if out['pronta'] is None:
                out['pronta'] = t
        elif m == 'Aguardando digitação do identificador do eleitor':
            cur = {'tent': 0}
        elif m.startswith('Solicita digital. Tentativa'):
            if cur is not None:
                cur['tent'] += 1
        elif m == 'Tipo de habilitação do eleitor [biométrica]':
            out['log_hab_biometrica'] += 1
            if cur is not None:
                cur['bio'] = True
            if cur is not None and cur['tent'] > 1:
                out['log_bio_mais_de_1_tentativa'] += 1
        elif m.startswith('Mesário ') and m.endswith('habilitou o eleitor'):
            out['log_mesario_habilitou'] += 1
        elif m == 'Eleitor foi habilitado':
            out['log_habilitados'] += 1
            if cur is None:
                cur = {'tent': 0}
            cur['hab'] = s
            if cur['tent']:
                out['log_hab_com_tentativa'] += 1
            for c in CORTES:
                if s >= c * 3600:
                    out[f'hab_apos_{c}h'] += 1
        elif m == 'Eleitor foi suspenso e não confirmou nenhum voto':
            out['log_suspenso_sem_voto'] += 1
            if cur is not None and cur.get('bio'):
                cur['bio_anulada'] = True
        elif m in ('Voto confirmado para [Presidente]', 'Atribuido voto nulo por suspensão [Presidente]'):
            if m[0] == 'V':
                out['log_presidente'] += 1
            else:
                out['log_nulo_suspensao_pres'] += 1
            if out['primeiro_voto_pres'] is None:
                out['primeiro_voto_pres'] = t
            out['ultimo_voto_pres'] = t
            hab = cur.get('hab') if cur else None
            for c in CORTES:
                if s >= c * 3600:
                    out[f'pres_apos_{c}h'] += 1
                    if hab is not None and hab < c * 3600:
                        out[f'pres_apos_{c}h_hab_antes'] += 1
        elif m == 'O voto do eleitor foi computado':
            out['log_computados'] += 1
            if cur is not None and cur.get('bio'):
                out['log_hab_biometrica_efetiva'] += 1
            cur = None
        elif m == 'Procedimento de encerramento confirmado':
            out['encerramento_log'] = t
        ml = m.lower()
        if 'suspens' in ml and 'eleitor voltou' not in ml or 'reinici' in ml or 'contingência' in ml:
            out['log_eventos_excepcionais'] += 1
    out['log_urnas_no_dia'] = len(urnas)
    return out
