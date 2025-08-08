# ========================
#  ⚙️ Comparatif JSON-LD complet
# ========================
import pandas as pd
import streamlit as st

# -------------------------------------------------
# 🔧 Fonction utilitaire : normaliser un schéma en paires (Type, Propriété)
# -------------------------------------------------
def extract_pairs(schema):
    """
    Transforme un schéma en set de paires (item_type, prop).
    Formats acceptés :
      - set({("Product","name"), ...})
      - list([("Product","name"), ...])
      - dict({"Product": ["name","price"], "Offer": {"price": "..."} })
      - dict({"Product": {"name": True, "price": True}})
    """
    pairs = set()
    if not schema:
        return pairs

    # set de tuples
    if isinstance(schema, set):
        for x in schema:
            if isinstance(x, tuple) and len(x) == 2:
                pairs.add((str(x[0]), str(x[1])))
        return pairs

    # liste de tuples
    if isinstance(schema, list):
        for x in schema:
            if isinstance(x, tuple) and len(x) == 2:
                pairs.add((str(x[0]), str(x[1])))
        return pairs

    # dict
    if isinstance(schema, dict):
        for item_type, props in schema.items():
            if props is None:
                continue
            if isinstance(props, dict):
                iterable = props.keys()
            elif isinstance(props, (list, set, tuple)):
                iterable = props
            else:
                iterable = [props]
            for p in iterable:
                if p is None:
                    continue
                pairs.add((str(item_type), str(p)))
        return pairs

    # Autres formats : ignorés
    return pairs

# -------------------------------------------------
# 🧱 Sécurisation des entrées
# -------------------------------------------------
client_schema = client_schema if 'client_schema' in globals() else None
competitor_schemas = competitor_schemas if 'competitor_schemas' in globals() else []
competitor_names = competitor_names if 'competitor_names' in globals() else []

# Normalisation des noms concurrents
safe_competitor_names = []
for i, name in enumerate(competitor_names or []):
    nm = name or f"Concurrent {i+1}"
    if nm in safe_competitor_names:
        nm = f"{nm} ({i+1})"
    safe_competitor_names.append(nm)

# Complète si moins de noms que de schémas
while len(safe_competitor_names) < len(competitor_schemas):
    safe_competitor_names.append(f"Concurrent {len(safe_competitor_names)+1}")

# -------------------------------------------------
# 🧮 Construction des paires et de all_keys
# -------------------------------------------------
client_pairs = extract_pairs(client_schema)
competitor_pairs_list = [extract_pairs(s) for s in competitor_schemas]

all_keys = set(client_pairs)
for s in competitor_pairs_list:
    all_keys |= s

# -------------------------------------------------
# 📋 Construction du DataFrame
# -------------------------------------------------
rows = []
missing_opportunities = []

for item_type, prop in sorted(all_keys):
    row = {
        "Type": item_type,
        "Propriété": prop,
        "Votre site": "✅" if (item_type, prop) in client_pairs else "❌"
    }
    at_least_one_has_it = False

    for i, schema_pairs in enumerate(competitor_pairs_list):
        has_it = "✅" if (item_type, prop) in schema_pairs else "❌"
        if has_it == "✅":
            at_least_one_has_it = True
        row[safe_competitor_names[i]] = has_it

    if row["Votre site"] == "❌" and at_least_one_has_it:
        missing_opportunities.append((item_type, prop))

    rows.append(row)

expected_cols = ["Type", "Propriété", "Votre site"] + safe_competitor_names
df = pd.DataFrame(rows)

# Ajoute colonnes manquantes si besoin
for c in expected_cols:
    if c not in df.columns:
        df[c] = ""

# Réordonne
df = df[expected_cols]

# -------------------------------------------------
# 🎨 Fonction de coloration
# -------------------------------------------------
def colorize(val):
    if val == "✅":
        return "color: green"
    elif val == "❌":
        return "color: red"
    return ""

# -------------------------------------------------
# 📊 Affichage Streamlit
# -------------------------------------------------
st.subheader("🧩 Données comparées par type")

if df.empty or "Type" not in df.columns:
    st.info(
        "Aucune donnée structurée JSON-LD détectée pour ces URLs. "
        "Essaie avec une **fiche produit** ou colle le **HTML** en fallback."
    )
else:
    grouped = df.groupby("Type", dropna=False)

    for t, sub in grouped:
        st.markdown(f"#### {t}")
        check_cols = ["Votre site"] + [name for name in safe_competitor_names if name in sub.columns]
        cols_to_show = ["Propriété"] + check_cols

        styled = sub[cols_to_show].style.applymap(colorize, subset=check_cols)
        st.dataframe(styled, use_container_width=True)

# -------------------------------------------------
# 💡 Opportunités manquantes
# -------------------------------------------------
if missing_opportunities:
    with st.expander("💡 Opportunités manquantes (présentes chez au moins un concurrent)"):
        opp_df = pd.DataFrame(sorted(missing_opportunities), columns=["Type", "Propriété"])
        st.dataframe(opp_df, use_container_width=True)
