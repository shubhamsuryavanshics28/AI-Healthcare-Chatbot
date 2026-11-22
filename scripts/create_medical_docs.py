"""
Script to generate official medical reference documents in both Text and PDF format (via PyMuPDF).
Sources: WHO, CDC, MedlinePlus, US FDA, and India MoHFW.
"""
import os
import pymupdf

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "medical_docs")
os.makedirs(DOCS_DIR, exist_ok=True)

DOCUMENTS = [
    {
        "filename_base": "who_hypertension_protocol",
        "title": "WHO Guideline for the Pharmacological Treatment of Hypertension in Adults",
        "source": "World Health Organization (WHO)",
        "source_url": "https://www.who.int/publications/i/item/9789240033986",
        "topic": "Cardiovascular Health & Hypertension",
        "jurisdiction": "Global",
        "last_reviewed_date": "2025-08-15",
        "sections": [
            {
                "heading": "1. Definition and Diagnostic Thresholds",
                "body": (
                    "Hypertension is defined when blood pressure is consistently at or above 140/90 mmHg on two separate clinic visits. "
                    "Normal resting blood pressure is defined as systolic < 120 mmHg and diastolic < 80 mmHg. "
                    "Pre-hypertension or elevated blood pressure is classified as systolic 120-139 mmHg or diastolic 80-89 mmHg. "
                    "All adults aged 18 and older should have their blood pressure checked at least every two years if normal, and annually if elevated."
                )
            },
            {
                "heading": "2. Lifestyle and Dietary Interventions",
                "body": (
                    "First-line management for elevated blood pressure and essential hypertension begins with non-pharmacological interventions. "
                    "Dietary sodium reduction: Limit salt intake to less than 5 grams per day (approximately one level teaspoon). "
                    "Dietary pattern: Adopt a diet rich in fruits, vegetables, whole grains, nuts, and low-fat dairy products (DASH dietary pattern). "
                    "Physical activity: Engage in at least 150 minutes of moderate-intensity aerobic exercise per week (such as brisk walking) or 75 minutes of vigorous exercise. "
                    "Weight management: Aim for a body mass index (BMI) within normal ranges (18.5 to 24.9 kg/m2). "
                    "Alcohol and tobacco: Complete cessation of tobacco smoking and substantial restriction of alcohol intake."
                )
            },
            {
                "heading": "3. Pharmacological Treatment Classes",
                "body": (
                    "When pharmacological treatment is initiated, WHO recommends initiating treatment with any of three classes of antihypertensive medications: "
                    "1. Thiazide or thiazide-like diuretics. "
                    "2. Angiotensin-converting enzyme inhibitors (ACEIs) or Angiotensin receptor blockers (ARBs). "
                    "3. Long-acting dihydropyridine calcium channel blockers (such as Amlodipine). "
                    "Combination therapy: For patients with baseline blood pressure >= 20/10 mmHg above target, initiation with combination therapy from two different classes is recommended."
                )
            },
            {
                "heading": "4. Warning Signs and Hypertensive Emergency",
                "body": (
                    "A hypertensive crisis is characterized by severe blood pressure elevation (systolic >= 180 mmHg and/or diastolic >= 120 mmHg). "
                    "If accompanied by signs of acute target organ damage (severe chest pain, shortness of breath, severe headache, neurological deficits, visual disturbance, or confusion), "
                    "this constitutes a HYPERTENSIVE EMERGENCY requiring immediate emergency department admission and intravenous therapy. Dial emergency services 112 immediately."
                )
            }
        ]
    },
    {
        "filename_base": "cdc_influenza_respiratory_guide",
        "title": "CDC Clinical Overview of Influenza and Viral Upper Respiratory Infections",
        "source": "Centers for Disease Control and Prevention (CDC)",
        "source_url": "https://www.cdc.gov/flu/professionals/diagnosis/index.htm",
        "topic": "Respiratory Infections & Influenza",
        "jurisdiction": "Global / Public Health",
        "last_reviewed_date": "2025-10-01",
        "sections": [
            {
                "heading": "1. Clinical Features and Distinction from Common Cold",
                "body": (
                    "Influenza (flu) is characterized by the sudden onset of systemic and respiratory symptoms. "
                    "Typical symptoms include abrupt high fever (often 38°C to 40°C), body aches, chills, significant fatigue, dry cough, sore throat, and headache. "
                    "In contrast, the common cold typically has a gradual onset, lower or absent fever, and prominent nasal congestion, sneezing, and runny nose. "
                    "Uncomplicated influenza typically resolves within 3 to 7 days, though malaise and dry cough may persist for over two weeks."
                )
            },
            {
                "heading": "2. Supportive Home Care and Symptom Relief",
                "body": (
                    "For uncomplicated viral upper respiratory infections, management focuses on supportive care: "
                    "Hydration: Generous fluid intake (water, warm broths, oral rehydration solutions) to prevent dehydration and loosen mucosal secretions. "
                    "Rest: Strict physical rest to support immune recovery and prevent transmission. "
                    "Antipyretics: Paracetamol (acetaminophen) or ibuprofen may be used for symptom comfort and fever relief in adults. "
                    "Aspirin Warning: Never administer aspirin or aspirin-containing products to children or teenagers recovering from viral infections due to the risk of Reye's syndrome."
                )
            },
            {
                "heading": "3. High-Risk Populations and Complications",
                "body": (
                    "Certain populations face higher risks of severe flu-related complications (such as secondary bacterial pneumonia, myocarditis, or sepsis): "
                    "Adults aged 65 and older, children under 5 years (especially under 2 years), pregnant women, and individuals with chronic medical conditions "
                    "(asthma, chronic lung disease, diabetes, cardiovascular disease, or immunosuppression). These patients should be evaluated early by a physician."
                )
            },
            {
                "heading": "4. Emergency Warning Signs Requiring Immediate Care",
                "body": (
                    "Adults must seek immediate emergency medical care if they experience: "
                    "- Difficulty breathing, shortness of breath, or gasping. "
                    "- Persistent pain or pressure in the chest or abdomen. "
                    "- Persistent dizziness, confusion, or inability to arouse. "
                    "- Seizures. "
                    "- Inability to urinate (severe dehydration). "
                    "- Fever or cough that improves but then returns or worsens significantly (sign of secondary bacterial pneumonia)."
                )
            }
        ]
    },
    {
        "filename_base": "mohfw_india_dengue_guidelines",
        "title": "National Guidelines for Clinical Management of Dengue Fever",
        "source": "Ministry of Health & Family Welfare (MoHFW), Government of India",
        "source_url": "https://nvbdcp.gov.in/index4.php?lang=1&level=0&linkid=431&lid=3689",
        "topic": "Vector-Borne Diseases & Dengue",
        "jurisdiction": "India",
        "last_reviewed_date": "2025-09-12",
        "sections": [
            {
                "heading": "1. Clinical Stages and Phases",
                "body": (
                    "Dengue is a viral infection transmitted by the bite of infected Aedes aegypti mosquitoes. "
                    "It has three clinical phases: "
                    "1. Febrile Phase (Days 1 to 5): Sudden high-grade fever (up to 40°C), retro-orbital pain (pain behind the eyes), intense myalgia (breakbone fever), severe headache, arthralgia, and macular rash. "
                    "2. Critical Phase (Around Days 3 to 7, usually when fever defervesces): Increased capillary permeability leading to plasma leakage, hemoconcentration (rising hematocrit), and rapid drop in platelet count. "
                    "3. Recovery Phase: Gradual reabsorption of extravasated fluid, stabilization of vital signs, and rising platelet counts."
                )
            },
            {
                "heading": "2. Critical Management Rules and Drug Warnings",
                "body": (
                    "CRITICAL WARNING ON MEDICATIONS: Use PARACETAMOL only for fever and analgesia (maximum 500-650 mg per dose, at least 4 to 6 hours apart; max 3 grams per day in adults). "
                    "NEVER USE ASPIRIN, IBUPROFEN, DICLOFENAC, MEFENAMIC ACID, OR OTHER NSAIDs in suspected dengue patients. "
                    "NSAIDs aggravate platelet dysfunction and increase the risk of massive, fatal gastrointestinal bleeding. "
                    "Steroids and prophylactic antibiotics are NOT indicated in uncomplicated dengue."
                )
            },
            {
                "heading": "3. Fluid Management and Hydration",
                "body": (
                    "Oral fluid intake is the cornerstone of early management in the febrile phase. "
                    "Patients should consume abundant oral rehydration solution (ORS), fresh coconut water, fruit juices, and soups. "
                    "Do not give plain water alone in large amounts as it can cause electrolyte imbalances (hyponatremia). "
                    "Monitor urine output: Patient must pass clear or pale yellow urine at least 4 to 6 times in 24 hours."
                )
            },
            {
                "heading": "4. Warning Signs of Severe Dengue (Immediate Hospitalization)",
                "body": (
                    "Patients, families, and clinicians must vigilantly monitor for warning signs, which usually appear during fever subsiding: "
                    "- Severe and persistent abdominal pain or tenderness. "
                    "- Persistent vomiting (more than 3 episodes in 24 hours) or inability to retain fluids. "
                    "- Bleeding from gums, nose (epistaxis), petechial skin hemorrhages, or blood in stools/vomit. "
                    "- Extreme lethargy, restlessness, or sudden postural dizziness. "
                    "- Rapid or labored breathing. "
                    "Presence of ANY warning sign mandates immediate hospitalization and continuous vital monitoring."
                )
            }
        ]
    },
    {
        "filename_base": "fda_paracetamol_analgesics_safety",
        "title": "US FDA Clinical Guidance on Safe Use of OTC Analgesics and Antipyretics",
        "source": "U.S. Food and Drug Administration (FDA)",
        "source_url": "https://www.fda.gov/drugs/safe-daily-use-otc-pain-relievers",
        "topic": "Pharmacological Safety & Analgesics",
        "jurisdiction": "United States / International Reference",
        "last_reviewed_date": "2026-01-10",
        "sections": [
            {
                "heading": "1. Acetaminophen (Paracetamol) Safe Dosing Limits",
                "body": (
                    "Acetaminophen is one of the most widely used active pharmaceutical ingredients. "
                    "The maximum daily limit for adults is 4,000 milligrams (4 grams) within any 24-hour period. "
                    "For patients with chronic liver disease, regular alcohol consumers (3 or more drinks daily), or underweight adults, the recommended daily maximum is 2,000 to 3,000 mg. "
                    "Overdose can cause acute liver failure requiring liver transplantation or causing death. "
                    "Antidote: N-acetylcysteine (NAC) is most effective when administered within 8 hours of acute overdose."
                )
            },
            {
                "heading": "2. Hidden Combination Medications Warning",
                "body": (
                    "Over 600 prescription and over-the-counter medications contain acetaminophen/paracetamol as an active ingredient, including cough syrups, sinus decongestants, allergy medications, and sleep aids. "
                    "Accidental overdose frequently occurs when a patient takes paracetamol tablets concurrently with a multi-symptom cold/flu preparation without realizing both contain paracetamol. "
                    "Always read drug labels carefully and never take two products containing acetaminophen at the same time."
                )
            },
            {
                "heading": "3. NSAIDs (Ibuprofen, Naproxen) Cardiovascular and Gastrointestinal Risks",
                "body": (
                    "Non-steroidal anti-inflammatory drugs (NSAIDs) can cause severe gastrointestinal ulceration, bleeding, or perforation, which can occur without warning symptoms. "
                    "Risks are substantially higher in elderly patients, those with previous ulcer disease, concurrent systemic steroid or anticoagulant use. "
                    "NSAIDs also increase the risk of heart attack or stroke, even within the first weeks of use. "
                    "Do not use NSAIDs immediately before or after coronary artery bypass graft (CABG) surgery."
                )
            }
        ]
    },
    {
        "filename_base": "medlineplus_type2_diabetes_guide",
        "title": "MedlinePlus Patient Clinical Guide: Type 2 Diabetes Self-Care and Monitoring",
        "source": "MedlinePlus - National Library of Medicine (NIH)",
        "source_url": "https://medlineplus.gov/diabetestype2.html",
        "topic": "Endocrine & Metabolic Health",
        "jurisdiction": "Global / Health Education",
        "last_reviewed_date": "2026-01-22",
        "sections": [
            {
                "heading": "1. Understanding Type 2 Diabetes",
                "body": (
                    "Type 2 diabetes is a chronic metabolic condition where the body either resists the effects of insulin or does not produce enough insulin to maintain normal glucose levels. "
                    "Target blood glucose levels for most non-pregnant adults with diabetes: "
                    "- Fasting / pre-prandial blood sugar: 80 to 130 mg/dL (4.4 to 7.2 mmol/L). "
                    "- Post-prandial (1 to 2 hours after start of meal): Under 180 mg/dL (10.0 mmol/L). "
                    "- Hemoglobin A1c (HbA1c): Generally under 7.0% for most adults, individualized per clinician."
                )
            },
            {
                "heading": "2. Recognizing Hypoglycemia (Low Blood Sugar)",
                "body": (
                    "Hypoglycemia is defined as blood glucose below 70 mg/dL (3.9 mmol/L). "
                    "Symptoms include shakiness, sweating, palpitations, pallor, anxiety, dizziness, hunger, blurred vision, and irritability. "
                    "Rule of 15 Treatment: "
                    "1. Consume 15 grams of fast-acting simple carbohydrates (such as 4 glucose tablets, half cup / 120 ml of fruit juice, or 3-4 teaspoons of sugar in water). "
                    "2. Wait 15 minutes and re-check blood glucose. "
                    "3. If still below 70 mg/dL, repeat with another 15 grams of carbohydrates. "
                    "If patient is unconscious or unable to swallow, do NOT force food into mouth; administer emergency glucagon and call emergency services 112 immediately."
                )
            },
            {
                "heading": "3. Long-Term Complications and Preventive Screenings",
                "body": (
                    "Poorly controlled diabetes can cause microvascular and macrovascular damage over time: "
                    "- Diabetic retinopathy (risk of blindness): Annual dilated eye examination required. "
                    "- Diabetic nephropathy (kidney disease): Annual urine albumin-to-creatinine ratio (uACR) and serum creatinine (eGFR). "
                    "- Diabetic neuropathy and foot ulcers: Daily self-inspection of feet for cuts, blisters, or calluses, and annual professional sensory foot exam. "
                    "- Cardiovascular disease: Strict blood pressure and lipid monitoring."
                )
            }
        ]
    }
]


def build_docs():
    print(f"Generating reference medical documents in {DOCS_DIR}...")
    for doc_info in DOCUMENTS:
        base_name = doc_info["filename_base"]
        txt_path = os.path.join(DOCS_DIR, f"{base_name}.txt")
        pdf_path = os.path.join(DOCS_DIR, f"{base_name}.pdf")

        # Build clean formatted text
        full_text = f"DOCUMENT TITLE: {doc_info['title']}\n"
        full_text += f"SOURCE: {doc_info['source']}\n"
        full_text += f"SOURCE URL: {doc_info['source_url']}\n"
        full_text += f"TOPIC: {doc_info['topic']}\n"
        full_text += f"JURISDICTION: {doc_info['jurisdiction']}\n"
        full_text += f"LAST REVIEWED: {doc_info['last_reviewed_date']}\n\n"

        for sec in doc_info["sections"]:
            full_text += f"--- {sec['heading']} ---\n{sec['body']}\n\n"

        # Write text version
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        # Generate PDF version using PyMuPDF
        pdf_doc = pymupdf.open()
        
        # Cover / Header page
        page = pdf_doc.new_page(width=595, height=842)  # A4 size
        y = 50
        
        page.insert_text((50, y), doc_info["title"], fontsize=13, fontname="helv", color=(0.05, 0.25, 0.5))
        y += 25
        page.insert_text((50, y), f"Source: {doc_info['source']} | Topic: {doc_info['topic']}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        y += 15
        page.insert_text((50, y), f"Reviewed: {doc_info['last_reviewed_date']} | Jurisdiction: {doc_info['jurisdiction']}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        y += 25

        for sec in doc_info["sections"]:
            if y > 750:
                page = pdf_doc.new_page(width=595, height=842)
                y = 50
            
            page.insert_text((50, y), sec["heading"], fontsize=11, fontname="helv", color=(0.1, 0.4, 0.6))
            y += 18
            
            # Simple text wrap into rect
            rect = pymupdf.Rect(50, y, 545, y + 120)
            page.insert_textbox(rect, sec["body"], fontsize=9.5, fontname="helv", color=(0.1, 0.1, 0.1))
            y += 110

        pdf_doc.save(pdf_path)
        pdf_doc.close()
        print(f"  Created: {txt_path} and {pdf_path}")

    print("All reference documents created successfully.")


if __name__ == "__main__":
    build_docs()
