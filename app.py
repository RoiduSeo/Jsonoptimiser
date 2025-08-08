# ------------------------
# Construction du tableau (robuste)
# ------------------------
rows = []
missing_opportunities = []

for item_type, prop in sorted(all_keys):
    row = {
        "Type": item_type,
        "Propriété": prop,
        "Votre site": "✅" if (item_type, prop) in client_schema else "❌"
    }
    at_least_one_has_it = False

    for i, schema in enumerate(competitor_schemas):
        has_it = "✅" if (item_type, prop) in schema else "❌"
        if has_it == "✅":
            at_least_one_has_it = True
        # Sécurise l'accès au nom (si aucun concurrent saisi)
        name = competitor_names[i] if i < len(competitor_names) else f"Concurrent {i+1}"
        row[name] = has_it

    if row["Votre site"] == "❌" and at_least_one_has_it:
        missing_opportunities.append((item_type, prop))

    rows.append(row)

# on force les colonnes attendues (même si rows est vide)
expected_cols = ["Type", "Propriété", "Votre site"] + competitor_names
df = pd.DataFrame(rows)
for c in expected_cols:
    if c not in df.columns:
        df[c] = []

# ------------------------
# 📊 TABLEAU COMPARATIF PAR TYPE (sécurisé)
# ------------------------
st.subheader("🧩 Données comparées par type")

if df.empty or "Type" not in df.columns:
    st.info("Aucune donnée structurée JSON-LD détectée pour ces URLs. "
            "Essaie avec une **fiche produit** ou colle le **HTML** en fallback.")
else:
    # on ordonne les colonnes pour l'affichage
    df = df[expected_cols]

    grouped = df.groupby("Type", dropna=False)

    def colorize(val):
        return "color: green" if val == "✅" else "color: r
