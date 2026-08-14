# PII Redaction Tool for Word Documents (.docx)

## Project Overview

This project is a specialized Personally Identifiable Information (PII) detection and deterministic pseudonymization system built for Microsoft Word (`.docx`) files. It was developed and tested on dense financial documents, specifically Indian IPO Draft Red Herring Prospectuses (DRHP) and Red Herring Prospectuses (RHP).

Instead of permanently deleting text or stripping styling, it identifies sensitive personal entities—including names, email addresses, phone numbers, postal addresses, organization names, dates of birth, IP addresses, government/corporate identifiers (like CIN/DIN), and financial numbers—and replaces them with contextually realistic synthetic values.

Crucially, the tool performs surgical in-place editing at the XML run level (`<w:r>`) using `python-docx`, ensuring that all original fonts, colors, bolding, italics, headers, footers, and table layouts remain completely intact.

---

## Key Features

### 1. Hybrid Detection Engine
- **Pattern-Based Regex Detectors**: Strict regular expressions for structured PII types (emails, phone numbers, IP addresses, dates of birth, credit cards validated via Luhn checksum, and PAN/SSN-like numbers).
- **Context-Gated Dates of Birth**: Dates are only classified as DOBs if they appear in close proximity to trigger keywords (such as "born on", "date of birth", or "DOB"). General corporate and regulatory dates (filing dates, resolution dates, bidding windows) are preserved.
- **spaCy Named Entity Recognition (NER)**: Uses `en_core_web_sm` to detect unstructured entity types, specifically person names (`PERSON`) and company names (`ORG`).
- **Structured Address Extraction**: Combines 6-digit Indian postal PIN codes (`\d{6}` or `\d{3}\s\d{3}`) with spatial boundary checks and keyword anchors (`Village`, `Road`, `Taluka`, `Floor`, `Bandra Kurla Complex`, `Registered Office`).

### 2. 1:1 Global Consistency (Deterministic Masking)
- Entity mentions across the document are normalized and grouped.
- A salted SHA-256 hash seeds Python's `Faker` library (using the Indian locale `en_IN`) to generate a unique synthetic replacement for each canonical entity.
- If a person or third-party company appears across multiple paragraphs and tables, it is deterministically replaced with the exact same fake name everywhere.

### 3. XML Run-Level Replacement
- Character offsets detected in the reconstructed text are mapped directly back to individual run boundaries within the document.
- Replacements are applied right-to-left (from the end of the text block to the beginning), which prevents character offset drift and preserves all inline typography.

### 4. Interactive Review Interface & Evaluation Tools
- **Streamlit Web Dashboard (`app.py`)**: Drag-and-drop file upload, one-click redaction, and instant output download.
- **Evaluation Harness (`evaluate.py` / `eval_script.py`)**: Computes precision, recall, F1-scores, span Jaccard accuracy, and sample pass rates against hand-labeled ground-truth datasets.

---

## Deliberate Design Decisions

- **Preserving Filing Company Identity (`EXCLUDED_ENTITIES`)**: A prospectus is written about a specific issuer company. Redacting the company's own legal names (`KSH International Limited` and predecessor `Bhandary Metal Extrusion Private Limited`) destroys readability and legal context. The tool explicitly excludes the issuer from redaction while masking third parties (promoters, directors, advisors, auditors, individual contacts).
- **Statutory Boilerplate Protection**: General regulators, stock exchanges, and legal acronyms (`SEBI`, `RBI`, `BSE`, `NSE`, `GST`, `PAN`, `Companies Act`) are excluded from organization redaction. They represent public regulatory frameworks rather than private company PII.
- **Dynamic Denylist Extraction**: Automatically inspects the document's own "Definitions and Abbreviations" tables at startup to extract capitalized terms (such as `INTERNAL RISKS`, `Net Proceeds`, `Statutory Auditors`, `CARE Report`), preventing spaCy from misclassifying them as names.

---

## Real-World Tradeoffs and Known Limitations

- **Dense Multi-Name Lists**: In promoter and director listings where multiple individuals share a surname (for example, several family members sharing the last name "Hegde"), spaCy occasionally truncates three-word names into two-word fragments (e.g., matching "Kushal Hegde" instead of "Rohit Kushal Hegde") or picks up nearby title phrases ("Independent Directors"). This makes the `PERSON` category the most complex (69.2% precision, 66.7% recall).
- **Company Names Without Legal Suffixes**: Organization detection performs best when standard corporate suffixes (`Limited`, `LLP`, `Private Limited`) are present. Standalone trade names or foundations sitting alone in table cells without surrounding grammatical context can occasionally be missed by small NER models.
- **Address Formatting Variability**: Address detection achieves 94.1% recall on standard postal and office blocks. However, non-standard addresses split across separate table rows or embedded inside lengthy narrative sentences can occasionally have partial span boundaries.
- **Sample Size Transparency**: Structured categories (`DOB` with 3 spans, `IP` with 2 spans) achieved 100% precision and recall in benchmarks, but these sample sizes are small because those fields occur infrequently in prospectuses.

---

## Performance & Evaluation Benchmark

The system was evaluated against 81 manually annotated ground-truth spans across 19 representative text sections from the prospectus. Spans were matched using character-level overlap (IoU >= 0.3) with entity type alignment.

### Evaluation Results Table

| Entity Type | Ground Truth | Predicted | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | F1-Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **EMAIL** | 12 | 12 | 12 | 0 | 0 | **100.0%** | **100.0%** | **1.000** |
| **PHONE** | 13 | 13 | 13 | 0 | 0 | **100.0%** | **100.0%** | **1.000** |
| **ADDRESS** | 17 | 16 | 16 | 0 | 1 | **100.0%** | **94.1%** | **0.970** |
| **ORG** | 7 | 6 | 6 | 0 | 1 | **100.0%** | **85.7%** | **0.923** |
| **DOB** | 3 | 3 | 3 | 0 | 0 | **100.0%** | **100.0%** | **1.000** |
| **IP** | 2 | 2 | 2 | 0 | 0 | **100.0%** | **100.0%** | **1.000** |
| **PERSON** | 27 | 26 | 18 | 8 | 9 | **69.2%** | **66.7%** | **0.679** |
| **Overall (Micro Avg)** | **81** | **78** | **70** | **8** | **11** | **89.7%** | **86.4%** | **0.881** |
| **Macro Average (F1)** | - | - | - | - | - | **95.6%** | **92.4%** | **0.939** |

### Additional Benchmark Metrics
- **Micro F1-Score**: 88.05%
- **Span Jaccard Accuracy (TP / (TP + FP + FN))**: 78.65%
- **Sample Perfect Pass Rate (0 FP and 0 FN)**: 57.89% (11 of 19 samples perfectly redacted)

---

## How to Run the Project

### 1. Installation
```bash
git clone https://github.com/Sakshi-Sood/pii_redaction.git
cd pii_redaction
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Run Redaction Pipeline (CLI)
```bash
python redactor.py
```
This reads `input/Red Herring Prospectus.docx` and writes the sanitized output to `output/redacted_prospectus.docx`.

### 3. Run Benchmark Evaluation
```bash
# Standard evaluation summary
python eval_script.py

# Print detailed false positive and false negative snippets
python eval_script.py --show-errors
```

### 4. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```

---

## How to Add a New PII Type

Each detector in `redactor.py` is a standalone function that takes plain text and returns a list of `(start, end, entity_type, value)` tuples.

To add a new entity category:
1. Write a detector function (using regex for pattern-based data or custom rules/NLP for unstructured data).
2. Call your detector inside `detect_pii()`.
3. Downstream entity normalization, 1:1 deterministic fake value assignment, and run-level Word splicing work automatically without modification.