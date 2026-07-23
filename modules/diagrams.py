"""
All diagrams use only matplotlib (no external graphviz binary).
Runs fully embedded in PyInstaller bundles without system dependencies.
"""

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 12,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
})

PALETTE = {
    "blue":   "#2E86AB",
    "green":  "#27AE60",
    "red":    "#E74C3C",
    "orange": "#F39C12",
    "purple": "#8E44AD",
    "teal":   "#1ABC9C",
    "gray":   "#7F8C8D",
    "dark":   "#2C3E50",
    "bg":     "#FAFAFA",
}

DATE_COLORS = {
    "inicio":     PALETTE["green"],
    "fim":        PALETTE["red"],
    "pagamento":  PALETTE["blue"],
    "entrega":    PALETTE["orange"],
    "vencimento": PALETTE["red"],
}

OBLIGATION_COLORS = [
    PALETTE["blue"], PALETTE["green"], PALETTE["red"],
    PALETTE["orange"], PALETTE["purple"], PALETTE["teal"],
]

DIAGRAM_MIN_ITEMS = {
    "parties":     ("partes",      2),
    "timeline":    ("datas",       1),
    "obligations": ("obrigacoes",  2),
    "values":      ("valores",     1),
    "penalties":   ("penalidades", 1),
}

DETAIL_LIMITS = {
    "resumido": 4,
    "completo": 8,
    "maximo":   999,
}


def generate_diagrams(
    data: dict[str, Any],
    session_id: str,
    temp_dir: Path,
    config: dict[str, dict] | None = None,
) -> dict[str, str]:
    out_dir = temp_dir / session_id / "diagrams"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_types = list(DIAGRAM_MIN_ITEMS.keys())
    resolved: dict[str, int] = {}

    if not config:
        for t in all_types:
            resolved[t] = DETAIL_LIMITS["completo"]
    else:
        for t in all_types:
            cfg = config.get(t, {})
            if cfg.get("enabled", False):
                detail = cfg.get("detail", "completo")
                resolved[t] = DETAIL_LIMITS.get(detail, DETAIL_LIMITS["completo"])

    generators = {
        "parties":     _parties,
        "timeline":    _timeline,
        "obligations": _obligations,
        "values":      _values,
        "penalties":   _penalties,
    }

    paths: dict[str, str] = {}
    for diag_type, max_items in resolved.items():
        data_key, min_count = DIAGRAM_MIN_ITEMS[diag_type]
        items = data.get(data_key, [])
        if len(items) < min_count:
            continue
        p = generators[diag_type](items[:max_items], out_dir)
        if p:
            paths[diag_type] = p

    return paths


# ── Parties — pure matplotlib network diagram ─────────────────────────────────

def _parties(partes: list, out_dir: Path) -> str | None:
    try:
        contratantes = [p for p in partes if "contratante" in (p.get("tipo") or "").lower()]
        contratados  = [p for p in partes if "contratado"  in (p.get("tipo") or "").lower()]
        others       = [p for p in partes if p not in contratantes and p not in contratados]

        n_left  = max(len(contratantes), 1)
        n_right = max(len(contratados), 1)

        fig_h = max(5.0, max(n_left, n_right) * 2.0 + (1.8 if others else 0) + 1.5)
        fig, ax = plt.subplots(figsize=(13, fig_h))
        fig.patch.set_facecolor("white")
        ax.set_facecolor(PALETTE["bg"])
        ax.axis("off")
        ax.set_title("Relacionamento entre as Partes", pad=16)

        NW, NH = 3.2, 0.85
        LEFT_X, RIGHT_X = 1.8, 7.8

        def centered_ys(n, fig_h):
            span = (n - 1) * 2.0
            top  = fig_h / 2 + span / 2 - 0.5
            return [top - i * 2.0 for i in range(n)]

        left_ys  = centered_ys(max(len(contratantes), 1), fig_h)
        right_ys = centered_ys(max(len(contratados),  1), fig_h)

        def draw_node(cx, cy, party, color):
            box = FancyBboxPatch(
                (cx - NW / 2, cy - NH / 2), NW, NH,
                boxstyle="round,pad=0.12",
                facecolor=color, edgecolor="white", linewidth=2, zorder=3,
            )
            ax.add_patch(box)
            nome  = _clip(party.get("nome", "?"), 28)
            tipo_ = _clip(party.get("tipo", ""),  22)
            ax.text(cx, cy + 0.18, nome,  ha="center", va="center",
                    fontsize=10.5, color="white", fontweight="bold", zorder=4)
            ax.text(cx, cy - 0.20, tipo_, ha="center", va="center",
                    fontsize=8.5, color="white", alpha=0.88, zorder=4)

        def draw_edge(x1, y1, x2, y2, label="", color=PALETTE["blue"]):
            ax.annotate(
                "", xy=(x2 - NW / 2, y2), xytext=(x1 + NW / 2, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=2.0,
                                connectionstyle="arc3,rad=0.0"), zorder=2,
            )
            if label:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                ax.text(mx, my + 0.18, label, ha="center", va="center",
                        fontsize=9, color=color,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white",
                                  ec=color, lw=1, alpha=0.95), zorder=5)

        c_coords = []
        for i, p in enumerate(contratantes):
            y = left_ys[i] if i < len(left_ys) else left_ys[0]
            draw_node(LEFT_X, y, p, PALETTE["blue"])
            c_coords.append((LEFT_X, y))

        cd_coords = []
        for i, p in enumerate(contratados):
            y = right_ys[i] if i < len(right_ys) else right_ys[0]
            draw_node(RIGHT_X, y, p, PALETTE["green"])
            cd_coords.append((RIGHT_X, y))

        for cp in c_coords:
            for cdp in cd_coords:
                draw_edge(cp[0], cp[1], cdp[0], cdp[1], "contrata", PALETTE["blue"])

        if others:
            bot_y = 0.6
            for i, p in enumerate(others):
                tipo_l = (p.get("tipo") or "").lower()
                color  = PALETTE["orange"] if "fiador" in tipo_l else PALETTE["gray"]
                bx     = 2.2 + i * 3.0
                draw_node(bx, bot_y, p, color)
                target = c_coords[0] if c_coords else (cd_coords[0] if cd_coords else None)
                if target:
                    ax.plot([bx, target[0]], [bot_y + NH / 2, target[1] - NH / 2],
                            color=color, lw=1.5, linestyle="--", zorder=2)

        handles = [
            mpatches.Patch(color=PALETTE["blue"],  label="Contratante"),
            mpatches.Patch(color=PALETTE["green"], label="Contratado"),
        ]
        if others:
            handles.append(mpatches.Patch(color=PALETTE["orange"], label="Fiador / Testemunha"))
        ax.legend(handles=handles, loc="upper right", fontsize=10,
                  framealpha=0.95, edgecolor="#DDD")

        all_ys = [y for _, y in c_coords + cd_coords]
        if others:
            all_ys.append(0.6)
        ax.set_xlim(0, 10)
        ax.set_ylim(min(all_ys) - 1.2, max(all_ys) + 1.5)

        plt.tight_layout()
        out = str(out_dir / "parties.png")
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return out

    except Exception as e:
        print(f"[diagrams] parties: {e}")
        return None


# ── Timeline ─────────────────────────────────────────────────────────────────

def _timeline(datas: list, out_dir: Path) -> str | None:
    try:
        n     = len(datas)
        row_h = 1.2
        fig, ax = plt.subplots(figsize=(14, max(4, n * row_h + 1.5)))
        fig.patch.set_facecolor("white")
        ax.set_facecolor(PALETTE["bg"])

        spine_x = 0.38
        ax.axvline(x=spine_x, color="#CCCCCC", linewidth=2.5, zorder=1)

        for i, ev in enumerate(datas):
            y     = (n - 1 - i) * row_h
            tipo  = (ev.get("tipo") or "").lower()
            color = DATE_COLORS.get(tipo, PALETTE["dark"])

            ax.axhline(y=y, color="#EEEEEE", linewidth=1, zorder=0, xmin=0.01, xmax=0.99)

            date_str = (ev.get("data") or "").strip()
            if date_str and date_str != "null":
                ax.text(spine_x - 0.02, y, date_str, ha="right", va="center",
                        fontsize=11, color="#444", fontweight="bold", family="monospace")

            ax.scatter([spine_x], [y], s=320, color=color, zorder=5,
                       edgecolors="white", linewidths=2.5)

            if tipo:
                bbox_props = dict(boxstyle="round,pad=0.3", fc=color + "22", ec=color, lw=1)
                ax.text(spine_x + 0.03, y + row_h * 0.32, tipo.upper(),
                        ha="left", va="center", fontsize=9, color=color,
                        fontweight="bold", bbox=bbox_props)

            desc = _clip(ev.get("descricao", ""), 72)
            ax.text(spine_x + 0.03, y - row_h * 0.08, desc,
                    ha="left", va="center", fontsize=12, color=PALETTE["dark"])

        legend_handles = [
            mpatches.Patch(color=c, label=t.capitalize())
            for t, c in DATE_COLORS.items()
        ]
        ax.legend(handles=legend_handles, loc="lower right", fontsize=10,
                  framealpha=0.95, edgecolor="#DDD")

        ax.set_xlim(0, 5)
        ax.set_ylim(-row_h * 0.8, (n - 0.2) * row_h)
        ax.axis("off")
        ax.set_title("Linha do Tempo do Contrato", pad=16)

        plt.tight_layout()
        out = str(out_dir / "timeline.png")
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return out

    except Exception as e:
        print(f"[diagrams] timeline: {e}")
        return None


# ── Obligations — pure matplotlib flow ───────────────────────────────────────

def _obligations(obrigacoes: list, out_dir: Path) -> str | None:
    try:
        groups: dict[str, list] = {}
        for ob in obrigacoes:
            parte = (ob.get("parte") or "Não especificado").strip()
            groups.setdefault(parte, []).append(ob)

        total_items = sum(len(v) for v in groups.values())
        n_groups    = len(groups)
        row_h       = 1.1
        gap         = 0.6
        fig_h       = max(5.0, total_items * row_h + n_groups * (0.9 + gap) + 1.5)

        fig, ax = plt.subplots(figsize=(13, fig_h))
        fig.patch.set_facecolor("white")
        ax.set_facecolor(PALETTE["bg"])
        ax.axis("off")
        ax.set_title("Fluxo de Obrigações por Parte", pad=16)

        y     = fig_h - 1.4
        box_x = 1.2
        box_w = 10.5

        for gi, (parte, obs) in enumerate(groups.items()):
            color = OBLIGATION_COLORS[gi % len(OBLIGATION_COLORS)]

            hdr = FancyBboxPatch(
                (box_x, y - 0.38), box_w, 0.76,
                boxstyle="round,pad=0.1",
                facecolor=color, edgecolor="none", zorder=2,
            )
            ax.add_patch(hdr)
            ax.text(box_x + box_w / 2, y, _clip(parte, 55),
                    ha="center", va="center",
                    fontsize=11, color="white", fontweight="bold", zorder=3)
            y -= 1.05

            for oi, ob in enumerate(obs):
                desc  = _clip(ob.get("descricao", ""), 70)
                prazo = ob.get("prazo") or ""
                if prazo and prazo != "null":
                    desc += f"  ⏱ {prazo}"

                item_box = FancyBboxPatch(
                    (box_x + 0.3, y - 0.34), box_w - 0.6, 0.68,
                    boxstyle="round,pad=0.08",
                    facecolor=color + "1E", edgecolor=color + "66", linewidth=1, zorder=2,
                )
                ax.add_patch(item_box)

                dot = plt.Circle((box_x + 0.68, y), 0.14, color=color, zorder=4)
                ax.add_patch(dot)

                ax.text(box_x + 1.0, y, desc,
                        va="center", fontsize=11, color=PALETTE["dark"], zorder=3)

                if oi < len(obs) - 1:
                    ax.annotate(
                        "", xy=(box_x + box_w / 2, y - 0.34),
                        xytext=(box_x + box_w / 2, y - 0.72),
                        arrowprops=dict(arrowstyle="->", color=color + "AA", lw=1.5),
                    )

                y -= row_h

            y -= gap

        ax.set_xlim(0, 12.5)
        ax.set_ylim(y - 0.3, fig_h - 0.3)
        plt.tight_layout()
        out = str(out_dir / "obligations.png")
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return out

    except Exception as e:
        print(f"[diagrams] obligations: {e}")
        return None


# ── Financial values ──────────────────────────────────────────────────────────

def _values(valores: list, out_dir: Path) -> str | None:
    try:
        import re as _re

        parsed = []
        for v in valores:
            raw  = v.get("valor", "")
            nums = _re.findall(r"[\d]+(?:[.,]\d+)*", raw.replace(".", "").replace(",", "."))
            num  = float(nums[0]) if nums else None
            parsed.append({
                "label":  _clip(v.get("descricao", "Valor"), 36),
                "raw":    raw,
                "value":  num,
                "period": v.get("periodicidade", "") or "",
            })

        n     = len(parsed)
        row_h = 1.3
        fig, ax = plt.subplots(figsize=(14, max(4, n * row_h + 1.8)))
        fig.patch.set_facecolor("white")
        ax.set_facecolor(PALETTE["bg"])

        color_cycle = [PALETTE["blue"], PALETTE["teal"], PALETTE["purple"],
                       PALETTE["orange"], PALETTE["green"]]

        has_numeric = any(p["value"] for p in parsed)
        max_val     = max((p["value"] for p in parsed if p["value"]), default=1)

        for i, p in enumerate(parsed):
            y     = (n - 1 - i) * row_h
            color = color_cycle[i % len(color_cycle)]

            row_patch = FancyBboxPatch(
                (0, y - 0.45), 13.5, row_h - 0.15,
                boxstyle="round,pad=0.1", facecolor=color + "12", edgecolor="none",
            )
            ax.add_patch(row_patch)

            if has_numeric and p["value"]:
                bar_w = (p["value"] / max_val) * 7.0
                bar = FancyBboxPatch(
                    (3.8, y - 0.3), bar_w, row_h * 0.55,
                    boxstyle="round,pad=0.05", facecolor=color, edgecolor="none", alpha=0.85,
                )
                ax.add_patch(bar)
                ax.text(3.8 + bar_w + 0.1, y + 0.05, p["raw"],
                        va="center", fontsize=12, color=color, fontweight="bold")
            else:
                vp = FancyBboxPatch(
                    (3.8, y - 0.25), 9.5, row_h * 0.5,
                    boxstyle="round,pad=0.1", facecolor=color + "25", edgecolor=color, lw=1,
                )
                ax.add_patch(vp)
                ax.text(8.5, y + 0.06, p["raw"], ha="center", va="center",
                        fontsize=12, color=color, fontweight="bold")

            period = f"  ({p['period']})" if p["period"] and p["period"] != "null" else ""
            ax.text(0.15, y + 0.06, p["label"] + period,
                    va="center", fontsize=12, color=PALETTE["dark"])
            ax.axhline(y - 0.45, color="#E8E8E8", linewidth=0.8, zorder=0)

        ax.set_xlim(0, 14)
        ax.set_ylim(-0.6, n * row_h)
        ax.axis("off")
        ax.set_title("Valores Financeiros do Contrato", pad=16)

        plt.tight_layout()
        out = str(out_dir / "values.png")
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return out

    except Exception as e:
        print(f"[diagrams] values: {e}")
        return None


# ── Penalties map ─────────────────────────────────────────────────────────────

def _penalties(penalidades: list, out_dir: Path) -> str | None:
    try:
        n     = len(penalidades)
        row_h = 1.6
        fig, ax = plt.subplots(figsize=(14, max(4.5, n * row_h + 1.8)))
        fig.patch.set_facecolor("white")
        ax.set_facecolor(PALETTE["bg"])

        HIGH_WORDS = ["rescisão","rescisao","multa","judicial","indeniz"]
        MED_WORDS  = ["suspens","bloqueio","juros","mora"]

        for i, pen in enumerate(penalidades):
            y        = (n - 1 - i) * row_h
            combined = (pen.get("penalidade","") + " " + pen.get("condicao","")).lower()

            if any(w in combined for w in HIGH_WORDS):
                sev_label, color = "ALTO",  PALETTE["red"]
            elif any(w in combined for w in MED_WORDS):
                sev_label, color = "MÉDIO", PALETTE["orange"]
            else:
                sev_label, color = "BAIXO", PALETTE["blue"]

            card = FancyBboxPatch(
                (0.1, y - 0.55), 13.3, row_h - 0.1,
                boxstyle="round,pad=0.15",
                facecolor=color + "12", edgecolor=color + "55", linewidth=1.2,
            )
            ax.add_patch(card)

            badge = FancyBboxPatch(
                (0.2, y - 0.28), 1.6, 0.56,
                boxstyle="round,pad=0.08", facecolor=color, edgecolor="none",
            )
            ax.add_patch(badge)
            ax.text(1.0, y + 0.03, sev_label, ha="center", va="center",
                    fontsize=11, color="white", fontweight="bold")

            ax.text(2.1, y + 0.25, "SE:", ha="left", va="center",
                    fontsize=9, color=color + "CC", fontweight="bold")
            ax.text(2.1, y - 0.05, _clip(pen.get("condicao",""), 42),
                    ha="left", va="center", fontsize=12, color=PALETTE["dark"])

            ax.text(7.1, y + 0.03, "➜", ha="center", va="center",
                    fontsize=18, color=color)

            ax.text(7.5, y + 0.25, "ENTÃO:", ha="left", va="center",
                    fontsize=9, color=color + "CC", fontweight="bold")
            ax.text(7.5, y - 0.05, _clip(pen.get("penalidade",""), 42),
                    ha="left", va="center", fontsize=12, color=color, fontweight="bold")

            if i < n - 1:
                ax.axhline(y - 0.55, color="#E0E0E0", linewidth=0.8, zorder=0)

        legend_handles = [
            mpatches.Patch(color=PALETTE["red"],    label="Severidade Alta"),
            mpatches.Patch(color=PALETTE["orange"], label="Severidade Média"),
            mpatches.Patch(color=PALETTE["blue"],   label="Severidade Baixa"),
        ]
        ax.legend(handles=legend_handles, loc="upper right", fontsize=10,
                  framealpha=0.95, edgecolor="#DDD")

        ax.set_xlim(0, 13.8)
        ax.set_ylim(-0.7, n * row_h)
        ax.axis("off")
        ax.set_title("Mapa de Penalidades e Sanções", pad=16)

        plt.tight_layout()
        out = str(out_dir / "penalties.png")
        plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return out

    except Exception as e:
        print(f"[diagrams] penalties: {e}")
        return None


def _clip(text: str, n: int) -> str:
    s = str(text).strip()
    return s[:n] + "…" if len(s) > n else s
