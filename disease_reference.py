"""
disease_reference.py
----------------------
A symptom-matching reference tool for common crop diseases — NOT an image
classifier. I looked for a real, freely-usable pretrained plant-disease
image model to bundle here (found one: a fastai-exported ResNet34 trained
on PlantVillage, from github.com/imskr/Plant_Disease_Detection). It's not
used, because fastai 1.x (which that .pkl export requires to even
unpickle) is unmaintained and doesn't install cleanly on modern Python —
shipping it would mean either a broken dependency or a feature that
silently doesn't work, which is exactly the kind of fake-functional thing
this project is trying to avoid.

Instead, this module matches farmer-described symptoms (leaf color/pattern,
spots, wilting, powdery coating, etc.) against a reference table of common
diseases per crop, sourced from standard published plant-pathology/
extension-service knowledge. The photo upload/camera capture in the UI is
real and works, but the photo is kept for the farmer's own reference only
— it is not analyzed by this module. If a real image-classification API
key is added later, that can slot in alongside this without removing it.
"""

DISEASE_REFERENCE = {
    "rice": [
        {"disease": "Blast (Magnaporthe oryzae)",
         "symptoms": ["diamond-shaped grey/white lesions with brown margins on leaves",
                      "lesions on leaf, collar, and neck"],
         "cause": "Fungal, favored by high humidity, dense planting, excess nitrogen.",
         "treatment": "Remove and destroy infected plant debris; avoid excess nitrogen; ensure field drainage.",
         "recommended_fungicide": "Tricyclazole or Isoprothiolane (follow label dose)."},
        {"disease": "Bacterial Leaf Blight",
         "symptoms": ["water-soaked streaks near leaf tip/margin turning yellow-white",
                      "wavy lesion margins"],
         "cause": "Bacterial (Xanthomonas oryzae), spreads via irrigation water and wind-driven rain.",
         "treatment": "Use disease-free seed; avoid clipping seedling leaf tips at transplanting; balanced N application.",
         "recommended_fungicide": "Copper oxychloride-based spray; streptocycline seed treatment where permitted."},
        {"disease": "Sheath Blight",
         "symptoms": ["irregular greenish-grey lesions on leaf sheath near water line",
                      "lesions with grey center and brown margin"],
         "cause": "Fungal (Rhizoctonia solani), favored by dense canopy and high humidity.",
         "treatment": "Avoid excess nitrogen and dense spacing; improve field drainage between irrigations.",
         "recommended_fungicide": "Hexaconazole or Validamycin."},
    ],
    "wheat": [
        {"disease": "Yellow (Stripe) Rust",
         "symptoms": ["yellow-orange powdery stripes running along leaf veins"],
         "cause": "Fungal, favored by cool, humid weather.",
         "treatment": "Use resistant varieties where available; monitor early in cool weather.",
         "recommended_fungicide": "Propiconazole spray at first sign of infection."},
        {"disease": "Loose Smut",
         "symptoms": ["black powdery mass replacing the grain head at heading stage"],
         "cause": "Fungal, seed-borne.",
         "treatment": "Use certified disease-free seed.",
         "recommended_fungicide": "Carboxin or Tebuconazole seed treatment before sowing."},
    ],
    "cotton": [
        {"disease": "Bacterial Blight",
         "symptoms": ["angular water-soaked spots on leaves turning brown/black",
                      "black lesions along veins ('vein blight')"],
         "cause": "Bacterial, spreads via infected seed and wind-driven rain.",
         "treatment": "Use disease-free/treated seed; remove and destroy infected plant debris.",
         "recommended_fungicide": "Copper oxychloride spray; seed treatment with Carboxin."},
        {"disease": "Boll Rot",
         "symptoms": ["dark, sunken, rotting spots on bolls, often after wet weather"],
         "cause": "Fungal/bacterial complex, favored by prolonged wet conditions and insect entry wounds.",
         "treatment": "Manage sucking-pest entry wounds; avoid waterlogging; timely picking of open bolls.",
         "recommended_fungicide": "Copper oxychloride or Carbendazim spray."},
    ],
    "potato": [
        {"disease": "Late Blight",
         "symptoms": ["water-soaked dark lesions on leaves that enlarge quickly",
                      "white fungal growth on leaf undersurface in humid weather"],
         "cause": "Fungal-like oomycete (Phytophthora infestans), spreads fast in cool, wet weather.",
         "treatment": "Improve field drainage and airflow; remove infected plants promptly; avoid overhead irrigation in cool weather.",
         "recommended_fungicide": "Mancozeb as a preventive spray; Metalaxyl + Mancozeb once infection appears."},
        {"disease": "Early Blight",
         "symptoms": ["dark brown spots with concentric rings ('target spot') on older leaves first"],
         "cause": "Fungal (Alternaria solani), favored by warm, humid weather and plant stress.",
         "treatment": "Balanced fertilization (avoid nitrogen stress); remove infected lower leaves.",
         "recommended_fungicide": "Mancozeb or Chlorothalonil spray."},
    ],
    "maize": [
        {"disease": "Common Rust",
         "symptoms": ["small reddish-brown powdery pustules on both leaf surfaces"],
         "cause": "Fungal, favored by cool, moist weather.",
         "treatment": "Usually manageable without spray in most seasons; monitor if severe.",
         "recommended_fungicide": "Mancozeb spray if severe/early in the season."},
        {"disease": "Turcicum Leaf Blight",
         "symptoms": ["long, elliptical grey-green to tan lesions on leaves"],
         "cause": "Fungal (Exserohilum turcicum), favored by moderate temperature and high humidity.",
         "treatment": "Remove crop debris after harvest; avoid dense planting.",
         "recommended_fungicide": "Mancozeb or Propiconazole spray."},
    ],
}

GENERAL_SAFETY_NOTE = (
    "This is a symptom-matching reference, not an image-based diagnosis — the photo you attach is "
    "kept for your own record, not analyzed. For a confirmed diagnosis and exact pesticide dosage, "
    "consult your local Krishi Vigyan Kendra or agricultural extension office, and always follow the "
    "product label."
)


def list_symptoms_for_crop(crop):
    crop_key = (crop or "").strip().lower()
    diseases = DISEASE_REFERENCE.get(crop_key, [])
    symptom_set = []
    for d in diseases:
        for s in d["symptoms"]:
            if s not in symptom_set:
                symptom_set.append(s)
    return {"covered": bool(diseases), "crop": crop_key, "symptoms": symptom_set}


def match_disease(crop, selected_symptoms):
    crop_key = (crop or "").strip().lower()
    diseases = DISEASE_REFERENCE.get(crop_key)
    if not diseases:
        return {
            "covered": False, "crop": crop,
            "message": f"No disease reference for '{crop}' yet. Currently covers: "
                       f"{', '.join(DISEASE_REFERENCE.keys())}.",
        }

    selected = set(s.strip().lower() for s in (selected_symptoms or []))
    scored = []
    for d in diseases:
        d_symptoms = set(s.lower() for s in d["symptoms"])
        overlap = len(selected & d_symptoms)
        if overlap > 0:
            scored.append((overlap, d))
    scored.sort(key=lambda x: x[0], reverse=True)

    matches = [{
        "disease": d["disease"], "matched_symptoms": overlap,
        "cause": d["cause"], "treatment": d["treatment"],
        "recommended_fungicide": d["recommended_fungicide"],
    } for overlap, d in scored]

    return {
        "covered": True, "crop": crop_key,
        "matches": matches if matches else [],
        "message": None if matches else "No close match for the symptoms selected — try selecting "
                                          "more specific symptoms, or consult a local expert.",
        "disclaimer": GENERAL_SAFETY_NOTE,
    }
