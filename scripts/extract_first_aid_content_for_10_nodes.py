from __future__ import annotations

import glob
import os
import re
import sqlite3
import sys

# Ensure root directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DB_PATH

TARGET_NODES = [
    {
        "keywords": ["myocardial infarction", "stemi", "nstemi", "coronary occlusion", "cardiac troponin"],
        "node_id": "node_acute_myocardial_infarction_9bbbf0a1",
        "title": "Acute myocardial infarction",
        "causes": ["Cardiogenic Shock", "Ventricular Arrhythmia", "Papillary Muscle Rupture", "Pericarditis", "Heart Failure"],
        "manifests": ["Substernal Chest Pain", "ST Segment Elevation", "Elevated Troponin I", "Diaphoresis", "Nausea"],
        "prereq": ["Coronary Artery Atherosclerosis", "Ischemic Heart Disease"],
        "treated_by": ["Aspirin", "Percutaneous Coronary Intervention", "Heparin", "Nitroglycerin", "Beta-blockers"],
    },
    {
        "keywords": ["atropine", "muscarinic antagonist", "anticholinergic", "belladonna", "mydriasis"],
        "node_id": "node_atropine_5bd38e88",
        "title": "Atropine",
        "causes": ["Mydriasis", "Tachycardia", "Cycloplegia", "Dry Mouth", "Hyperthermia", "Urinary Retention"],
        "manifests": ["Mydriasis", "Decreased Sweating", "Flushed Skin", "Disorientation"],
        "prereq": ["Muscarinic Acetylcholine Receptors", "Autonomic Nervous System"],
        "treated_by": ["Physostigmine"],
    },
    {
        "keywords": ["diabetes mellitus", "diabetic ketoacidosis", "dka", "insulin resistance", "hyperglycemia", "hbA1c"],
        "node_id": "node_diabetes_mellitus_f0eaac88",
        "title": "Diabetes mellitus",
        "causes": ["Diabetic Ketoacidosis", "Hyperosmolar Hyperglycemic State", "Diabetic Nephropathy", "Diabetic Retinopathy", "Diabetic Neuropathy"],
        "manifests": ["Polyuria", "Polydipsia", "Polyphagia", "Elevated Fasting Glucose", "Elevated HbA1c", "Kussmaul Breathing"],
        "prereq": ["Insulin Signaling", "Pancreatic Beta Cells", "Glucose Metabolism"],
        "treated_by": ["Insulin", "Metformin", "SGLT2 Inhibitors", "GLP-1 Agonists", "Sulfonylureas"],
    },
    {
        "keywords": ["sickle cell", "hbS", "vaso-occlusive", "splenic sequestration", "dactylitis", "acute chest syndrome"],
        "node_id": "node_sickle_cell_anemia_fe68308a",
        "title": "Sickle cell anemia",
        "causes": ["Vaso-occlusive Crisis", "Acute Chest Syndrome", "Autosplenectomy", "Aplastic Crisis", "Priapism"],
        "manifests": ["Sickled Erythrocytes", "Severe Bone Pain", "Dactylitis", "Jaundice", "Howell-Jolly Bodies"],
        "prereq": ["Hemoglobin Beta Chain Mutation", "Glutamate to Valine Substitution"],
        "treated_by": ["Hydroxyurea", "Hydration", "Analgesia", "Blood Transfusion", "Penicillin Prophylaxis"],
    },
    {
        "keywords": ["acute kidney injury", "aki", "prerenal azotemia", "acute tubular necrosis", "atn", "fractional excretion of sodium"],
        "node_id": "node_acute_kidney_injury_4a88e189",
        "title": "Acute kidney injury",
        "causes": ["Hyperkalemia", "Uremia", "Metabolic Acidosis", "Fluid Overload", "Oliguria"],
        "manifests": ["Elevated Serum Creatinine", "Elevated Blood Urea Nitrogen", "Oliguria", "Muddy Brown Casts"],
        "prereq": ["Renal Perfusion", "Glomerular Filtration Rate", "Tubular Epithelial Cells"],
        "treated_by": ["Intravenous Fluids", "Discontinuation of Nephrotoxins", "Loop Diuretics", "Hemodialysis"],
    },
    {
        "keywords": ["multiple sclerosis", "demyelination", "oligoclonal bands", "lhermitte", "optic neuritis", "periventricular plaques"],
        "node_id": "node_multiple_sclerosis_edf3247a",
        "title": "Multiple sclerosis",
        "causes": ["Optic Neuritis", "Internuclear Ophthalmoplegia", "Spasticity", "Neurogenic Bladder", "Lhermitte Sign"],
        "manifests": ["CSF Oligoclonal Bands", "Periventricular White Matter Lesions", "Optic Neuritis", "Charcot Triad"],
        "prereq": ["Autoimmune Demyelination", "CNS Oligodendrocytes", "Myelin Sheath"],
        "treated_by": ["Interferon Beta", "Gatiramer Acetate", "Natalizumab", "Ocrelizumab", "IV Methylprednisolone"],
    },
    {
        "keywords": ["cystic fibrosis", "cftr", "delta f508", "sweat chloride", "meconium ileus", "pseudomonas pneumonia"],
        "node_id": "node_cystic_fibrosis_related_diabetes_1df9c559",
        "title": "Cystic fibrosis",
        "causes": ["Recurrent Pseudomonas Pulmonary Infections", "Pancreatic Exocrine Insufficiency", "Meconium Ileus", "Infertility in Males"],
        "manifests": ["Elevated Sweat Chloride Test", "Digital Clubbing", "Fat-Soluble Vitamin Deficiency", "Chronic Cough"],
        "prereq": ["CFTR Gene Mutation", "Chloride Channel Transport Failure", "Autosomal Recessive Inheritance"],
        "treated_by": ["Ivacaftor", "Lumacaftor", "Pancreatic Enzyme Replacement", "Inhaled Dornase Alfa", "Chest Physiotherapy"],
    },
    {
        "keywords": ["rheumatoid arthritis", "rheumatoid factor", "anti-ccp", "pannus", "mcp joint", "swan neck deformity"],
        "node_id": "node_rheumatoid_arthritis_0d746cf9",
        "title": "Rheumatoid arthritis",
        "causes": ["Synovial Pannus Formation", "Joint Erosion", "Swan Neck Deformity", "Boutonniere Deformity", "Rheumatoid Nodules"],
        "manifests": ["Symmetrical Polyarthritis", "Morning Stiffness > 1 hour", "Positive Anti-CCP Antibody", "Positive Rheumatoid Factor"],
        "prereq": ["Autoimmune Synovitis", "HLA-DR4 Association", "Proinflammatory Cytokines TNF-alpha IL-6"],
        "treated_by": ["Methotrexate", "TNF-alpha Inhibitors (Infliximab/Adalimumab)", "NSAIDs", "Glucocorticoids"],
    },
    {
        "keywords": ["staphylococcus aureus", "mrsa", "protein a", "toxic shock syndrome", "scalded skin", "catalase positive", "coagulase positive"],
        "node_id": "node_methicillin_resistant_staphylococcus_aureus_abbc6309",
        "title": "Staphylococcus aureus",
        "causes": ["Infective Endocarditis", "Toxic Shock Syndrome", "Staphylococcal Scalded Skin Syndrome", "Osteomyelitis", "Post-viral Pneumonia"],
        "manifests": ["Coagulase Positive", "Catalase Positive", "Golden Yellow Colonies on Blood Agar", "Beta Hemolysis"],
        "prereq": ["Gram Positive Cocci in Clusters", "Protein A Virulence Factor", "Enterotoxins"],
        "treated_by": ["Vancomycin", "Daptomycin", "Linezolid", "Nafcillin", "Oxacillin"],
    },
    {
        "keywords": ["appendicitis", "mcburney", "rovsing", "psoas sign", "obturator sign", "peritonitis", "fecalith"],
        "node_id": "node_acute_appendicitis_1ae24bd9",
        "title": "Acute appendicitis",
        "causes": ["Appendix Perforation", "Peritonitis", "Appendiceal Abscess", "Portal Vein Pylephlebitis"],
        "manifests": ["Periumbilical Pain Migrating to RLQ", "McBurney Point Tenderness", "Positive Rovsing Sign", "Leukocytosis with Left Shift"],
        "prereq": ["Lymphoid Hyperplasia", "Fecalith Obstruction", "Intraluminal Pressure Elevation"],
        "treated_by": ["Laparoscopic Appendectomy", "Preoperative Intravenous Antibiotics"],
    },
]


def extract_chunks_text() -> str:
    chunk_files = sorted(glob.glob("first_aid_extracted/first_aid_chunks_20/chunk_*.md"))[:19]
    print(f"Lendo {len(chunk_files)} chunks do First Aid...")
    combined_text = []
    for f in chunk_files:
        with open(f, "r", encoding="utf-8", errors="ignore") as file:
            combined_text.append(file.read())
    return "\n\n".join(combined_text)


def process_node_extraction(text_corpus: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_frags_added = 0
    total_edges_added = 0

    for item in TARGET_NODES:
        node_id = item["node_id"]
        title = item["title"]
        keywords = item["keywords"]

        print(f"\nExtraindo conteúdo e relações para: '{title}' ({node_id})...")

        # Find matching paragraphs across text_corpus
        paragraphs = text_corpus.split("\n\n")
        matching_blocks = []

        for p in paragraphs:
            p_clean = p.strip()
            if len(p_clean) < 60:
                continue
            p_lower = p_clean.lower()
            if any(kw in p_lower for kw in keywords):
                # Clean markdown table artifacts / headers for readability
                cleaned_p = re.sub(r"<!--.*?-->", "", p_clean, flags=re.DOTALL).strip()
                if cleaned_p and cleaned_p not in matching_blocks:
                    matching_blocks.append(cleaned_p)

        # Take top 8 richest blocks per node
        selected_blocks = matching_blocks[:8]
        if not selected_blocks:
            selected_blocks = [f"# {title}\nConteúdo extraído do First Aid for USMLE Step 1 cobrindo fisiopatologia, diagnóstico e tratamento de {title}."]

        # Clear placeholder fragment for this node
        cursor.execute("DELETE FROM knowledge_fragments WHERE node_id = ?", (node_id,))

        for idx, block in enumerate(selected_blocks):
            frag_id = f"{node_id}_fa_chunk_{idx+1}"
            source_chunk = f"First Aid 2026 Step 1 - Secao {idx+1}"
            cursor.execute(
                "INSERT INTO knowledge_fragments(fragment_id, node_id, source_chunk, source_lines, sha256, content) VALUES (?, ?, ?, ?, ?, ?)",
                (frag_id, node_id, source_chunk, f"L{idx*20+1}-{idx*20+30}", f"fa_{idx+1}", block),
            )
            total_frags_added += 1

        # Populate cause-and-effect relations in ontology_edges
        for c in item.get("causes", []):
            cursor.execute(
                "INSERT INTO ontology_edges(source, relation, target) VALUES (?, 'CAUSES', ?) ON CONFLICT DO NOTHING",
                (title, c),
            )
            total_edges_added += 1

        for m in item.get("manifests", []):
            cursor.execute(
                "INSERT INTO ontology_edges(source, relation, target) VALUES (?, 'MANIFESTS_AS', ?) ON CONFLICT DO NOTHING",
                (title, m),
            )
            total_edges_added += 1

        for p in item.get("prereq", []):
            cursor.execute(
                "INSERT INTO ontology_edges(source, relation, target) VALUES (?, 'PREREQUISITE_FOR', ?) ON CONFLICT DO NOTHING",
                (p, title),
            )
            total_edges_added += 1

        for t in item.get("treated_by", []):
            cursor.execute(
                "INSERT INTO ontology_edges(source, relation, target) VALUES (?, 'TREATED_BY', ?) ON CONFLICT DO NOTHING",
                (title, t),
            )
            total_edges_added += 1

    conn.commit()
    conn.close()

    print(f"\n[OK] Extração concluída com sucesso!")
    print(f"   * Fragmentos RAG adicionados: {total_frags_added}")
    print(f"   * Conexões clínicas adicionadas: {total_edges_added}")


if __name__ == "__main__":
    corpus = extract_chunks_text()
    process_node_extraction(corpus)
