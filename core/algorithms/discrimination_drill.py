from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any

from ai.client import generate_text
from ai.settings import load_ai_settings
from core.repositories.database import connection


@dataclass(frozen=True)
class DiscriminationDrill:
    id: str
    concept_a: str
    concept_b: str
    prompt_clue: str
    correct_choice: str  # "A" or "B"
    pivot_explanation: str
    sistema: str
    tags: list[str]


# Pre-seeded classic USMLE Step 1/Step 2 CK High-Yield Discriminators
PRESEEDED_PAIRED_DRILLS: list[dict[str, Any]] = [
    {
        "concept_a": "Pre-Renal Azotemia",
        "concept_b": "Acute Tubular Necrosis (ATN)",
        "prompt_clue": "Fractional excretion of sodium (FeNa) < 1%, Urine Osmolality > 500 mOsm/kg, and BUN/Cr ratio > 20:1.",
        "correct_choice": "A",
        "pivot_explanation": "Pre-renal AKI features intact tubular epithelium retaining avid sodium and water reabsorption capacity.",
        "sistema": "Renal",
        "tags": ["Renal", "FeNa", "AKI"],
    },
    {
        "concept_a": "Pre-Renal Azotemia",
        "concept_b": "Acute Tubular Necrosis (ATN)",
        "prompt_clue": "Granular 'muddy brown' epithelial casts in urinalysis with FeNa > 2% and Urine Osmolality < 350 mOsm/kg.",
        "correct_choice": "B",
        "pivot_explanation": "Muddy brown casts represent sloughed tubular epithelial cells characteristic of ischemic or toxic ATN.",
        "sistema": "Renal",
        "tags": ["Renal", "ATN", "Casts"],
    },
    {
        "concept_a": "Crohn Disease",
        "concept_b": "Ulcerative Colitis",
        "prompt_clue": "Transmural inflammation, skip lesions, cobblestone mucosa, and noncaseating granulomas.",
        "correct_choice": "A",
        "pivot_explanation": "Crohn disease causes transmural skip lesions anywhere from mouth to anus, whereas UC is continuous and mucosal.",
        "sistema": "Gastroenterology",
        "tags": ["GI", "IBD", "Crohn"],
    },
    {
        "concept_a": "Crohn Disease",
        "concept_b": "Ulcerative Colitis",
        "prompt_clue": "Continuous mucosal inflammation starting in the rectum with crypt abscesses and pseudopolyps; marked lead-pipe appearance.",
        "correct_choice": "B",
        "pivot_explanation": "Ulcerative colitis consistently involves the rectum and extends proximally in a continuous mucosal pattern.",
        "sistema": "Gastroenterology",
        "tags": ["GI", "IBD", "UC"],
    },
    {
        "concept_a": "Thrombotic Thrombocytopenic Purpura (TTP)",
        "concept_b": "Hemolytic Uremic Syndrome (HUS)",
        "prompt_clue": "Adult female presenting with fever, severe thrombocytopenia, microangiopathic hemolytic anemia, and fluctuating neurological symptoms.",
        "correct_choice": "A",
        "pivot_explanation": "TTP is caused by ADAMTS13 deficiency with prominent neurological symptoms in adults (the classic pentad).",
        "sistema": "Hematology",
        "tags": ["Heme", "TTP", "ADAMTS13"],
    },
    {
        "concept_a": "Thrombotic Thrombocytopenic Purpura (TTP)",
        "concept_b": "Hemolytic Uremic Syndrome (HUS)",
        "prompt_clue": "Child presenting with bloody diarrhea prodrome followed by acute oliguric renal failure, thrombocytopenia, and schistocytes.",
        "correct_choice": "B",
        "pivot_explanation": "HUS typically follows Shiga-toxin producing E. coli (O157:H7) in children with dominant renal endothelial injury.",
        "sistema": "Hematology",
        "tags": ["Heme", "HUS", "ShigaToxin"],
    },
    {
        "concept_a": "Cardiac Tamponade",
        "concept_b": "Constrictive Pericarditis",
        "prompt_clue": "Elevated JVP with absent y-descent, Pulsus Paradoxus > 10 mmHg, and electrical alternans on ECG without Kussmaul sign.",
        "correct_choice": "A",
        "pivot_explanation": "Tamponade impairs ventricular filling throughout diastole (absent y-descent) and presents with pulsus paradoxus.",
        "sistema": "Cardiovascular",
        "tags": ["Cardio", "Tamponade", "Pericardium"],
    },
    {
        "concept_a": "Cardiac Tamponade",
        "concept_b": "Constrictive Pericarditis",
        "prompt_clue": "Positive Kussmaul sign (JVP increases on inspiration), prominent y-descent, and early diastolic pericardial knock.",
        "correct_choice": "B",
        "pivot_explanation": "Constrictive pericarditis features a rigid pericardium halting rapid early filling (pericardial knock) and Kussmaul sign.",
        "sistema": "Cardiovascular",
        "tags": ["Cardio", "ConstrictivePericarditis"],
    },
    {
        "concept_a": "Pemphigus Vulgaris",
        "concept_b": "Bullous Pemphigoid",
        "prompt_clue": "Flaccid intraepidermal blisters, painful oral mucosal erosions, and positive Nikolsky sign.",
        "correct_choice": "A",
        "pivot_explanation": "Pemphigus vulgaris involves anti-desmoglein 1/3 antibodies causing intraepidermal acantholysis and flaccid blisters.",
        "sistema": "Dermatology",
        "tags": ["Derm", "Pemphigus", "Nikolsky"],
    },
    {
        "concept_a": "Pemphigus Vulgaris",
        "concept_b": "Bullous Pemphigoid",
        "prompt_clue": "Tense subepidermal bullae with negative Nikolsky sign and linear IgG deposition along the basement membrane.",
        "correct_choice": "B",
        "pivot_explanation": "Bullous pemphigoid involves anti-hemidesmosome (BP180/BP230) antibodies creating tense subepidermal blisters.",
        "sistema": "Dermatology",
        "tags": ["Derm", "BullousPemphigoid"],
    },
    {
        "concept_a": "Goodpasture Syndrome",
        "concept_b": "Granulomatosis with Polyangiitis (GPA)",
        "prompt_clue": "Hemoptysis and glomerulonephritis with linear IgG deposition along the glomerular basement membrane (anti-GBM).",
        "correct_choice": "A",
        "pivot_explanation": "Goodpasture syndrome is characterized by anti-alpha3 chain of type IV collagen with smooth linear immunofluorescence.",
        "sistema": "Pulmonology",
        "tags": ["Pulm", "Renal", "AntiGBM"],
    },
    {
        "concept_a": "Goodpasture Syndrome",
        "concept_b": "Granulomatosis with Polyangiitis (GPA)",
        "prompt_clue": "Sinusitis, saddle-nose deformity, cavitary pulmonary nodules, and positive c-ANCA (anti-PR3) with pauci-immune crescentic GN.",
        "correct_choice": "B",
        "pivot_explanation": "GPA involves necrotizing granulomatous vasculitis with upper airway involvement and c-ANCA/PR3 positivity.",
        "sistema": "Pulmonology",
        "tags": ["Pulm", "Vasculitis", "cANCA"],
    },
    {
        "concept_a": "Niemann-Pick Disease",
        "concept_b": "Tay-Sachs Disease",
        "prompt_clue": "Infant with neurodegeneration, cherry-red macular spot, and prominent hepatosplenomegaly with foam cells (sphingomyelinase deficiency).",
        "correct_choice": "A",
        "pivot_explanation": "Niemann-Pick presents with hepatosplenomegaly (sphingomyelin accumulation), whereas Tay-Sachs characteristically lacks hepatosplenomegaly (hexosaminidase A deficiency).",
        "sistema": "General_Principles",
        "tags": ["Biochemistry", "LysosomalStorage", "NiemannPick"],
    },
    {
        "concept_a": "Niemann-Pick Disease",
        "concept_b": "Tay-Sachs Disease",
        "prompt_clue": "Infant with progressive neurodegeneration, hyperreflexia, cherry-red macular spot, and NO hepatosplenomegaly with lysosomes with onion skinning.",
        "correct_choice": "B",
        "pivot_explanation": "Tay-Sachs features hexosaminidase A deficiency with GM2 ganglioside accumulation, exhibiting cherry-red macula without organomegaly.",
        "sistema": "General_Principles",
        "tags": ["Biochemistry", "LysosomalStorage", "TaySachs"],
    },
    {
        "concept_a": "Central Diabetes Insipidus",
        "concept_b": "Nephrogenic Diabetes Insipidus",
        "prompt_clue": "Hypernatremia and dilute polyuria with >50% increase in urine osmolality following administration of desmopressin (dDAVP).",
        "correct_choice": "A",
        "pivot_explanation": "Central DI is caused by hypothalamic/pituitary ADH deficiency; renal V2 receptors remain responsive to exogenous dDAVP.",
        "sistema": "Endocrine",
        "tags": ["Endocrine", "DiabetesInsipidus", "dDAVP"],
    },
    {
        "concept_a": "Central Diabetes Insipidus",
        "concept_b": "Nephrogenic Diabetes Insipidus",
        "prompt_clue": "Severe polyuria and polydipsia in a bipolar patient on Lithium with minimal to no change in urine osmolality after exogenous dDAVP.",
        "correct_choice": "B",
        "pivot_explanation": "Lithium-induced nephrogenic DI impairs renal collecting duct responsiveness to ADH; administration of dDAVP yields no significant concentrated urine output.",
        "sistema": "Endocrine",
        "tags": ["Endocrine", "NephrogenicDI", "Lithium"],
    },
    {
        "concept_a": "Polymyositis",
        "concept_b": "Polymyalgia Rheumatica (PMR)",
        "prompt_clue": "Progressive, symmetric proximal muscle weakness (difficulty climbing stairs/combing hair) with markedly elevated serum Creatine Kinase (CK) and anti-Jo-1.",
        "correct_choice": "A",
        "pivot_explanation": "Polymyositis is an inflammatory myopathy featuring true motor weakness and CD8+ endomysial inflammation with elevated CK.",
        "sistema": "Musculoskeletal",
        "tags": ["Rheumatology", "Polymyositis", "CK"],
    },
    {
        "concept_a": "Polymyositis",
        "concept_b": "Polymyalgia Rheumatica (PMR)",
        "prompt_clue": "Elderly patient with severe morning stiffness and aching in the shoulders and hips, normal muscle strength, elevated ESR/CRP, and normal Creatine Kinase.",
        "correct_choice": "B",
        "pivot_explanation": "PMR involves joint/synovial aching rather than true muscle necrosis; CK is normal, and it responds dramatically to low-dose prednisone.",
        "sistema": "Musculoskeletal",
        "tags": ["Rheumatology", "PMR", "GiantCellArteritis"],
    },
    {
        "concept_a": "Vitamin B12 (Cobalamin) Deficiency",
        "concept_b": "Folate (Vitamin B9) Deficiency",
        "prompt_clue": "Megaloblastic macrocytic anemia with hypersegmented neutrophils, elevated Methylmalonic Acid (MMA), elevated Homocysteine, and subacute combined degeneration.",
        "correct_choice": "A",
        "pivot_explanation": "Vitamin B12 is a cofactor for methylmalonyl-CoA mutase; its deficiency causes elevated MMA and posterior/lateral spinal cord demyelination.",
        "sistema": "Hematology",
        "tags": ["Hematology", "B12", "Neuropathy"],
    },
    {
        "concept_a": "Vitamin B12 (Cobalamin) Deficiency",
        "concept_b": "Folate (Vitamin B9) Deficiency",
        "prompt_clue": "Alcoholic patient with macrocytic anemia, hypersegmented neutrophils, elevated Homocysteine, normal Methylmalonic Acid (MMA), and no neurological symptoms.",
        "correct_choice": "B",
        "pivot_explanation": "Folate deficiency causes elevated homocysteine with normal MMA levels, with absence of neurological deficits.",
        "sistema": "Hematology",
        "tags": ["Hematology", "Folate", "MMA"],
    },
    {
        "concept_a": "Multiple Endocrine Neoplasia 1 (MEN 1)",
        "concept_b": "Multiple Endocrine Neoplasia 2A (MEN 2A)",
        "prompt_clue": "Autosomal dominant MEN1 tumor suppressor mutation presenting with Pituitary adenoma, Parathyroid hyperplasia, and Pancreatic neuroendocrine tumor (Zollinger-Ellison/Insulinoma).",
        "correct_choice": "A",
        "pivot_explanation": "MEN1 (3 Ps: Pituitary, Parathyroid, Pancreas) is caused by menin gene inactivation on chromosome 11.",
        "sistema": "Endocrine",
        "tags": ["Endocrine", "MEN1", "Menin"],
    },
    {
        "concept_a": "Multiple Endocrine Neoplasia 1 (MEN 1)",
        "concept_b": "Multiple Endocrine Neoplasia 2A (MEN 2A)",
        "prompt_clue": "Autosomal dominant RET proto-oncogene mutation presenting with Medullary Thyroid Carcinoma (calcitonin), Pheochromocytoma, and Parathyroid hyperplasia.",
        "correct_choice": "B",
        "pivot_explanation": "MEN 2A features 2 Ps (Parathyroid, Pheochromocytoma) plus Medullary Thyroid Carcinoma, driven by gain-of-function RET mutations.",
        "sistema": "Endocrine",
        "tags": ["Endocrine", "MEN2A", "RET"],
    },
    {
        "concept_a": "Myasthenia Gravis",
        "concept_b": "Lambert-Eaton Myasthenic Syndrome (LEMS)",
        "prompt_clue": "Fluctuating ptosis, diplopia, and proximal weakness that worsens progressively with repetitive muscle use; associated with thymoma or thymic hyperplasia.",
        "correct_choice": "A",
        "pivot_explanation": "Myasthenia gravis features autoantibodies against postsynaptic nicotinic ACh receptors (AChR-Ab), causing decremental response with use.",
        "sistema": "Neurology",
        "tags": ["Neuro", "MyastheniaGravis", "Thymoma"],
    },
    {
        "concept_a": "Myasthenia Gravis",
        "concept_b": "Lambert-Eaton Myasthenic Syndrome (LEMS)",
        "prompt_clue": "Proximal muscle weakness and hyporeflexia that IMPROVES with repetitive muscle contraction, dry mouth, and associated Small Cell Lung Cancer (SCLC).",
        "correct_choice": "B",
        "pivot_explanation": "LEMS is a paraneoplastic syndrome with autoantibodies against presynaptic voltage-gated calcium channels (P/Q-type VGCC), showing incremental EMG response.",
        "sistema": "Neurology",
        "tags": ["Neuro", "LEMS", "VGCC"],
    },
    {
        "concept_a": "Primary Biliary Cholangitis (PBC)",
        "concept_b": "Primary Sclerosing Cholangitis (PSC)",
        "prompt_clue": "Middle-aged female with pruritus, fatigue, jaundice, elevated alkaline phosphatase, and positive Anti-Mitochondrial Antibodies (AMA).",
        "correct_choice": "A",
        "pivot_explanation": "PBC is an autoimmune granulomatous destruction of intrahepatic interlobular bile ducts predominantly in women (AMA+).",
        "sistema": "Gastroenterology",
        "tags": ["GI", "PBC", "AMA"],
    },
    {
        "concept_a": "Primary Biliary Cholangitis (PBC)",
        "concept_b": "Primary Sclerosing Cholangitis (PSC)",
        "prompt_clue": "Young man with Ulcerative Colitis presenting with jaundice, positive p-ANCA, and MRCP showing 'beading' (multifocal strictures and dilations) of bile ducts with concentric 'onion-skin' fibrosis.",
        "correct_choice": "B",
        "pivot_explanation": "PSC features progressive obliterative periductal fibrosis affecting both intra- and extrahepatic bile ducts, strongly associated with IBD (p-ANCA+).",
        "sistema": "Gastroenterology",
        "tags": ["GI", "PSC", "pANCA"],
    },
    {
        "concept_a": "Epidural Hematoma",
        "concept_b": "Subdural Hematoma",
        "prompt_clue": "Temporal bone fracture (pterion) with middle meningeal artery laceration, classic 'lucid interval', and CT showing biconvex hyperdense collection limited by cranial sutures.",
        "correct_choice": "A",
        "pivot_explanation": "Epidural hematomas are arterial bleeds confined between skull and dura, creating lens-shaped (biconvex) collections that do not cross suture lines.",
        "sistema": "Neurology",
        "tags": ["Neuro", "EpiduralHematoma", "MiddleMeningeal"],
    },
    {
        "concept_a": "Epidural Hematoma",
        "concept_b": "Subdural Hematoma",
        "prompt_clue": "Elderly patient with brain atrophy or shaken infant with bridging vein rupture, showing crescent-shaped concave hyperdensity that CROSSES cranial sutures.",
        "correct_choice": "B",
        "pivot_explanation": "Subdural hematomas result from venous tearing of bridging cortical veins, spreading diffusely along the subdural space and crossing sutures.",
        "sistema": "Neurology",
        "tags": ["Neuro", "SubduralHematoma", "BridgingVeins"],
    },
    {
        "concept_a": "Carbon Monoxide (CO) Poisoning",
        "concept_b": "Methemoglobinemia",
        "prompt_clue": "Smoke inhalation victim with headache, cherry-red skin, normal PaO2 on ABG, falsely normal pulse oximetry, and elevated carboxyhemoglobin treated with 100% O2.",
        "correct_choice": "A",
        "pivot_explanation": "CO has 240x higher affinity for hemoglobin, causing a left-shift in the oxygen dissociation curve without altering dissolved PaO2.",
        "sistema": "Public_Health_Sciences",
        "tags": ["Toxicology", "CarbonMonoxide", "Carboxyhemoglobin"],
    },
    {
        "concept_a": "Carbon Monoxide (CO) Poisoning",
        "concept_b": "Methemoglobinemia",
        "prompt_clue": "Patient receiving topical benzocaine or dapsone presenting with refractory cyanosis, chocolate-brown blood, normal PaO2, and iron oxidized to Fe3+ treated with Methylene Blue.",
        "correct_choice": "B",
        "pivot_explanation": "Methemoglobinemia occurs when heme iron is oxidized to Fe3+ (ferric state), impairing O2 release to tissues; treated with methylene blue or ascorbic acid.",
        "sistema": "Public_Health_Sciences",
        "tags": ["Toxicology", "Methemoglobinemia", "MethyleneBlue"],
    },
    {
        "concept_a": "Confounding Bias",
        "concept_b": "Effect Modification",
        "prompt_clue": "An apparent association between exposure and disease completely disappears or becomes statistically non-significant when data is stratified by a third variable.",
        "correct_choice": "A",
        "pivot_explanation": "Confounding is an extraneous variable related to both exposure and outcome; stratification makes the association uniform and null across all strata.",
        "sistema": "Public_Health_Sciences",
        "tags": ["Biostatistics", "Confounding", "Stratification"],
    },
    {
        "concept_a": "Confounding Bias",
        "concept_b": "Effect Modification",
        "prompt_clue": "Stratified analysis reveals that the strength of association between exposure and disease is significantly different across subgroups (e.g., strong in smokers, absent in non-smokers).",
        "correct_choice": "B",
        "pivot_explanation": "Effect modification is a true biological interaction where the effect estimate differs across strata; it is not a bias and should be reported, not controlled.",
        "sistema": "Public_Health_Sciences",
        "tags": ["Biostatistics", "EffectModification", "Interaction"],
    },
    {
        "concept_a": "Lead-Time Bias",
        "concept_b": "Length-Time Bias",
        "prompt_clue": "A new screening test detects disease earlier in its clinical course, creating the illusion of prolonged survival time without actually improving overall clinical mortality.",
        "correct_choice": "A",
        "pivot_explanation": "Lead-time bias artificially inflates survival time because the zero point of diagnosis moved earlier, while the natural history of death remains unchanged.",
        "sistema": "Public_Health_Sciences",
        "tags": ["Biostatistics", "LeadTimeBias", "Screening"],
    },
    {
        "concept_a": "Orotic Aciduria",
        "concept_b": "Ornithine Transcarbamylase (OTC) Deficiency",
        "prompt_clue": "Infant with failure to thrive, megaloblastic anemia refractory to B12 and folate, orotic acid crystalluria, and NORMAL serum ammonia levels.",
        "correct_choice": "A",
        "pivot_explanation": "Orotic aciduria (UMP synthase defect) causes orotic acid accumulation without hyperammonemia, treated with oral uridine supplementation.",
        "sistema": "General_Principles",
        "tags": ["Biochemistry", "OroticAciduria", "UMPSynthase"],
    },
    {
        "concept_a": "Orotic Aciduria",
        "concept_b": "Ornithine Transcarbamylase (OTC) Deficiency",
        "prompt_clue": "X-linked urea cycle defect in a neonate presenting with severe hyperammonemia, lethargy, encephalopathy, and high urinary orotic acid with decreased BUN.",
        "correct_choice": "B",
        "pivot_explanation": "OTC deficiency shifts excess carbamoyl phosphate into pyrimidine synthesis, causing massive hyperammonemia alongside urinary orotic acid.",
        "sistema": "General_Principles",
        "tags": ["Biochemistry", "OTCDeficiency", "Hyperammonemia"],
    }
]


class DiscriminationDrillService:
    def __init__(self, db_path=None):
        import config
        self.db_path = db_path or config.DB_PATH

    def get_registered_confusion_pairs(self) -> list[tuple[str, str]]:
        try:
            with connection(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT tag_correct, tag_confused, count FROM confusions ORDER BY count DESC LIMIT 10"
                ).fetchall()
                return [(r["tag_correct"], r["tag_confused"]) for r in rows if r["tag_correct"] and r["tag_confused"]]
        except Exception:
            return []

    def get_drills(self, limit: int = 10, sistema: str | None = None) -> list[DiscriminationDrill]:
        candidates = list(PRESEEDED_PAIRED_DRILLS)
        if sistema and sistema != "Todos":
            candidates = [d for d in candidates if d.get("sistema") == sistema] or candidates

        random.shuffle(candidates)
        selected = candidates[:limit]

        drills = []
        for idx, item in enumerate(selected):
            # Randomize whether concept_a is option A or B to avoid positional bias
            swap = random.choice([True, False])
            if swap:
                a_name = item["concept_b"]
                b_name = item["concept_a"]
                correct = "A" if item["correct_choice"] == "B" else "B"
            else:
                a_name = item["concept_a"]
                b_name = item["concept_b"]
                correct = item["correct_choice"]

            drill = DiscriminationDrill(
                id=f"drill_{idx}_{random.randint(1000, 9999)}",
                concept_a=a_name,
                concept_b=b_name,
                prompt_clue=item["prompt_clue"],
                correct_choice=correct,
                pivot_explanation=item["pivot_explanation"],
                sistema=item.get("sistema", "General_Principles"),
                tags=item.get("tags", []),
            )
            drills.append(drill)
        return drills

    def generate_ai_drill_for_confusion(self, correct_tag: str, confused_tag: str) -> DiscriminationDrill | None:
        prompt = f"""
You are an elite USMLE diagnostician creating a High-Speed Paired Discrimination Drill.
The student frequently confuses {correct_tag} with {confused_tag}.

TASK:
Write a 1-sentence prompt clue describing a high-yield clinical finding, lab value, or pathognomonic feature that definitively points to ONE of these two conditions.
Provide the pivot explanation explaining why this specific feature distinguishes the two.

FORMAT (JSON only):
{{
    "concept_a": "{correct_tag}",
    "concept_b": "{confused_tag}",
    "prompt_clue": "High-yield clue text in English",
    "correct_choice": "A",
    "pivot_explanation": "1-2 sentence concise clinical distinction in English."
}}
"""
        try:
            raw = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True, use_cache=True)
            data = json.loads(raw)
            return DiscriminationDrill(
                id=f"ai_drill_{random.randint(1000, 9999)}",
                concept_a=data.get("concept_a", correct_tag),
                concept_b=data.get("concept_b", confused_tag),
                prompt_clue=data.get("prompt_clue", ""),
                correct_choice=data.get("correct_choice", "A"),
                pivot_explanation=data.get("pivot_explanation", ""),
                sistema="General_Principles",
                tags=[correct_tag, confused_tag],
            )
        except Exception:
            return None
