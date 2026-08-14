import re
import spacy
import hashlib
from docx import Document
from faker import Faker

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

def normalize_entity(text, entity_type):
    """Normalize text for consistent hashing and registry mapping."""
    # Remove harmless surrounding punctuation, footnotes, and whitespace
    text = text.strip('.,;:\'"()[]{}<>*- \t\n\r*^&#@!~`')
    text = " ".join(text.split())
    text = text.lower()
    
    if entity_type == 'PHONE':
        digits = re.sub(r'\D', '', text)
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith('0'):
            digits = digits[1:]
        return digits
    return text

def generate_fake_value(canonical_text, entity_type):
    """Deterministically generate fake data based on canonical text and entity type."""
    seed = int(hashlib.sha256(f"{canonical_text}_{entity_type}".encode()).hexdigest()[:15], 16)
    
    Faker.seed(seed)
    fake = Faker('en_IN')
    
    if entity_type == 'PERSON':
        return fake.name()
    elif entity_type == 'EMAIL':
        return fake.email()
    elif entity_type == 'PHONE':
        return fake.phone_number()
    elif entity_type == 'ORG':
        return fake.company()
    elif entity_type == 'ADDRESS':
        return fake.address().replace('\n', ', ')
    elif entity_type == 'DOB':
        return fake.date_of_birth().strftime('%B %d, %Y')
    elif entity_type == 'IP':
        return fake.ipv4()
    elif entity_type == 'SSN':
        return fake.ssn()
    elif entity_type == 'CREDIT_CARD':
        return fake.credit_card_number()
    return "REDACTED"

def detect_emails(text):
    spans = []
    pattern = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
    for m in pattern.finditer(text):
        val = m.group()
        end = m.end()
        while val and val[-1] in '.,;':
            val = val[:-1]
            end -= 1
        if val and '@' in val:
            spans.append((m.start(), end, 'EMAIL', val))
    return spans

def detect_phones(text):
    spans = []
    # Strict formats with country/area code or spacing/hyphens
    pattern_format = re.compile(r'(?:\+\s*91[\s-]*\d[\d\s-]{8,}|\b0\d{2,4}[\s-]+\d{6,8}\b|\b[6-9]\d{2}[\s-]+\d{3}[\s-]+\d{4}\b)')
    for m in pattern_format.finditer(text):
        spans.append((m.start(), m.end(), 'PHONE', m.group()))
        
    # Flat 10-digit numbers require contextual confidence
    pattern_flat = re.compile(r'\b[6-9]\d{9}\b')
    phone_keywords = ['phone', 'tel', 'mobile', 'contact', 'call', 'fax']
    lower_text = text.lower()
    has_context = any(kw in lower_text for kw in phone_keywords)
    
    for m in pattern_flat.finditer(text):
        if not any(s[0] <= m.start() and s[1] >= m.end() for s in spans):
            if has_context:
                spans.append((m.start(), m.end(), 'PHONE', m.group()))
    return spans

def detect_ips(text):
    spans = []
    pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    for m in pattern.finditer(text):
        parts = [int(x) for x in m.group().split('.')]
        if all(0 <= p <= 255 for p in parts):
            spans.append((m.start(), m.end(), 'IP', m.group()))
    return spans

def detect_ssns(text):
    spans = []
    pattern = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    for m in pattern.finditer(text):
        spans.append((m.start(), m.end(), 'SSN', m.group()))
    return spans

def detect_credit_cards(text):
    spans = []
    pattern = re.compile(r'\b(?:\d{4}[\s-]?){3,4}\d{0,4}\b')
    for m in pattern.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if len(digits) in (15, 16):
            s = 0
            for i, c in enumerate(reversed(digits)):
                n = int(c)
                if i % 2 == 1:
                    n *= 2
                    if n > 9: n -= 9
                s += n
            if s % 10 == 0:
                spans.append((m.start(), m.end(), 'CREDIT_CARD', m.group()))
    return spans

def detect_dobs(text):
    spans = []
    ctx_pat = re.compile(r'(?:date\s+of\s+birth|DOB|born|birth\s+date)', re.IGNORECASE)
    if ctx_pat.search(text):
        date_pat = re.compile(r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b', re.IGNORECASE)
        for m in date_pat.finditer(text):
            spans.append((m.start(), m.end(), 'DOB', m.group()))
    return spans

def detect_ner(text):
    spans = []
    if not text.strip(): return spans
    doc = nlp(text)
    
    org_suffixes = {
        'limited', 'ltd', 'pvt', 'private', 'llp', 'inc', 'corporation', 
        'industries', 'technologies', 'bank', 'management', 'securities', 
        'capital', 'partners', 'associates', 'group', 'services', 
        'chartered accountants', 'advocates', 'consultants', 'auditors'
    }
    
    excluded_person_words = {
        'director', 'officer', 'secretary', 'chairman', 'board', 'committee', 
        'promoter', 'shareholder', 'investor', 'manager', 'lead', 'act', 
        'section', 'red', 'herring', 'prospectus', 'equity', 'shares', 'company',
        'value', 'face', 'total', 'offer', 'bidders', 'bid', 'issue', 'date',
        'financial', 'statement', 'year', 'period', 'exchange', 'managers', 'mr', 'mrs', 'ms', 'dr'
    }
    
    # Check NER entities from spaCy
    for ent in doc.ents:
        val = ent.text.strip()
        if not val or len(val) < 3: continue
        lower_val = val.lower()
        
        has_suffix = any(re.search(rf'\b{s}\b', lower_val) for s in org_suffixes)
        
        if ent.label_ == 'ORG' and has_suffix:
            spans.append((ent.start_char, ent.start_char + len(val), 'ORG', val))
        elif ent.label_ in ('PERSON', 'ORG', 'GPE', 'NORP', 'WORK_OF_ART', 'PRODUCT'):
            words = val.split()
            while words and words[0].lower().rstrip('.,;*^&#@!~`') in excluded_person_words:
                words.pop(0)
            while words and words[-1].lower().rstrip('.,;*^&#@!~`') in excluded_person_words:
                words.pop()
                
            clean_words = [w.strip('.,;:\'"*^&()[]{}#@!~`') for w in words]
            if len(clean_words) >= 2 and all(w and w[0].isupper() for w in clean_words):
                if not any(w.lower() in excluded_person_words for w in clean_words):
                    clean_name = " ".join(clean_words)
                    start_offset = text.find(clean_name, ent.start_char)
                    if start_offset != -1:
                        spans.append((start_offset, start_offset + len(clean_name), 'PERSON', clean_name))
                
    # Contextual pattern for list of promoters / directors if missed by spaCy
    promoter_pat = re.compile(r'(?:Individual Promoters|Promoters|Directors)[\s:]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+(?:,\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)*)', re.UNICODE)
    for m in promoter_pat.finditer(text):
        list_str = m.group(1)
        base_offset = m.start(1)
        for item in re.finditer(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', list_str):
            p_name = item.group().strip()
            w_list = [w for w in p_name.split() if w.lower() not in excluded_person_words]
            if len(w_list) >= 2:
                spans.append((base_offset + item.start(), base_offset + item.end(), 'PERSON', p_name))
                
    return spans

def detect_addresses(text):
    spans = []
    if len(text) > 300:
        return spans
        
    lower_text = text.lower()
    address_anchors = [
        'village', 'taluka', 'pin -', 'pin code', 'road', 'floor', 'tower', 
        'building', 'marg', 'nagar', 'apartment', 'reclamation', 'churchgate', 
        'street', 'lane', 'district', 'residential address', 'registered office', 'corporate office'
    ]
    
    score = sum(1 for anchor in address_anchors if anchor in lower_text)
    has_pin = bool(re.search(r'\b\d{6}\b|\b\d{3}\s\d{3}\b', text))
    has_address_kw = any(kw in lower_text for kw in ['registered office', 'corporate office', 'address', 'residential address'])
    
    if score >= 2 or (score >= 1 and has_pin) or (has_address_kw and score >= 1):
        start = 0
        match = re.search(r'^(?:Registered Office|Corporate Office|Residential Address|Address)[\s:]*', text, re.IGNORECASE)
        if match:
            start = match.end()
        address_text = text[start:].strip()
        if len(address_text) > 15:
            spans.append((start, start + len(address_text), 'ADDRESS', address_text))
    return spans

def detect_pii(text):
    all_spans = []
    all_spans.extend(detect_emails(text))
    all_spans.extend(detect_phones(text))
    all_spans.extend(detect_ips(text))
    all_spans.extend(detect_ssns(text))
    all_spans.extend(detect_credit_cards(text))
    all_spans.extend(detect_dobs(text))
    all_spans.extend(detect_ner(text))
    all_spans.extend(detect_addresses(text))
    
    priority = {'EMAIL': 1, 'PHONE': 2, 'SSN': 3, 'CREDIT_CARD': 4, 'IP': 5, 'DOB': 6, 'ADDRESS': 7, 'PERSON': 8, 'ORG': 9}
    all_spans.sort(key=lambda x: (x[0], priority[x[2]], -(x[1]-x[0])))
    
    resolved = []
    for span in all_spans:
        start, end, etype, val = span
        overlap = False
        for r_start, r_end, r_etype, r_val in resolved:
            if not (end <= r_start or start >= r_end):
                overlap = True
                break
        if not overlap:
            resolved.append(span)
            
    return resolved

def redact_runs(runs, replacements):
    """Map replacements to original runs and update their text right-to-left."""
    if not replacements:
        return
        
    char_map = []
    for ri, r in enumerate(runs):
        for ci in range(len(r.text)):
            char_map.append((ri, ci))
            
    replacements.sort(key=lambda x: x[0], reverse=True)
    
    for start, end, fake_text in replacements:
        if start >= len(char_map) or end > len(char_map) or start >= end:
            continue
            
        affected_runs = sorted(list(set(char_map[i][0] for i in range(start, end))))
        if not affected_runs:
            continue
            
        first_char_idx = char_map[start][1]
        last_char_idx = char_map[end-1][1]
        
        if len(affected_runs) == 1:
            r_idx = affected_runs[0]
            runs[r_idx].text = runs[r_idx].text[:first_char_idx] + fake_text + runs[r_idx].text[last_char_idx+1:]
        else:
            r_first = affected_runs[0]
            runs[r_first].text = runs[r_first].text[:first_char_idx] + fake_text
            
            for r_mid in affected_runs[1:-1]:
                runs[r_mid].text = ""
                
            r_last = affected_runs[-1]
            runs[r_last].text = runs[r_last].text[last_char_idx+1:]

class BlockRecord:
    def __init__(self, runs):
        self.runs = runs
        self.text = "".join(r.text for r in runs)
        self.resolved_spans = []

def process_document(input_path, output_path):
    import os
    import tempfile
    import subprocess
    
    # Load input document safely with fallback for Windows file locking
    try:
        doc = Document(input_path)
    except Exception:
        temp_input = os.path.join(tempfile.gettempdir(), "temp_input_redactor.docx")
        subprocess.run(["powershell", "-Command", f'Copy-Item -Path "{input_path}" -Destination "{temp_input}" -Force'], capture_output=True)
        doc = Document(temp_input)
        if os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except Exception:
                pass
                
    records = []
    seen_paragraphs = set()
    
    # Extract unique logical blocks from paragraphs, tables, headers, and footers
    for p in doc.paragraphs:
        if p._p not in seen_paragraphs:
            seen_paragraphs.add(p._p)
            records.append(BlockRecord(p.runs))
            
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p._p not in seen_paragraphs:
                        seen_paragraphs.add(p._p)
                        records.append(BlockRecord(p.runs))
                        
    for section in doc.sections:
        if section.header:
            for p in section.header.paragraphs:
                if p._p not in seen_paragraphs:
                    seen_paragraphs.add(p._p)
                    records.append(BlockRecord(p.runs))
        if section.footer:
            for p in section.footer.paragraphs:
                if p._p not in seen_paragraphs:
                    seen_paragraphs.add(p._p)
                    records.append(BlockRecord(p.runs))
                
    # Phase 1: Detect and build global mapping
    global_registry = {}
    
    for record in records:
        if not record.text.strip():
            continue
        record.resolved_spans = detect_pii(record.text)
        
        for start, end, etype, val in record.resolved_spans:
            canon = normalize_entity(val, etype)
            if canon not in global_registry:
                global_registry[canon] = generate_fake_value(canon, etype)
                
    # Internal validation for 1:1 mapping
    assert len(global_registry) == len(set(global_registry.keys())), "Duplicate keys in registry"
                
    # Phase 2: Modify the DOCX using the global registry
    validation_registry = {}
    
    for record in records:
        if not record.resolved_spans:
            continue
            
        replacements = []
        for start, end, etype, val in record.resolved_spans:
            canon = normalize_entity(val, etype)
            fake_val = global_registry[canon]
            
            # Runtime validation: verify one canonical entity maps to exactly one replacement
            if canon in validation_registry:
                if validation_registry[canon] != fake_val:
                    raise ValueError(f"Consistency error: '{canon}' mapped to multiple replacements ('{validation_registry[canon]}' vs '{fake_val}')!")
            else:
                validation_registry[canon] = fake_val
                
            replacements.append((start, end, fake_val))
            
        redact_runs(record.runs, replacements)
                
    try:
        doc.save(output_path)
        print(f"Redacted document saved to {output_path}")
    except PermissionError:
        alt_path = output_path.replace(".docx", "_redacted.docx")
        doc.save(alt_path)
        print(f"Notice: '{output_path}' is open in an external viewer. Redacted output successfully saved to '{alt_path}'.")

if __name__ == "__main__":
    process_document("input/Red Herring Prospectus.docx", "output/redacted_prospectus.docx")
