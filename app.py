import pandas as pd
import streamlit as st
import unicodedata
import re

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

def normalize_colname(s: str) -> str:
    """
    Normaliza o nome da coluna para facilitar match:
    - remove acentos
    - remove quebras de linha
    - reduz espaços
    - deixa minúsculo
    """
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\n", " ").replace("\r", " ").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s)
    return s

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
    best_i = 0
    best_score = -1
    for i in range(len(preview)):
        row = preview.iloc[i]
        text = _row_to_text(row).lower()
        non_empty = sum(1 for x in row.tolist() if pd.notna(x) and str(x).strip() != "")
        kw_hits = sum(1 for kw in required_keywords if kw.lower() in text)
        penalty = 3 if non_empty <= 1 else 0
        score = (kw_hits * 10) + non_empty - penalty
        if score > best_score:
            best_score = score
            best_i = i
    return best_i

def read_xlsx_smart(f, required_keywords=None, max_scan_rows=80) -> pd.DataFrame:
    if required_keywords is None:
        required_keywords = ["campanha", "anuncio", "impress", "cliq", "invest", "receita", "acos", "roas"]

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

            if df.shape[1] <= 2:
                continue

            if df.shape[1] > best_cols:
                best_cols = df.shape[1]
                best_df = df
        except Exception:
            continue

    if best_df is None:
        df = pd.read_excel(f)
        df = _clean_columns(df)
        return df

    return best_df

def rename_by_normalized(df: pd.DataFrame, mapping_norm: dict) -> pd.DataFrame:
    """
    mapping_norm: dict com chaves já normalizadas -> nome padrão
    """
    ren = {}
    for col in df.columns:
        key = normalize_colname(col)
        if key in mapping_norm:
            ren[col] = mapping_norm[key]
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

# ================= Read files =================

camp = read_xlsx_smart(camp_file, required_keywords=["campanha", "orcamento", "acos", "impress", "cliq", "invest", "receita"])
esp = read_xlsx_smart(esp_file, required_keywords=["espaco", "impress", "cliq", "invest", "vendas", "receita"])
ads = read_xlsx_smart(ads_file, required_keywords=["campanha", "anuncio", "impress", "cliq", "invest", "receita", "acos", "roas"])

# ================= Normalize / Rename (fuzzy) =================

ads = rename_by_normalized(ads, {
    normalize_colname("Código do anúncio"): "id_anuncio",
    normalize_colname("ID do anúncio"): "id_anuncio",
    normalize_colname("Campanha"): "campanha",
    normalize_colname("impressões"): "impressoes",
    normalize_colname("impressoes"): "impressoes",
    normalize_colname("cliques"): "cliques",
    normalize_colname("Receita (Moeda local)"): "receita_ads",
    normalize_colname("Investimento (Moeda local)"): "investimento",
    normalize_colname("ACOS (Investimento / Receitas)"): "acos",
    normalize_colname("ROAS (Receitas / Investimento)"): "roas",
})

camp = rename_by_normalized(camp, {
    normalize_colname("Nome da campanha"): "campanha",
    normalize_colname("Campanha"): "campanha",
    normalize_colname("Orçamento médio diário"): "orcamento_diario",
    normalize_colname("ACOS Objetivo"): "acos_objetivo",
    normalize_colname("ACOS"): "acos_campanha",
    normalize_colname("Investimento"): "investimento_campanha",
    normalize_colname("Receita"): "receita_campanha",
    normalize_colname("Impressões"): "impressoes_campanha",
    normalize_colname("Cliques"): "cliques_campanha",
})

esp = rename_by_normalized(esp, {
    normalize_colname("Espaço de publicidade"): "espaco",
    normalize_colname("Espaco de publicidade"): "espaco",
    normalize_colname("impressões"): "impressoes",
    normalize_colname("impressoes"): "impress_
