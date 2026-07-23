import re
from dataclasses import dataclass

@dataclass
class Section:
    title: str
    content: str
    visual_type: str | None

# Only match explicit clause/article/chapter headers at line start.
# Deliberately excludes bare "3 - Something" to avoid mid-sentence matches.
_CLAUSE_RE = re.compile(
    r"(?m)^("
    # "CLÁUSULA PRIMEIRA - DO OBJETO" or "CLÁUSULA 1ª - DO OBJETO"
    r"CLÁUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SÉTIMA|OITAVA|NONA"
    r"|DÉCIMA(?:\s+\w+)?|UNDÉCIMA|DUODÉCIMA|\d+[ªº°]?)\s*[-–—]?\s*[^\n]{0,90}"
    r"|CLAUSULA\s+(?:PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|SETIMA|OITAVA|NONA"
    r"|DECIMA(?:\s+\w+)?|\d+[ªº°]?)\s*[-–—]?\s*[^\n]{0,90}"
    # "ARTIGO 1°" / "ART. 2 -"
    r"|(?:ARTIGO|ART\.?)\s+\d+[ªº°]?\s*[-–—.]?\s*[^\n]{0,80}"
    # "CAPÍTULO I / SEÇÃO 2"
    r"|(?:CAPÍTULO|CAPITULO|SEÇÃO|SECAO)\s+[IVXLCDM\d]+\s*[-–—]?\s*[^\n]{0,70}"
    r")",
    re.IGNORECASE,
)

_VISUAL_KEYWORDS: dict[str, list[str]] = {
    "parties": [
        "parte", "qualificaç", "contratante", "contratado", "fiador",
        "testemunha", "interveniente", "representad", "denomina",
        "pessoa jurídica", "pessoa física", "cnpj", "cpf",
    ],
    "timeline": [
        "prazo", "vigência", "vigencia", "data", "início", "inicio",
        "término", "termino", "duração", "duracao", "entrega",
        "vencimento", "calendário", "cronograma", "semanas", "dias corridos",
    ],
    "values": [
        "valor", "preço", "preco", "pagamento", "honorário", "honorario",
        "remuneraç", "mensalidade", "parcela", "r$", "reais", "pix",
        "contraprestação", "importância",
    ],
    "obligations": [
        "obrigaç", "dever", "responsabilidade", "incumbe", "compromete",
        "compete", "cabe ao", "deve ", "prestação", "deveres",
        "homologação", "deploy", "entrega",
    ],
    "penalties": [
        "penalidade", "multa", "rescisão", "rescisao", "sançã", "sancao",
        "infração", "inadimpl", "descumprimento", "mora", "indeniz",
        "rescind", "juros",
    ],
}


def split_sections(text: str) -> list[Section]:
    matches = list(_CLAUSE_RE.finditer(text))

    if not matches:
        return [Section(title="", content=text, visual_type=_classify("", text))]

    sections: list[Section] = []

    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append(Section(
            title="Identificação e Qualificação das Partes",
            content=preamble,
            visual_type="parties",
        ))

    for i, m in enumerate(matches):
        title   = m.group(0).strip()
        start   = m.end()
        end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        sections.append(Section(
            title=title,
            content=content,
            visual_type=_classify(title, content),
        ))

    return sections


def _classify(title: str, content: str) -> str | None:
    combined = (title + " " + content).lower()
    scores = {
        vtype: sum(1 for kw in kws if kw in combined)
        for vtype, kws in _VISUAL_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] >= 1 else None
