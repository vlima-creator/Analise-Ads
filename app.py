import pandas as pd
import streamlit as st

st.set_page_config(page_title="Mercado Ads - Análise", layout="wide")

st.title("Mercado Ads - Análise Estratégica")
st.caption("Suba os relatórios do Mercado Livre e veja base consolidada + análise por espaços.")

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

def read_xlsx(f) -> pd.DataFrame:
    return pd.read_excel(f)

def ensure_cols(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    cols = df.columns.tolist()
    ren = {c_exist: c_pad for c_exist, c_pad in mapping.items() if c_exist in cols}
    return df.rename(columns=ren)

def status_produto(row) -> str:
    dep = row.get("dependencia_ads", 0) or 0
    acos = row.get("acos", 0) or 0

    if dep > dep_alta and acos > acos_bom:
        return "Sanguessuga"
    if dep <= dep_alta and acos > acos_bom:
        return "Gastao"
    if dep <= dep_baixa:
        return "Estrela"
    return "Potencial"

def status_espaco(acos: float) -> str:
    if pd.isna(acos):
        return ""
    if acos <= acos_bom:
        return "Saudavel"
    if acos <= acos_atencao:
        return "Atencao"
    return "Critico"

# Validação de uploads
if not all([pub_file, ads_file, prod_file, esp_file]):
    st.info("Envie os 4 relatórios para gerar a análise.")
    st.stop()

# Leitura
pub = read_xlsx(pub_file)
ads = read_xlsx(ads_file)
prod = read_xlsx(prod_file)
esp = read_xlsx(esp_file)

# Normalização: ajuste nomes conforme seus relatórios
ads = ensure_cols(ads, {
    "ID do anúncio": "id_anuncio",
    "ID_Anuncio": "id_anuncio",
    "Campanha": "campanha",
    "Impressões": "impressoes",
    "Impressoes": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Vendas": "vendas_ads",
    "Vendas_Ads": "vendas_ads",
    "Receita": "receita_ads",
    "Receita_Ads": "receita_ads",
    "ACOS": "acos",
    "ROAS": "roas",
})

pub = ensure_cols(pub, {
    "ID do anúncio": "id_anuncio",
    "ID_Anuncio": "id_anuncio",
    "SKU": "sku",
    "Visitas": "visitas",
    "Quantidade de vendas": "vendas_publicacao",
    "Vendas_Publicacao": "vendas_publicacao",
    "Conversão de visitas em vendas": "conv_organica",
    "Conversao_Organica": "conv_organica",
})

prod = ensure_cols(prod, {
    "SKU": "sku",
    "Quantidade de vendas": "vendas_totais",
    "Vendas_Totais": "vendas_totais",
    "Vendas brutas (BRL)": "receita_total",
    "Vendas brutas": "receita_total",
    "Receita_Total": "receita_total",
})

esp = ensure_cols(esp, {
    "Espaço de publicidade": "espaco",
    "Espaco_Publicidade": "espaco",
    "Impressões": "impressoes",
    "Impressoes": "impressoes",
    "Cliques": "cliques",
    "Investimento": "investimento",
    "Quantidade de vendas": "vendas_ads",
    "Vendas_Ads": "vendas_ads",
    "Vendas brutas (BRL)": "receita_ads",
    "Vendas brutas": "receita_ads",
    "Receita_Ads": "receita_ads",
})

# Checagem mínima de colunas essenciais
required_ads = {"id_anuncio", "campanha", "impressoes", "cliques", "investimento", "receita_ads", "acos", "roas"}
if not required_ads.issubset(set(ads.columns)):
    st.error(f"Relatório RAW_ADS não tem todas as colunas necessárias. Encontradas: {list(ads.columns)}")
    st.stop()

required_pub = {"id_anuncio", "sku", "visitas", "conv_organica"}
if not required_pub.issubset(set(pub.columns)):
    st.error(f"Relatório RAW_PUBLICACOES não tem todas as colunas necessárias. Encontradas: {list(pub.columns)}")
    st.stop()

# Base consolidada
base = ads.copy()

base = base.merge(
    pub[["id_anuncio", "sku", "visitas", "conv_organica"]],
    on="id_anuncio",
    how="left"
)

if "sku" in prod.columns:
    base = base.merge(
        prod[["sku", "vendas_totais", "receita_total"]],
        on="sku",
        how="left"
    )

# Métricas
base["dependencia_ads"] = (base["receita_ads"].fillna(0) / base["receita_total"].replace({0: pd.NA})).fillna(0)
base["ctr"] = (base["cliques"].fillna(0) / base["impressoes"].replace({0: pd.NA})).fillna(0)

# Status e ação (aqui está a correção do seu erro)
base["status_produto"] = base.apply(status_produto, axis=1)
base["acao_recomendada"] = base["status_produto"].map({
    "Estrela": "Escalar",
    "Potencial": "Dar tracao",
    "Gastao": "Ajustar ACOS / Oferta",
    "Sanguessuga": "Pausar ou corrigir oferta",
}).fillna("")

# Análise por espaços
esp_group = esp.groupby("espaco", dropna=False).agg(
    investimento_total=("investimento", "sum"),
    receita_total=("receita_ads", "sum")
).reset_index()

esp_group["acos_espaco"] = (esp_group["investimento_total"] / esp_group["receita_total"].replace({0: pd.NA})).fillna(0)
esp_group["roas_espaco"] = (esp_group["receita_total"] / esp_group["investimento_total"].replace({0: pd.NA})).fillna(0)
esp_group["status_espaco"] = esp_group["acos_espaco"].apply(status_espaco)

# KPIs
c1, c2, c3, c4 = st.columns(4)

invest_total = float(base["investimento"].fillna(0).sum())
receita_ads_total = float(base["receita_ads"].fillna(0).sum())
receita_total = float(base["receita_total"].fillna(0).sum())

acos_global = (invest_total / receita_ads_total) if receita_ads_total else 0
dep_global = (receita_ads_total / receita_total) if receita_total else 0

def brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

c1.metric("Investimento (Ads)", brl(invest_total))
c2.metric("Receita Ads", brl(receita_ads_total))
c3.metric("ACOS Global", f"{acos_global:.2%}".replace(".", ","))
c4.metric("Dependência Ads", f"{dep_global:.2%}".replace(".", ","))

tab1, tab2 = st.tabs(["Base consolidada", "Espaços de publicidade"])

with tab1:
    st.subheader("Produtos e campanhas")
    cols = [
        "campanha","id_anuncio","sku",
        "impressoes","cliques","investimento","receita_ads","acos","roas",
        "visitas","conv_organica","vendas_totais","receita_total",
        "dependencia_ads","ctr","status_produto","acao_recomendada"
    ]
    cols = [c for c in cols if c in base.columns]
    st.dataframe(base[cols], use_container_width=True)

    st.download_button(
        "Baixar base consolidada (CSV)",
        data=base.to_csv(index=False).encode("utf-8"),
        file_name="base_consolidada.csv",
        mime="text/csv"
    )

with tab2:
    st.subheader("Análise por espaço")
    st.dataframe(esp_group, use_container_width=True)

    st.download_button(
        "Baixar análise de espaços (CSV)",
        data=esp_group.to_csv(index=False).encode("utf-8"),
        file_name="analise_espacos.csv",
        mime="text/csv"
    )
