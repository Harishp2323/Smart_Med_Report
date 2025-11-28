import re

def extract_cbc_clean(text: str):
    results = {}

    def clean_token(s: str):
        return s.replace(",", "").replace("\xa0", " ").strip() if s else s

    def parse_number(s: str):
        if not s:
            return None
        s = s.strip().replace(",", "")
        s = re.sub(r"[^\d.\-]", "", s)
        try:
            return float(s)
        except:
            return None

    def normalize_by_unit(param, value, unit):
        if value is None:
            return None
        u = (unit or "").lower()

        if param == "HEMOGLOBIN":
            if "g/l" in u:
                return value / 10.0
            return value

        if param == "TOTAL LEUKOCYTE COUNT":
            if any(tok in u for tok in ["10^3", "10*3", "per cmm", "thou/mm3","10^3/ul", "10*3/ul", "10^3/uL", "10*3/uL"]) or not u:
                return value * 1000.0
            return value

        if param == "TOTAL RBC COUNT":
            if any(tok in u for tok in ["million", "10^6", "10*6", "mil/cumm","millmm3"]) or not u:
                return value * 1_000_000.0
            return value

        if param == "PLATELET COUNT":
            if "lakh" in u or "lacs" in u:
                return value * 100_000.0
            if any(tok in u for tok in ["10^3", "10*3", "per cmm", "10^3/µl", "10*3/µl", "10^3/uL"]):
                return value * 1000.0
            return value

        return value

    raw_text = text or ""
    text_up = raw_text.replace("\r", "\n")
    text_up = re.sub(r"[\u00A0\t]+", " ", text_up)
    lines = [ln.strip() for ln in text_up.splitlines() if ln.strip()]

    age = None
    sex = None
    age_sex_match = re.search(
        r"Age\s*[/\\]?Gender\s*[:\s]*([0-9]{1,3})\s*[/\\]?\s*(M|F|Male|Female)",
        raw_text, re.I)
    if age_sex_match:
        age = int(age_sex_match.group(1))
        s = age_sex_match.group(2).strip().upper()
        sex = "Male" if s in ["M", "MALE"] else "Female"

    if age is None:
        age_match = re.search(r"\bAge\s*[:/\\]?\s*(\d{1,3})", raw_text, re.I)
        if age_match:
            age = int(age_match.group(1))

    if sex is None:
        sex_match = re.search(r"\b(?:Sex|Gender)\s*[:/\\]?\s*(Male|Female|M|F|Other)", raw_text, re.I)
        if sex_match:
            s = sex_match.group(1).strip().upper()
            sex = "Male" if s in ["M", "MALE"] else ("Female" if s in ["F", "FEMALE"] else s.capitalize())

    results["Age"] = age
    results["Sex"] = sex

    PARAM_PATTERNS = {
        "HEMOGLOBIN": r"\b(?:HB|HEMOGLOBIN|HAEMOGLOBIN)\b",
        "TOTAL LEUKOCYTE COUNT": r"\b(?:WBC|TOTAL\s+LEUKOCYTE\s+COUNT|TOTAL\s+LEUKOCYTE|TOTAL\s+W\.?\s*B\.?\s*C\.?\s*COUNT|TOTAL\s+LEUCOCYTE\s*COUNT|TLC)\b",
        "TOTAL RBC COUNT": r"\b(?:RBC|TOTAL\s+RBC\s+COUNT|TOTAL\s+RED\s+BLOOD\s+CELLS?|RBC\s*COUNT)\b",
        "PLATELET COUNT": r"\b(?:PLT|PLATELET\s+COUNT|PLATELETS|TOTAL\s+PLATELET\s+COUNT)\b",
        "HEMATOCRIT": r"\b(?:HCT|HEMATOCRIT|PCV|HEMATOCRIT\s+VALUE)\b",
        "MCV": r"\b(?:MCV|M\.?C\.?V\.?|MEAN\s+CORPUSCULAR\s+VOLUME)\b",
        "MCH": r"\b(?:MCH|MEAN\s+CELL\s+HAEMOGLOBIN)(?!\s+CON)\b",
        "MCHC": r"\b(?:MCHC|MEAN\s+CELL\s+HAEMOGLOBIN\s+CON)\b",
        "RDW-CV": r"\bRDW[-\s]*CV\b",
        "RDW-SD": r"\bRDW[-\s]*SD\b",
        "RDW": r"\bRED\s*CELL\s*DISTRIBUTION\s*WIDTH\b|RDW\b",
        "NEUTROPHILS": r"\b(?:NEU[%\s]*|NEUTROPHILS|SEGMENTED\s+NEUTROPHILS|NEUTROPHIL)\b",
        "LYMPHOCYTES": r"\b(?:L?YMPHOCYTE|L?YMPHOCYTES|LYM[%\s]*)\b",
        "MONOCYTES": r"\b(?:MON[%\s]*|MONOCYTE|MONOCYTES)\b",
        "EOSINOPHILS": r"\b(?:EOS[%\s]*|EOSINOPHIL|EOSINOPHILS)\b",
        "BASOPHILS": r"\b(?:BAS[%\s]*|BASOPHIL|BASOPHILS)\b",
        "ESR": r"\bESR\b"
    }

    parameters = {}
    raw_parameters = {}
    ranges_extracted = {}
    n = len(lines)
    unit_pattern = r"\b(g/dl|g/dL|g/l|g/L|%|Lacs Per cmm|Lacs|lakhs|mil/cumm|million/cumm|million|10\^3|10\*3|10\^6|10\*6|cumm|/ul|/uL|/µl|Per cmm|cells/mm|pg|Pg|fl|fL|mm/hr|millmm3|thou/mm3)\b"
    range_pattern = r"(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)"

    for param, name_pattern in PARAM_PATTERNS.items():
        found = False
        for i in range(n):
            current_line = lines[i].upper()
            if re.search(name_pattern, current_line, re.I):
                search_block = " ".join(lines[i:i+7])
                number_match = re.search(r"([<>]?\d[\d,\.]*)", search_block)
                raw_val = clean_token(number_match.group(1)) if number_match else None
                unit_match = re.search(unit_pattern, search_block, re.I)
                unit = unit_match.group(1) if unit_match else ""

                if not unit:
                    unit = {
                        "HEMATOCRIT": "%", "PCV": "%", "MCV": "fL",
                        "RDW-CV": "%", "RDW": "%", "RDW-SD": "fL",
                        "MCH": "pg", "MCHC": "g/dL",
                        "NEUTROPHILS": "%", "LYMPHOCYTES": "%",
                        "MONOCYTES": "%", "EOSINOPHILS": "%", "BASOPHILS": "%",
                        "ESR": "mm/hr"
                    }.get(param, "")

                range_match = re.search(range_pattern, search_block)
                if range_match:
                    low = parse_number(range_match.group(1))
                    high = parse_number(range_match.group(2))
                    ranges_extracted[param] = (low, high)
                else:
                    upto_match = re.search(r"(up to|below)\s*(\d+\.?\d*)", search_block, re.I)
                    if upto_match:
                        high = parse_number(upto_match.group(2))
                        ranges_extracted[param] = (0, high)
                    else:
                        ranges_extracted[param] = None

                num = parse_number(raw_val)
                num = normalize_by_unit(param, num, unit)

                if param.upper() == "RDW":
                    if "RDW-CV" not in parameters or parameters["RDW-CV"] is None:
                        parameters["RDW-CV"] = num
                        raw_parameters["RDW-CV"] = {"raw": raw_val, "unit": unit}
                        ranges_extracted["RDW-CV"] = ranges_extracted.get(param)
                else:
                    parameters[param] = num
                    raw_parameters[param] = {"raw": raw_val, "unit": unit}

                found = True
                break

        if not found:
            parameters[param] = None
            raw_parameters[param] = {"raw": None, "unit": None}
            ranges_extracted[param] = None

    results["Parameters"] = parameters
    results["Raw_Parameters"] = raw_parameters
    results["Ranges"] = ranges_extracted
    return results


def assess_cbc(parameters: dict, age: int = None, sex: str = None, custom_ranges: dict = None):
    ranges = {
        "HEMOGLOBIN": {"Male": (13.0, 17.0), "Female": (12.0, 16.0)},
        "TOTAL LEUKOCYTE COUNT": (4500.0, 11000.0),
        "TOTAL RBC COUNT": (4_500_000.0, 5_500_000.0),
        "PLATELET COUNT": (150000.0, 450000.0),
        "HEMATOCRIT": (40.0, 50.0),
        "MCV": (80.0, 100.0),
        "MCH": (27.0, 32.0),
        "MCHC": (31.5, 34.5),
        "RDW-CV": (11.5, 14.5),
        "RDW-SD": (35.0, 56.0),
        "NEUTROPHILS": (40.0, 80.0),
        "LYMPHOCYTES": (20.0, 40.0),
        "MONOCYTES": (2.0, 10.0),
        "EOSINOPHILS": (1.0, 6.0),
        "BASOPHILS": (0.0, 2.0),
        "ESR": (0.0, 20.0)
    }

    if custom_ranges:
        for k, v in custom_ranges.items():
            ranges[k] = v

    if age is not None:
        if age <= 1:
            ranges.update({
                "HEMOGLOBIN": (10.0, 14.0),
                "TOTAL LEUKOCYTE COUNT": (6000.0, 17000.0),
                "TOTAL RBC COUNT": (3_900_000.0, 5_100_000.0),
                "HEMATOCRIT": (30.0, 40.0),
            })
        elif age <= 5:
            ranges.update({
                "HEMOGLOBIN": (11.0, 14.0),
                "TOTAL LEUKOCYTE COUNT": (5000.0, 15000.0),
                "TOTAL RBC COUNT": (4_000_000.0, 5_200_000.0),
                "HEMATOCRIT": (32.0, 40.0),
            })

    units = {
        "HEMOGLOBIN": "g/dL", "TOTAL LEUKOCYTE COUNT": "/µL", "TOTAL RBC COUNT": "/µL",
        "PLATELET COUNT": "/µL", "HEMATOCRIT": "%", "MCV": "fL", "MCH": "pg",
        "MCHC": "g/dL", "RDW-CV": "%", "RDW-SD": "%", "NEUTROPHILS": "%", "LYMPHOCYTES": "%",
        "MONOCYTES": "%", "EOSINOPHILS": "%", "BASOPHILS": "%", "ESR": "mm/hr"
    }

    TOLERANCE = 0.02

    def get_range(key):
        r = ranges.get(key)
        if r is None:
            return None
        if isinstance(r, dict):
            if sex and sex.capitalize() in r:
                return r[sex.capitalize()]
            return (min(v[0] for v in r.values()), max(v[1] for v in r.values()))
        return r

    assessed = {}
    for key in ranges.keys():
        unit = units.get(key, "")
        val = parameters.get(key)
        rng = get_range(key)
        
        if rng is None:
            assessed[key] = {"value": val, "status": "NA", "unit": unit, "range": "N/A"}
            continue

        low, high = rng
        if val is None:
            val = (low + high) / 2

        tol_low = low * (1 - TOLERANCE)
        tol_high = high * (1 + TOLERANCE)
        
        if val < tol_low:
            status = "Low"
        elif val > tol_high:
            status = "High"
        else:
            status = "Normal"

        assessed[key] = {"value": val, "status": status, "unit": unit, "range": f"{low}-{high}"}

    abs_counts = {}
    wbc = parameters.get("TOTAL LEUKOCYTE COUNT") or get_range("TOTAL LEUKOCYTE COUNT")[0]
    for diff_key in ["NEUTROPHILS", "LYMPHOCYTES", "MONOCYTES", "EOSINOPHILS", "BASOPHILS"]:
        pct = parameters.get(diff_key)
        if pct is None:
            pct = get_range(diff_key)[0]
        abs_counts[diff_key + "_ABS"] = {"value": round(wbc * (pct / 100.0), 2), "unit": "/µL"}

    return {"assessed": assessed, "absolute_counts": abs_counts}