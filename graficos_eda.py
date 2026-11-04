"""
Gráficos finais da análise exploratória (EDA) - Censo Escolar 2025 e IDEB 2025.

Cada função recebe as tabelas de estatisticas_eda.py (nenhum cálculo novo é
feito aqui) e salva um PNG. Não abre janelas: usa o backend "Agg".

Cores (validadas para daltonismo): a mesma cor identifica a mesma rede nos
três gráficos. Como o verde-água tem contraste menor, todos os valores têm
rótulo numérico visível.
"""

import matplotlib

matplotlib.use("Agg")  # gera arquivos sem abrir janelas

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

CORES_REDE = {"Federal": "#1baf7a", "Estadual": "#2a78d6", "Municipal": "#eb6834"}
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRADE = "#e4e3df"
FONTE = "Fonte: Inep – Censo Escolar 2025 e IDEB/Saeb 2025. Elaboração própria."
NOMES_ETAPAS = {
    "AI": "Anos iniciais\ndo Fundamental",
    "AF": "Anos finais\ndo Fundamental",
    "EM": "Ensino Médio",
}
NOMES_ESCOLAS = {"35010281": "EMEF César Yasigi", "35044386": "EE Jornalista David Nasser"}
DPI = 200

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": GRADE,
    "axes.labelcolor": TEXTO_SECUNDARIO,
    "axes.titlecolor": TEXTO,
    "xtick.color": TEXTO_SECUNDARIO,
    "ytick.color": TEXTO_SECUNDARIO,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "hatch.color": "white",
    "hatch.linewidth": 1.2,
})


def formatar(valor, casas=0):
    """Número no padrão brasileiro: 1.284.021 e 751,33."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def preparar_eixo(ax):
    """Grade horizontal discreta atrás das barras."""
    ax.yaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)


def rodape(fig, notas):
    """Notas metodológicas e fonte no pé da figura."""
    fig.text(0.01, 0.01, "\n".join(notas + [FONTE]), ha="left", va="bottom",
             fontsize=8, color=TEXTO_SECUNDARIO, linespacing=1.5)


# ---------------------------------------------------------------------------
# Gráfico 1 - P1: matrículas por rede (escola como unidade)
# ---------------------------------------------------------------------------

def grafico_matriculas_por_rede(matriculas_por_rede, limites_tukey, outliers, caminho):
    redes = matriculas_por_rede[matriculas_por_rede["rede_administrativa"] != "Total"]
    total = matriculas_por_rede[matriculas_por_rede["rede_administrativa"] == "Total"].iloc[0]
    cores = [CORES_REDE[r] for r in redes["rede_administrativa"]]
    rotulos = [f"{r}\n({formatar(n)} escolas)"
               for r, n in zip(redes["rede_administrativa"], redes["escolas"])]
    x = np.arange(len(redes))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.9),
                                   gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.28})
    fig.subplots_adjust(top=0.80, bottom=0.24, left=0.07, right=0.98)

    # Painel A: totais
    barras = ax1.bar(x, redes["total_matriculas"], color=cores, width=0.6,
                     edgecolor="white", linewidth=2)
    for barra, valor in zip(barras, redes["total_matriculas"]):
        ax1.annotate(formatar(valor), (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                     xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                     fontsize=10, color=TEXTO)
    ax1.set_title("A. TOTAL de matrículas por rede", loc="left", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Total de matrículas (Fundamental + Médio)")
    ax1.set_xticks(x, rotulos)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: formatar(v)))
    ax1.set_ylim(0, redes["total_matriculas"].max() * 1.15)
    preparar_eixo(ax1)

    # Painel B: média e mediana por escola (mesma unidade, mesmo eixo)
    largura = 0.36
    b_media = ax2.bar(x - largura / 2, redes["media"], largura, color=cores,
                      edgecolor="white", linewidth=2)
    b_mediana = ax2.bar(x + largura / 2, redes["mediana"], largura, color=cores, alpha=0.45,
                        hatch="///", edgecolor="white", linewidth=2)
    for barras_grupo in (b_media, b_mediana):
        for barra in barras_grupo:
            ax2.annotate(formatar(barra.get_height(), 1),
                         (barra.get_x() + barra.get_width() / 2, barra.get_height()),
                         xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                         fontsize=9, color=TEXTO)
    ax2.axhline(total["media"], color=TEXTO_SECUNDARIO, linestyle="--", linewidth=1)
    # Rótulo da linha à esquerda, sobre a rede federal (barras baixas, sem colisão).
    ax2.annotate(f"média geral: {formatar(total['media'], 2)}",
                 (x[0] - 0.55, total["media"]), xytext=(0, 4), textcoords="offset points",
                 ha="left", va="bottom", fontsize=8.5, color=TEXTO_SECUNDARIO)
    ax2.set_title("B. Matrículas POR ESCOLA: média e mediana", loc="left",
                  fontsize=11, fontweight="bold")
    ax2.set_ylabel("Matrículas por escola")
    ax2.set_xticks(x, rotulos)
    ax2.set_xlim(-0.6, len(redes) - 0.4)
    ax2.set_ylim(0, max(redes["media"].max(), redes["mediana"].max()) * 1.2)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: formatar(v)))
    preparar_eixo(ax2)
    ax2.legend(handles=[Patch(facecolor="#8f8e89", label="Média"),
                        Patch(facecolor="#8f8e89", alpha=0.45, hatch="///", label="Mediana")],
               loc="upper left", frameon=False, fontsize=9, ncol=2)

    fig.suptitle("Matrículas nas escolas públicas de São Paulo — 2025",
                 x=0.01, y=0.975, ha="left", fontsize=15, fontweight="bold", color=TEXTO)
    fig.text(0.01, 0.885,
             f"{formatar(total['escolas'])} escolas públicas em atividade com Ensino Fundamental "
             f"ou Médio; {formatar(total['total_matriculas'])} matrículas. "
             "Unidade de análise: a escola (etapas somadas).",
             fontsize=10, color=TEXTO_SECUNDARIO)
    inferior, superior = limites_tukey
    acima = int((outliers["tipo"] == "acima do limite superior").sum())
    rodape(fig, [
        f"Dispersão geral: Q1 = {formatar(total['q1'])}, mediana = {formatar(total['mediana'])}, "
        f"Q3 = {formatar(total['q3'])}, IQR = {formatar(total['iqr'])}, "
        f"desvio-padrão = {formatar(total['desvio_padrao'], 1)} matrículas por escola.",
        f"Outliers (Tukey, 1,5 × IQR): {acima} escolas acima de {formatar(superior)} matrículas e "
        "nenhuma abaixo do limite inferior; mantidas por serem registros válidos do Censo.",
        f"A rede federal tem apenas {formatar(redes.iloc[0]['escolas'])} escolas. "
        "Matrículas indicam porte, não desempenho.",
    ])
    fig.savefig(caminho, dpi=DPI)
    plt.close(fig)
    return caminho


# ---------------------------------------------------------------------------
# Gráfico 2 - P2: média do IDEB por rede e etapa
# ---------------------------------------------------------------------------

def grafico_ideb_rede_etapa(ideb_rede_etapa, caminho):
    etapas = list(NOMES_ETAPAS)
    redes = list(CORES_REDE)
    x = np.arange(len(etapas))
    largura = 0.26

    fig, ax = plt.subplots(figsize=(12, 6.4))
    fig.subplots_adjust(top=0.78, bottom=0.25, left=0.07, right=0.98)

    for i, rede in enumerate(redes):
        dados = (ideb_rede_etapa[ideb_rede_etapa["rede_administrativa"] == rede]
                 .set_index("co_etapa_ensino").reindex(etapas))
        posicoes = x + (i - 1) * largura
        ax.bar(posicoes, dados["media"], largura, color=CORES_REDE[rede], label=rede,
               edgecolor="white", linewidth=2)
        # Intervalo interquartil (Q1-Q3) das notas divulgadas
        com_dispersao = dados["ideb_divulgados"] > 1
        ax.vlines(posicoes[com_dispersao.values], dados.loc[com_dispersao, "q1"],
                  dados.loc[com_dispersao, "q3"], color=TEXTO, linewidth=1.3)
        for pos, (_, linha) in zip(posicoes, dados.iterrows()):
            topo = max(linha["media"], linha["q3"])
            ax.annotate(formatar(linha["media_2casas"], 2), (pos, topo), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=10, fontweight="bold", color=TEXTO)
            ax.annotate(f"n = {formatar(linha['ideb_divulgados'])}", (pos, topo), xytext=(0, 18),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=8.5, color=TEXTO_SECUNDARIO)

    ax.set_xticks(x, [NOMES_ETAPAS[e] for e in etapas], fontsize=10.5)
    ax.set_ylabel("Média do IDEB 2025 (escala de 0 a 10)")
    ax.set_ylim(0, 10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: formatar(v)))
    preparar_eixo(ax)
    alcas = [Patch(facecolor=CORES_REDE[r], label=r) for r in redes]
    alcas.append(plt.Line2D([], [], color=TEXTO, linewidth=1.3,
                            label="Intervalo interquartil (Q1–Q3) das notas"))
    ax.legend(handles=alcas, loc="upper right", frameon=False, ncol=4, fontsize=9.5,
              bbox_to_anchor=(1, 1.06))

    fig.suptitle("Média do IDEB 2025 por rede e etapa de ensino — São Paulo",
                 x=0.01, y=0.975, ha="left", fontsize=15, fontweight="bold", color=TEXTO)
    fig.text(0.01, 0.885,
             "Escolas públicas em atividade. Média calculada somente com os IDEBs divulgados; "
             "n = quantidade de notas usadas em cada barra.",
             fontsize=10, color=TEXTO_SECUNDARIO)
    federal = ideb_rede_etapa[ideb_rede_etapa["rede_administrativa"] == "Federal"]
    municipal_em = ideb_rede_etapa[(ideb_rede_etapa["rede_administrativa"] == "Municipal")
                                   & (ideb_rede_etapa["co_etapa_ensino"] == "EM")].iloc[0]
    ausentes = int(ideb_rede_etapa["ideb_ausentes"].sum())
    rodape(fig, [
        f"Atenção: a rede federal tem {int(federal['ideb_divulgados'].max())} nota divulgada por "
        f"etapa, e a rede municipal tem só {int(municipal_em['ideb_divulgados'])} notas no "
        "Ensino Médio; esses valores não representam a rede.",
        f"{formatar(ausentes)} ofertas sem IDEB divulgado foram excluídas do cálculo (não "
        "tratadas como zero). São médias dos IDEBs publicados, não um IDEB oficial do município.",
    ])
    fig.savefig(caminho, dpi=DPI)
    plt.close(fig)
    return caminho


# ---------------------------------------------------------------------------
# Gráfico 3 - P3: Jardim Macedônia x média da mesma rede e etapa
# ---------------------------------------------------------------------------

def grafico_jardim_macedonia(macedonia, caminho):
    x = np.arange(len(macedonia))
    largura = 0.36

    fig, ax = plt.subplots(figsize=(12, 6.4))
    fig.subplots_adjust(top=0.78, bottom=0.27, left=0.07, right=0.98)

    for pos, (_, linha) in zip(x, macedonia.iterrows()):
        cor = CORES_REDE[linha["rede_administrativa"]]
        media = ax.bar(pos + largura / 2, linha["media_rede_etapa"], largura, color=cor,
                       alpha=0.45, hatch="///", edgecolor="white", linewidth=2)[0]
        ax.annotate(formatar(linha["media_rede_etapa"], 2),
                    (media.get_x() + largura / 2, media.get_height()), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", fontsize=10, color=TEXTO)
        if np.isnan(linha["ideb_escola"]):
            # Ausência NÃO é desenhada como barra de altura zero.
            ax.annotate("IDEB 2025\nnão divulgado\npelo Inep", (pos - largura / 2, 0.25),
                        ha="center", va="bottom", fontsize=9, style="italic",
                        color=TEXTO_SECUNDARIO)
            continue
        escola = ax.bar(pos - largura / 2, linha["ideb_escola"], largura, color=cor,
                        edgecolor="white", linewidth=2)[0]
        ax.annotate(formatar(linha["ideb_escola"], 1),
                    (escola.get_x() + largura / 2, escola.get_height()), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", fontsize=10,
                    fontweight="bold", color=TEXTO)
        topo = max(linha["ideb_escola"], linha["media_rede_etapa"])
        sinal = "+" if linha["diferenca"] > 0 else "−"
        ax.annotate(f"diferença: {sinal}{formatar(abs(linha['diferenca']), 2)}",
                    (pos, topo), xytext=(0, 22), textcoords="offset points", ha="center",
                    va="bottom", fontsize=9, color=TEXTO_SECUNDARIO)

    rotulos = [f"{NOMES_ESCOLAS.get(l['co_entidade'], l['no_entidade'])}\n"
               f"{NOMES_ETAPAS[l['co_etapa_ensino']].replace(chr(10), ' ')}\n"
               f"rede {l['rede_administrativa'].lower()}"
               for _, l in macedonia.iterrows()]
    ax.set_xticks(x, rotulos, fontsize=9.5)
    ax.set_ylabel("IDEB 2025 (escala de 0 a 10)")
    ax.set_ylim(0, 8.5)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: formatar(v)))
    preparar_eixo(ax)
    ax.legend(handles=[
        Patch(facecolor="#8f8e89", label="IDEB da escola"),
        Patch(facecolor="#8f8e89", alpha=0.45, hatch="///",
              label="Média das escolas da mesma rede e etapa em São Paulo"),
        Patch(facecolor=CORES_REDE["Municipal"], label="Rede municipal"),
        Patch(facecolor=CORES_REDE["Estadual"], label="Rede estadual"),
    ], loc="upper right", frameon=False, ncol=2, fontsize=9, bbox_to_anchor=(1, 1.1))

    fig.suptitle("IDEB 2025 — Escolas do Jardim Macedônia × média da rede em São Paulo",
                 x=0.01, y=0.975, ha="left", fontsize=15, fontweight="bold", color=TEXTO)
    fig.text(0.01, 0.885,
             "Comparação somente com escolas da mesma rede administrativa e da mesma etapa.",
             fontsize=10, color=TEXTO_SECUNDARIO)
    rodape(fig, [
        "As médias usam apenas IDEBs divulgados e incluem a própria escola analisada.",
        "Escolas identificadas por código INEP (35010281 e 35044386): o Censo 2025 não traz o "
        "bairro, e elas não representam todas as escolas do Jardim Macedônia.",
    ])
    fig.savefig(caminho, dpi=DPI)
    plt.close(fig)
    return caminho
