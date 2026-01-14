import re
import math
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Mercado Livre Ads - Relatório Estratégico", layout="wide")

# =========================
# Helpers
# =========================

def _to_number(x):
    """Converte strings tipo 'R$ 1.234,56', '12,3%', '1.234' em float."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return float("nan")
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "-"}:
        return float("nan")

    s = s.replace("R$", "").replace("$", "").strip()
    is_percent = "%" in s
    s = s.replace("%", "").strip()

    # remove espaços e separadores de milhar comuns
    s = s.replace("\u00a0", " ")
    s = s.replace(" ", "")
    s = s.replace(".", "")  # remove milhar pt-br
    s = s.replace(",", ".")  # decimal pt-br

    try:
        v = float(s)
    except:
        return float("nan")

    if is_percent:
        return v / 100.0
    return v


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_col(df, candidates):
    """Retorna o nome da coluna existente no df que bate com algum candidato (case-insensitive)."""
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    # fallback por contains
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None


def coerce_numeric(df, colnames):
    out = df.copy()
    for c in colnames:
        if c and c in out.columns:
            out[c] = out[c].map(_to_number)
    return out


def safe_div(a, b):
    if b is None or (isinstance(b, float) and (math.isnan(b) or b == 0)):
        return float("nan")
    if isinstance(b, (int, float)) and b == 0:
        return float("nan")
    return a / b


def fmt_money(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    return f"{v*100:.1f}%".replace(".", ",")


def fmt_num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    if abs(v) >= 1000:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:.0f}"


def infer_period_label(text_hint: str):
    if not text_hint:
        return "Período"
    s = text_hint.strip()
    return s


# =========================
# Core logic
# =========================

def analyze_campaigns(df_camp: pd.DataFrame):
    df_camp = normalize_columns(df_camp)

    col_name = find_col(df_camp, ["Nome da Campanha", "Campanha", "Campaign", "Nome campanha", "Nome"])
    col_budget = find_col(df_camp, ["Orçamento", "Orçamento diário", "Orcamento diario", "Budget", "Orçamento médio diário"])
    col_acos_target = find_col(df_camp, ["ACOS Objetivo", "ACOS alvo", "ACOS Objetivo Atual", "ACOS objetivo"])
    col_spend = find_col(df_camp, ["Investimento", "Gasto", "Spend", "Custo"])
    col_revenue = find_col(df_camp, ["Receita", "Vendas", "Vendas por Product Ads", "Sales", "Faturamento"])
    col_loss_budget = find_col(df_camp, ["% Perda Orçamento", "Perda por Orçamento", "Loss budget", "Perda orçamento"])
    col_loss_rank = find_col(df_camp, ["% Perda Classificação", "Perda por Classificação", "Perda por rank", "Loss rank", "Classificação"])

    needed = [col_name, col_spend, col_revenue]
    if any(x is None for x in needed):
        return None, {
            "error": "Não consegui identificar colunas mínimas no relatório de campanhas. Preciso de algo como Nome da Campanha, Investimento/Gasto e Receita/Vendas."
        }

    df = df_camp.copy()

    df = coerce_numeric(df, [col_budget, col_acos_target, col_spend, col_revenue, col_loss_budget, col_loss_rank])

    df["Investimento"] = df[col_spend]
    df["Receita"] = df[col_revenue]
    df["ROAS"] = df.apply(lambda r: safe_div(r["Receita"], r["Investimento"]), axis=1)
    df["ACOS_real"] = df.apply(lambda r: safe_div(r["Investimento"], r["Receita"]), axis=1)

    df["Campanha"] = df[col_name].astype(str)

    if col_budget:
        df["Orçamento_atual"] = df[col_budget]
    else:
        df["Orçamento_atual"] = float("nan")

    if col_acos_target:
        df["ACOS_objetivo"] = df[col_acos_target]
    else:
        df["ACOS_objetivo"] = float("nan")

    if col_loss_budget:
        df["Perda_orc"] = df[col_loss_budget]
    else:
        df["Perda_orc"] = float("nan")

    if col_loss_rank:
        df["Perda_rank"] = df[col_loss_rank]
    else:
        df["Perda_rank"] = float("nan")

    # Pareto 80% da receita
    df_sorted = df.sort_values("Receita", ascending=False).reset_index(drop=True)
    total_rev = df_sorted["Receita"].sum(skipna=True)
    df_sorted["rev_share"] = df_sorted["Receita"] / total_rev if total_rev else float("nan")
    df_sorted["rev_cum"] = df_sorted["rev_share"].cumsum()

    df_sorted["Prioridade_Pareto"] = df_sorted["rev_cum"] <= 0.80

    # Matriz de oportunidade
    # Regras do prompt:
    # ESCALA ORÇAMENTO: ROAS > 7 e perda orçamento > 40%
    # COMPETITIVIDADE: receita relevante e perda rank > 50%
    # HEMORRAGIA: ACOS real muito acima do objetivo OU ROAS < 3 sem justificativa
    # ESTÁVEL: resto
    def classify(row):
        roas = row["ROAS"]
        perda_orc = row["Perda_orc"]
        perda_rank = row["Perda_rank"]
        receita = row["Receita"]
        acos_real = row["ACOS_real"]
        acos_obj = row["ACOS_objetivo"]

        if not math.isnan(roas) and roas > 7 and (not math.isnan(perda_orc) and perda_orc > 0.40):
            return "ESCALA_ORCAMENTO"

        # receita relevante. aqui usamos Pareto ou pelo menos receita acima da mediana
        receita_relevante = False
        if not math.isnan(receita):
            med = df_sorted["Receita"].median(skipna=True)
            receita_relevante = (receita >= med) or bool(row.get("Prioridade_Pareto", False))

        if receita_relevante and (not math.isnan(perda_rank) and perda_rank > 0.50):
            return "COMPETITIVIDADE"

        # hemorragia
        if not math.isnan(roas) and roas < 3:
            return "HEMORRAGIA"
        if (not math.isnan(acos_obj)) and (not math.isnan(acos_real)) and acos_real > (acos_obj * 1.35):
            return "HEMORRAGIA"

        return "ESTAVEL"

    df_sorted["Quadrante"] = df_sorted.apply(classify, axis=1)

    def action_emoji(q):
        if q == "ESCALA_ORCAMENTO":
            return "🟢 Aumentar Orçamento"
        if q == "COMPETITIVIDADE":
            return "🟡 Subir ACOS Alvo"
        if q == "HEMORRAGIA":
            return "🔴 Revisar/Pausar"
        return "🔵 Manter"

    df_sorted["AÇÃO RECOMENDADA"] = df_sorted["Quadrante"].map(action_emoji)

    # Seleção das campanhas que "mudam o jogo"
    gamechangers = df_sorted[df_sorted["Prioridade_Pareto"]].head(10).copy()

    return df_sorted, {
        "total_receita": float(total_rev) if not math.isnan(total_rev) else 0.0,
        "total_invest": float(df_sorted["Investimento"].sum(skipna=True)),
        "roas_conta": safe_div(df_sorted["Receita"].sum(skipna=True), df_sorted["Investimento"].sum(skipna=True)),
        "acos_conta": safe_div(df_sorted["Investimento"].sum(skipna=True), df_sorted["Receita"].sum(skipna=True)),
        "gamechangers": gamechangers
    }


def analyze_ads(df_ads: pd.DataFrame):
    df_ads = normalize_columns(df_ads)

    col_title = find_col(df_ads, ["Título do anúncio", "Titulo", "Anúncio", "Anuncio", "Item", "Publicação", "Publicacao"])
    col_mlb = find_col(df_ads, ["MLB", "Item ID", "ID do item", "Item_id", "ID"])
    col_spend = find_col(df_ads, ["Investimento", "Gasto", "Spend", "Custo"])
    col_revenue = find_col(df_ads, ["Receita", "Vendas", "Sales", "Faturamento"])
    col_units = find_col(df_ads, ["Unidades", "Unidades vendidas", "Units"])
    col_clicks = find_col(df_ads, ["Cliques", "Clicks"])
    col_impr = find_col(df_ads, ["Impressões", "Impressoes", "Impressions"])
    col_acos = find_col(df_ads, ["ACOS", "ACOS real", "ACOS Real"])
    col_roas = find_col(df_ads, ["ROAS", "ROAS real", "ROAS Real"])

    needed = [col_spend, col_revenue]
    if any(x is None for x in needed):
        return None, {
            "error": "Não consegui identificar Investimento/Gasto e Receita/Vendas no relatório de anúncios patrocinados."
        }

    df = df_ads.copy()
    df = coerce_numeric(df, [col_spend, col_revenue, col_units, col_clicks, col_impr, col_acos, col_roas])

    df["Investimento"] = df[col_spend]
    df["Receita"] = df[col_revenue]

    if col_roas:
        df["ROAS"] = df[col_roas]
    else:
        df["ROAS"] = df.apply(lambda r: safe_div(r["Receita"], r["Investimento"]), axis=1)

    if col_acos:
        df["ACOS_real"] = df[col_acos]
        # às vezes vem em %, às vezes vem em decimal. tentamos normalizar.
        # se vier tipo 15 (1500%), ajusta. se vier tipo 0.15 ok. se vier 15% já virou 0.15 no parser.
        df.loc[df["ACOS_real"] > 2, "ACOS_real"] = df.loc[df["ACOS_real"] > 2, "ACOS_real"] / 100.0
    else:
        df["ACOS_real"] = df.apply(lambda r: safe_div(r["Investimento"], r["Receita"]), axis=1)

    if col_title:
        df["Anúncio"] = df[col_title].astype(str)
    else:
        df["Anúncio"] = "Anúncio"

    if col_mlb:
        df["MLB"] = df[col_mlb].astype(str)
    else:
        df["MLB"] = "-"

    # Classificação por anúncio
    def tag(row):
        roas = row["ROAS"]
        acos = row["ACOS_real"]
        inv = row["Investimento"]
        rev = row["Receita"]
        units = row[col_units] if col_units else float("nan")

        # Estrela: ROAS alto e receita com alguma tração
        if not math.isnan(roas) and roas >= 7 and (not math.isnan(rev) and rev > 0):
            return "ESTRELA"

        # Sanguessuga: investe e não retorna
        if (not math.isnan(inv) and inv > 0) and (math.isnan(rev) or rev == 0):
            return "SANGUESSUGA"

        # Gastão: vende mas ROAS ruim
        if not math.isnan(roas) and roas < 3 and (not math.isnan(rev) and rev > 0):
            return "GASTAO"

        return "NEUTRO"

    df["Perfil"] = df.apply(tag, axis=1)

    return df.sort_values("Investimento", ascending=False), {
        "top_sanguessugas": df[df["Perfil"] == "SANGUESSUGA"].sort_values("Investimento", ascending=False).head(25),
        "top_gastoes": df[df["Perfil"] == "GASTAO"].sort_values("Investimento", ascending=False).head(25),
        "top_estrelas": df[df["Perfil"] == "ESTRELA"].sort_values("Receita", ascending=False).head(25),
    }


def render_report(camp_df, camp_meta, ads_df, ads_meta, period_label):
    st.markdown("## Relatório Estratégico de Performance")
    st.caption(period_label)

    # 1. Diagnóstico Executivo
    st.markdown("### 1. Diagnóstico Executivo")

    roas_conta = camp_meta.get("roas_conta")
    acos_conta = camp_meta.get("acos_conta")
    total_rev = camp_meta.get("total_receita")
    total_inv = camp_meta.get("total_invest")

    colA, colB, colC, colD = st.columns(4)
    colA.metric("Receita (Ads)", fmt_money(total_rev))
    colB.metric("Investimento", fmt_money(total_inv))
    colC.metric("ROAS da conta", "-" if math.isnan(roas_conta) else f"{roas_conta:.2f}")
    colD.metric("ACOS da conta", fmt_pct(acos_conta))

    veredito = []
    if not math.isnan(roas_conta) and roas_conta >= 7:
        veredito.append("Eficiência geral forte. Dá para escalar com segurança, desde que você corte sangrias.")
    elif not math.isnan(roas_conta) and roas_conta < 3:
        veredito.append("Conta em modo hemorragia. Corte imediato e ajuste de funil antes de pensar em escala.")
    else:
        veredito.append("Conta em faixa intermediária. Escala só onde o gargalo é verba ou rank, e corte do que drena.")

    # Tendências não dá para afirmar sem split 7x7. Aqui só orienta.
    st.write("- Resumo do cenário atual: eficiência e distribuição de investimento entre campanhas.")
    st.write("- Alerta de tendências: para detectar inflação real de leilão, traga também o recorte 7 dias vs 7 dias anterior no export.")
    st.write(f"- Veredito: {veredito[0]}")

    # 2. Matriz CPI
    st.markdown("### 2. Análise de Oportunidades (Matriz CPI)")

    gamechangers = camp_meta["gamechangers"].copy()
    locomotivas = gamechangers[gamechangers["Quadrante"] == "COMPETITIVIDADE"].head(5)
    minas = gamechangers[gamechangers["Quadrante"] == "ESCALA_ORCAMENTO"].head(5)
    hemo = gamechangers[gamechangers["Quadrante"] == "HEMORRAGIA"].head(5)

    st.markdown("**As Locomotivas (Faturamento Alto + Problema de Rank)**")
    if len(locomotivas) == 0:
        st.write("Nenhuma locomotiva detectada com os dados atuais de perda por rank. Se sua planilha não tem essa coluna, o app não consegue classificar por rank.")
    else:
        show = locomotivas[["Campanha", "Receita", "Investimento", "ROAS", "Perda_rank", "AÇÃO RECOMENDADA"]].copy()
        st.dataframe(show, use_container_width=True)

    st.markdown("**As Minas Limitadas (ROAS Alto + Falta de Verba)**")
    if len(minas) == 0:
        st.write("Nenhuma mina limitada detectada com os critérios atuais. Se sua planilha não tem perda por orçamento, o app não consegue confirmar esse quadrante.")
    else:
        show = minas[["Campanha", "Receita", "Investimento", "ROAS", "Perda_orc", "AÇÃO RECOMENDADA"]].copy()
        st.dataframe(show, use_container_width=True)

    if len(minas) > 0:
        # projeção simples, sem prometer exatidão
        minas_proj = minas.copy()
        minas_proj["Receita_proj"] = minas_proj["Receita"] * 1.25
        minas_proj["Ganho_proj"] = minas_proj["Receita_proj"] - minas_proj["Receita"]
        gain = minas_proj["Ganho_proj"].sum(skipna=True)
        st.write(f"Projeção conservadora: destravando orçamento nas minas, potencial de +{fmt_money(gain)} em receita no próximo ciclo, se o ROAS se mantiver.")

    if len(hemo) > 0:
        st.markdown("**Hemorragias (Detratoras)**")
        show = hemo[["Campanha", "Receita", "Investimento", "ROAS", "ACOS_real", "AÇÃO RECOMENDADA"]].copy()
        st.dataframe(show, use_container_width=True)

    # 3. Plano de ação
    st.markdown("### 3. Plano de Ação Tático (Próximos 7 Dias)")

    st.markdown("**Dia 1 (Destravar):**")
    if len(minas) > 0:
        for _, r in minas.iterrows():
            st.write(f"- Aumente orçamento: {r['Campanha']} (ROAS {r['ROAS']:.2f}, perda orçamento {fmt_pct(r['Perda_orc'])})")
    else:
        st.write("- Aumente orçamento apenas nas campanhas com ROAS alto e histórico de travamento por verba.")

    st.markdown("**Dia 2 (Competir):**")
    if len(locomotivas) > 0:
        for _, r in locomotivas.iterrows():
            st.write(f"- Suba ACOS objetivo: {r['Campanha']} (perda rank {fmt_pct(r['Perda_rank'])})")
    else:
        st.write("- Suba ACOS objetivo nas campanhas com receita forte que estão perdendo rank.")

    st.markdown("**Dia 3 (Estancar):**")
    if len(hemo) > 0:
        for _, r in hemo.iterrows():
            st.write(f"- Corte ou reduza agressividade: {r['Campanha']} (ROAS {r['ROAS']:.2f})")
    else:
        st.write("- Corte campanhas com ROAS abaixo de 3 que não tenham tese clara de lançamento.")

    st.markdown("**Dia 5 (Monitorar):**")
    st.write("- Vigie: ROAS das campanhas escaladas, estabilidade de receita, e se o investimento cresce mais rápido que a receita.")
    st.write("- Se o ROAS cair forte após abrir funil, você abriu demais. Recuar um pouco e reavaliar no próximo ciclo.")

    # 4. Painel Geral
    st.markdown("### 4. 📋 Painel de Controle Geral")
    painel = camp_df[[
        "Campanha", "Orçamento_atual", "ACOS_objetivo", "ROAS", "Perda_orc", "Perda_rank", "AÇÃO RECOMENDADA"
    ]].copy()

    painel = painel.rename(columns={
        "Campanha": "Nome da Campanha",
        "Orçamento_atual": "Orçamento Atual",
        "ACOS_objetivo": "ACOS Objetivo Atual",
        "ROAS": "ROAS Real (Calculado)",
        "Perda_orc": "% Perda Orçamento",
        "Perda_rank": "% Perda Classificação (Rank)",
    })

    st.dataframe(painel, use_container_width=True)

    # Anúncios patrocinados, corte de sangria
    if ads_df is not None:
        st.markdown("### Corte de Sangria em Produtos e Anúncios")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🔴 Sanguessugas (investe e não vende)**")
            st.dataframe(
                ads_meta["top_sanguessugas"][["MLB", "Anúncio", "Investimento", "Receita", "ROAS", "ACOS_real"]]
                if "Anúncio" in ads_meta["top_sanguessugas"].columns else ads_meta["top_sanguessugas"],
                use_container_width=True
            )

        with col2:
            st.markdown("**🟡 Gastões (vende mas destrói margem)**")
            st.dataframe(
                ads_meta["top_gastoes"][["MLB", "Anúncio", "Investimento", "Receita", "ROAS", "ACOS_real"]]
                if "Anúncio" in ads_meta["top_gastoes"].columns else ads_meta["top_gastoes"],
                use_container_width=True
            )

        with col3:
            st.markdown("**🟢 Estrelas (o que merece escala)**")
            st.dataframe(
                ads_meta["top_estrelas"][["MLB", "Anúncio", "Investimento", "Receita", "ROAS", "ACOS_real"]]
                if "Anúncio" in ads_meta["top_estrelas"].columns else ads_meta["top_estrelas"],
                use_container_width=True
            )


# =========================
# UI
# =========================

st.title("Mercado Livre Ads, Relatório Estratégico Automatizado")

with st.expander("Como usar", expanded=True):
    st.write("1) Faça upload do Relatório de Campanhas do período.")
    st.write("2) Faça upload do Relatório de Anúncios Patrocinados do mesmo período.")
    st.write("3) Confira o relatório pronto e exporte as tabelas se quiser.")
    st.write("Dica: 15 dias é o ciclo ideal para validar mudanças.")

period_label = st.text_input("Rótulo do período (opcional)", value="Últimos 15 dias")

camp_file = st.file_uploader("Relatório de Campanhas (Excel ou CSV)", type=["xlsx", "xls", "csv"])
ads_file = st.file_uploader("Relatório de Anúncios Patrocinados (Excel ou CSV)", type=["xlsx", "xls", "csv"])

def read_any(file):
    if file is None:
        return None
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

if camp_file:
    df_camp = read_any(camp_file)
    camp_df, camp_meta = analyze_campaigns(df_camp)
    if camp_df is None:
        st.error(camp_meta["error"])
        st.stop()

    ads_df = None
    ads_meta = None
    if ads_file:
        df_ads = read_any(ads_file)
        ads_df, ads_meta = analyze_ads(df_ads)
        if ads_df is None:
            st.warning(ads_meta["error"])
            ads_df = None
            ads_meta = None

    render_report(camp_df, camp_meta, ads_df, ads_meta, infer_period_label(period_label))

else:
    st.info("Envie pelo menos o Relatório de Campanhas para gerar o relatório.")
