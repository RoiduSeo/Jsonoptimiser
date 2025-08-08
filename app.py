# ========================
#  ⚙️ Normalisation & Tableau comparatif JSON-LD
# ========================
import pandas as pd
import streamlit as st

# -------------------------------------------------
# 🔧 Normalisation des schémas en paires (type, prop)
# -------------------------------------------------
def extract_pairs(schema):
    """
    Convertit un schéma en set de paires (item_type, prop).
    Formats acceptés :
      - set({("Product","name"), ...})
      - list([("Product","name"), ...])
      - dict({"Product": ["name","price"], "Offer": {"price": "..."} })
      - dict({"Product": {"name": True, "price": True}}) -> prend les clés
      - "brut" (str/None) -> ignoré
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

    # dict : {type: props}
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

    # autre: on ignore
    return pairs

# -------------------------------------------------
# 🧱 Entrées amont (sécurisation)
# -------------------------------------------------
client_schema = client_schema if 'client_schema' in globals() else None
competitor_schemas = competitor_schemas if 'competitor_schemas' in globals() else []
competitor_names = competitor_names if 'competitor_names' in globals() else []

# Noms concurrents sûrs & uniques (préserve l'ordre)
seen = set()
safe_competitor_names = []
for i, name in enumerate(competitor_names or []):
    nm = name or f"Concurrent {i+1}"
    if nm in seen:
        nm = f"{nm} ({i+1})"
    seen.add(nm)
    safe_competitor_names.append(nm)

# Si moins de noms que de schémas
if len(safe_competitor_names) < len(competitor_schemas):
    for i in range(len(safe_competitor_names), len(competitor_schemas)):
        safe_competitor_names.append(f"Concurrent {i+1}")

# -------------------------------------------------
# 🧮 Construction de all_keys
# -------------------------------------------------
client_pairs = extract_pairs(client_schema)
competitor_pairs_list = [extract_pairs(s) for s in (competitor_schemas or [])]

all_keys = set(client_pairs)
for s in competitor_pairs_list:
    all_keys |= s

# -------------------------------------------------
# 🧩 Construction du DataFrame (robuste)
# -------------------------------------------------
rows = []
missing_opportunities = []

if all_keys:
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
            name = safe_competitor_names[i]
            row[name] = has_it

        if row["Votre site"] == "❌" and at_least_one_has_it:
            missing_opport_
