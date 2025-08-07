import datetime

# Étape 3 : Générer JSON-LD à intégrer
if missing_opportunities:
    st.subheader("🛠️ Générer les données JSON-LD à intégrer")

    # Grouper les opportunités par type
    schema_to_generate = {}
    for item_type, prop in missing_opportunities:
        if item_type not in schema_to_generate:
            schema_to_generate[item_type] = {}
        if prop != '@type':
            schema_to_generate[item_type][prop] = f"Exemple_{prop}"

    # Génération du JSON-LD
    generated_jsonld = []
    for schema_type, props in schema_to_generate.items():
        block = {
            "@context": "https://schema.org",
            "@type": schema_type
        }
        block.update(props)
        generated_jsonld.append(block)

    editable_json = json.dumps(generated_jsonld, indent=2, ensure_ascii=False)
    user_json = st.text_area("✍️ JSON-LD généré automatiquement (modifiable)", value=editable_json, height=300)

    # Export .json
    st.download_button(
        label="📥 Télécharger le JSON-LD",
        data=user_json,
        file_name=f"donnees-structurees-a-ajouter-{datetime.date.today()}.json",
        mime="application/json"
    )

    st.markdown("👉 Ce code peut être intégré dans une balise `<script type=\"application/ld+json\">` sur votre page.")

else:
    st.info("Aucune donnée manquante à générer pour le moment.")
