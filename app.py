import pandas as pd
import streamlit as st

st.set_page_config(page_title="Mercado Ads - Análise", layout="wide")

st.title("Mercado Ads - Análise Estratégica")
st.caption("Envie 3 relatórios do Mercado Livre: Campanhas, Espaços de Publicidade e Anúncios Patrocinados.")

with st.sidebar:
    st.header("Uploads")
    camp_file = st.file_uploader("Relatório de Campanhas", type=["xlsx"])
    esp_file = st.file_uploader("Relatório de Espaços de Publicidade", type=["xlsx"])
    ads_file = st.file_uploader("Relatório de Anúncios Patrocinados", type=["xlsx"])

    st.divider()
    st.subheader("Regras")
    acos_bom = st.number_input("ACOS bom", min_value=0.0, max_value=1.0, value=0.12, step=0.01)
    acos_atencao = st.number_input("ACOS atenção", min_value=0.0, max_value=1.0, value=0.18, step=0.01)

# ================= Helpers =================

def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    return df

def _row_to_text(row: pd.Series) -> str:
    parts = []
    for x in row.tolist():
        if pd.notna(x):
            s = str(x).strip()
            if s:
                parts.append(s)
    return " ".join(parts)

def _find_best_header_row(preview: pd.DataFrame, required_keywords: list[str]) -> int:
    """
    Escolhe a linha que mais parece cabeçalho:
    - muitas células preenchidas
    - muitas palavras-chave
    - evita linhas com uma frase única tipo "Confira em detalhes..."
    """
    best_i = 0
    best_score = -1

    for i in range(len(preview)):
        row = preview.iloc[i]
        text = _row_to_text(row).lower()

        non_empty = sum(1 for x in row.tolist() if pd.notna(x) and str(x).strip() != "")
        kw_hits = sum(1 for kw in required_keywords if kw.lower() in text)

        # Penaliza linhas com 1 célula preenchida (geralmente título/capa)
        penalty = 3 if non_empty <= 1 else 0

        score = (kw_hits * 10) + non_empty - penalty

        if score > best_score:
            best_score = score
            best_i = i

    return best_i

def read_xlsx_smart(f, required_keywords=None, max_scan_rows=60) -> pd.DataFrame:
    """
    Lê XLSX de um jeito mais inteligente:
    - testa todas as abas
    - em cada aba, procura a melhor linha de header
    - escolhe a combinação (aba + header) que gera mais colunas úteis
    """
    if required_keywords is None:
        required_keywords = ["campanha", "anúncio", "anuncio", "impress", "cliq", "invest", "receita", "acos", "roas"]

    xls = pd.ExcelFile(f)
    best_df = None
    best_cols = -1

    for sheet in xls.sheet_names:
        try:
            preview = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=max_scan_rows)
            header_row = _find_best_header_row(preview, required_keywords)

            df = pd.read_excel(xls, sheet_name=sheet, header=header_row)
            df = _clean_columns(df)
            df = df.dropna(how="all")

            # ignora caso ainda esteja ruim (poucas colunas ou colunas com frase única)
            if df.shape[1] <= 2:
                continue

            # evita situação em que a "coluna" é uma frase só
            if df.shape[1] == 1:
                continue

            if df.shape[1] > best_cols:
                best_cols = df.shape[1]
                best_df = df

        except Exception:
            continue

    if best_df is None:
        # fallback simples
        df = pd.read_excel(f)
        df = _clean_columns(df)
        return df

    return best_df

def ensure_cols(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    cols = df.columns.tolist()
    ren = {c_exist: c_pad for c_exist, c_pad in mapping.items() if c_exist in cols}
    return df.rename(columns=ren)

def status_por_acos(acos: float) -> str:
    if pd.isna(acos):
        return ""
    if acos <= acos_bom:
        return "Saudavel"
    if acos <= acos_atencao:
        return "Atencao"
    return "Critico"

def acao_por_status(status: str) -> str:
    if status == "Saudavel":
        return "Escalar com controle"
    if status == "Atencao":
        return "Ajustar lances / segmentacao"
    if status == "Critico":
        return "Reduzir verba e corrigir oferta"
    return ""

def brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ================= Upload validation =================

if not all([camp_file, esp_file, ads_file]):
    st.info("Envie os 3 relatórios para gerar a análise.")
    st.stop()

# ================= Read files (smart) =================

camp = read_xlsx_smart(camp_file, required_keywords=["campanha", "orçamento", "acos", "impress", "cliq", "invest", "receita"])
esp = read_xlsx_smart(esp_file, required_keywords=["espaço", "espaco", "impress", "cliq", "invest", "vendas", "receita"])
ads = read_xlsx_smart(ads_file, required_keywords=["campanha", "anúncio", "anuncio", "impress", "cliq", "invest", "receita", "acos", "roas"])

# ================= Normalize columns =================

ads = ensure_cols(ads, {
    "ID do anúncio": "id_anuncio",
    "Id do anúncio": "id_anuncio",
    "ID_Anuncio": "id_anuncio",
    "Nome da campanha": "campanha",
    "Campanha": "campanha",
    "Impressões": "impressoes",
    "Impressoes": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Custo": "investimento",
    "Receita": "receita_ads",
    "Receita_Ads": "receita_ads",
    "Vendas": "vendas_ads",
    "Vendas_Ads": "vendas_ads",
    "ACOS": "acos",
    "ROAS": "roas",
})

camp = ensure_cols(camp, {
    "Nome da campanha": "campanha",
    "Campanha": "campanha",
    "Orçamento médio diário": "orcamento_diario",
    "Orcamento medio diario": "orcamento_diario",
    "ACOS Objetivo": "acos_objetivo",
    "ACOS objetivo": "acos_objetivo",
    "ACOS": "acos_campanha",
})

esp = ensure_cols(esp, {
    "Espaço de publicidade": "espaco",
    "Espaco de publicidade": "espaco",
    "Espaco_Publicidade": "espaco",
    "Impressões": "impressoes",
    "Impressoes": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Quantidade de vendas": "vendas_ads",
    "Vendas": "vendas_ads",
    "Vendas brutas (BRL)": "receita_ads",
    "Vendas brutas": "receita_ads",
    "Receita": "receita_ads",
})

# ================= Required checks =================

required_ads = {"campanha", "impressoes", "cliques", "investimento", "receita_ads"}
missing_ads = required_ads - set(ads.columns)
if missing_ads:
    st.error(f"Relatório de Anúncios Patrocinados não tem colunas essenciais: {sorted(missing_ads)}")
    st.write("Colunas encontradas:", list(ads.columns))
    st.stop()

# id_anuncio pode não existir dependendo do tipo de exportação
if "id_anuncio" not in ads.columns:
    ads["id_anuncio"] = ""

required_esp = {"espaco", "investimento", "receita_ads"}
missing_esp = required_esp - set(esp.columns)
if missing_esp:
    st.error(f"Relatório de Espaços não tem colunas essenciais: {sorted(missing_esp)}")
    st.write("Colunas encontradas:", list(esp.columns))
    st.stop()

# cria ACOS/ROAS se não existirem
if "acos" not in ads.columns:
    ads["acos"] = (ads["investimento"].fillna(0) / ads["receita_ads"].replace({0: pd.NA})).fillna(0)

if "roas" not in ads.columns:
    ads["roas"] = (ads["receita_ads"].fillna(0) / ads["investimento"].replace({0: pd.NA})).fillna(0)

# ================= Base consolidada por anúncio =================

base = ads.copy()
base["ctr"] = (base["cliques"].fillna(0) / base["impressoes"].replace({0: pd.NA})).fillna(0)
base["status"] = base["acos"].apply(status_por_acos)
base["acao_recomendada"] = base["status"].apply(acao_por_status)

# Enriquecer com dados do relatório de campanhas
if "campanha" in camp.columns:
    camp_cols = [c for c in ["campanha", "orcamento_diario", "acos_objetivo", "acos_campanha"] if c in camp.columns]
    if camp_cols:
        camp_unique = camp[camp_cols].drop_duplicates(subset=["campanha"])
        base = base.merge(camp_unique, on="campanha", how="left")

# ================= Campanhas (a partir dos anúncios) =================

camp_agg = base.groupby("campanha", dropna=False).agg(
    investimento_total=("investimento", "sum"),
    receita_ads_total=("receita_ads", "sum"),
    impressoes=("impressoes", "sum"),
    cliques=("cliques", "sum"),
).reset_index()

camp_agg["acos"] = (camp_agg["investimento_total"] / camp_agg["receita_ads_total"].replace({0: pd.NA})).fillna(0)
camp_agg["roas"] = (camp_agg["receita_ads_total"] / camp_agg["investimento_total"].replace({0: pd.NA})).fillna(0)
camp_agg["ctr"] = (camp_agg["cliques"] / camp_agg["impressoes"].replace({0: pd.NA})).fillna(0)
camp_agg["status"] = camp_agg["acos"].apply(status_por_acos)
camp_agg["acao_recomendada"] = camp_agg["status"].apply(acao_por_status)

# ================= Espaços =================

if "impressoes" not in esp.columns:
    esp["impressoes"] = 0
if "cliques" not in esp.columns:
    esp["cliques"] = 0

esp_group = esp.groupby("espaco", dropna=False).agg(
    investimento_total=("investimento", "sum"),
    receita_total=("receita_ads", "sum"),
    impressoes=("impressoes", "sum"),
    cliques=("cliques", "sum"),
).reset_index()

esp_group["acos"] = (esp_group["investimento_total"] / esp_group["receita_total"].replace({0: pd.NA})).fillna(0)
esp_group["roas"] = (esp_group["receita_total"] / esp_group["investimento_total"].replace({0: pd.NA})).fillna(0)
esp_group["ctr"] = (esp_group["cliques"] / esp_group["impressoes"].replace({0: pd.NA})).fillna(0)
esp_group["status"] = esp_group["acos"].apply(status_por_acos)
esp_group["acao_recomendada"] = esp_group["status"].apply(acao_por_status)

# ================= KPIs =================

c1, c2, c3, c4 = st.columns(4)
invest_total = float(base["investimento"].fillna(0).sum())
receita_ads_total = float(base["receita_ads"].fillna(0).sum())
acos_global = (invest_total / receita_ads_total) if receita_ads_total else 0
roas_global = (receita_ads_total / invest_total) if invest_total else 0

c1.metric("Investimento (Ads)", brl(invest_total))
c2.metric("Receita Ads", brl(receita_ads_total))
c3.metric("ACOS Global", f"{acos_global:.2%}".replace(".", ","))
c4.metric("ROAS Global", f"{roas_global:.2f}".replace(".", ","))

# ================= UI =================

tab1, tab2, tab3 = st.tabs(["Anúncios", "Campanhas", "Espaços"])

with tab1:
    st.subheader("Base consolidada por anúncio")
    cols = [
        "campanha", "id_anuncio",
        "impressoes", "cliques", "ctr",
        "investimento", "receita_ads", "acos", "roas",
        "status", "acao_recomendada",
        "orcamento_diario", "acos_objetivo", "acos_campanha"
    ]
    cols = [c for c in cols if c in base.columns]
    st.dataframe(base[cols], use_container_width=True)

    st.download_button(
        "Baixar anúncios (CSV)",
        data=base[cols].to_csv(index=False).encode("utf-8"),
        file_name="anuncios.csv",
        mime="text/csv"
    )

with tab2:
    st.subheader("Análise consolidada por campanha (a partir dos anúncios)")
    cols = ["campanha", "investimento_total", "receita_ads_total", "acos", "roas", "ctr", "status", "acao_recomendada"]
    st.dataframe(camp_agg[cols], use_container_width=True)

    st.download_button(
        "Baixar campanhas (CSV)",
        data=camp_agg[cols].to_csv(index=False).encode("utf-8"),
        file_name="campanhas.csv",
        mime="text/csv"
    )

with tab3:
    st.subheader("Análise por espaço de publicidade")
    cols = ["espaco", "investimento_total", "receita_total", "acos", "roas", "ctr", "status", "acao_recomendada"]
    st.dataframe(esp_group[cols], use_container_width=True)

    st.download_button(
        "Baixar espaços (CSV)",
        data=esp_group[cols].to_csv(index=False).encode("utf-8"),
        file_name="espacos.csv",
        mime="text/csv"
    )
