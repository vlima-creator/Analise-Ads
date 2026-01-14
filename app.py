import pandas as pd
import streamlit as st

st.set_page_config(page_title="Mercado Ads - Análise", layout="wide")

st.title("Mercado Ads - Análise Estratégica")
st.caption("Suba os relatórios do Mercado Livre e veja a base consolidada + análise por espaços.")

with st.sidebar:
    st.header("Uploads")
    pub_file = st.file_uploader("Relatório de Publicações", type=["xlsx"])
    ads_file = st.file_uploader("Relatório de Ads (Patrocinados)", type=["xlsx"])
    prod_file = st.file_uploader("Relatório de Produto", type=["xlsx"])
    esp_file = st.file_uploader("Relatório de Espaços de Publicidade", type=["xlsx"])

    st.divider()
    st.subheader("Regras")
    acos_bom = st.number_input("ACOS bom", min_value=0.0, max_value=1.0, value=0.12, step=0.01)
    acos_atencao = st.number_input("ACOS atenção", min_value=0.0, max_value=1.0, value=0.18, step=0.01)
    dep_alta = st.number_input("Dependência Ads alta", min_value=0.0, max_value=1.0, value=0.60, step=0.05)
    dep_baixa = st.number_input("Dependência Ads baixa", min_value=0.0, max_value=1.0, value=0.30, step=0.05)

def read_xlsx(f):
    return pd.read_excel(f)

def ensure_cols(df, mapping):
    # mapping: {col_existente: col_padrao}
    cols = df.columns.tolist()
    ren = {}
    for c_exist, c_pad in mapping.items():
        if c_exist in cols:
            ren[c_exist] = c_pad
    return df.rename(columns=ren)

def status_produto(row):
    dep = row.get("dependencia_ads", 0) or 0
    acos = row.get("acos", 0) or 0
    if dep > dep_alta and acos > acos_bom:
        return "Sanguessuga"
    if dep <= dep_alta and acos > acos_bom:
        return "Gastao"
    if dep <= dep_baixa:
        return "Estrela"
    return "Potencial"

def status_espaco(acos):
    if pd.isna(acos):
        return ""
    if acos <= acos_bom:
        return "Saudavel"
    if acos <= acos_atencao:
        return "Atencao"
    return "Critico"

if not all([pub_file, ads_file, prod_file, esp_file]):
    st.info("Envie os 4 relatórios para gerar a análise.")
    st.stop()

pub = read_xlsx(pub_file)
ads = read_xlsx(ads_file)
prod = read_xlsx(prod_file)
esp = read_xlsx(esp_file)

# Ajuste os nomes das colunas aqui se necessário
# Eu deixei alguns padrões comuns, mas podemos refinar com base nos seus arquivos.
ads = ensure_cols(ads, {
    "ID do anúncio": "id_anuncio",
    "Campanha": "campanha",
    "Impressões": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Vendas": "vendas_ads",
    "Receita": "receita_ads",
    "ACOS": "acos",
    "ROAS": "roas",
})

pub = ensure_cols(pub, {
    "ID do anúncio": "id_anuncio",
    "SKU": "sku",
    "Visitas": "visitas",
    "Quantidade de vendas": "vendas_publicacao",
    "Conversão de visitas em vendas": "conv_organica",
})

prod = ensure_cols(prod, {
    "SKU": "sku",
    "Quantidade de vendas": "vendas_totais",
    "Vendas brutas (BRL)": "receita_total",
    "Vendas brutas": "receita_total",
})

esp = ensure_cols(esp, {
    "Espaço de publicidade": "espaco",
    "Impressões": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Quantidade de vendas": "vendas_ads",
    "Vendas brutas (BRL)": "receita_ads",
    "Vendas brutas": "receita_ads",
})

# Base consolidada por ID do anúncio
base = ads.merge(pub[["id_anuncio", "sku", "visitas", "conv_organica"]], on="id_anuncio", how="left")

# Junta produto por SKU
base = base.merge(prod[["sku", "vendas_totais", "receita_total"]], on="sku", how="left")

# Métricas
base["dependencia_ads"] = (base["receita_ads"].fillna(0) / base["receita_total"].replace({0: pd.NA})).fillna(0)
base["ctr"] = (base["cliques"].fillna(0) / base["impressoes"].replace({0: pd.NA})).fillna(0)

# Status e ação
base["status_produto"] = base.apply(status_produto, axis=1)
base["acao_recomendada"] = bas_]()
