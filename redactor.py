import re
import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

def detect_emails(text):
    spans = []
    pattern = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
    for m in pattern.finditer(text):
        val = m.group()
        end = m.end()
        while val and val[-1] in '.,;':
            val = val[:-1]
            end -= 1
        if val:
            spans.append((m.start(), end, 'EMAIL', val))
    return spans

def detect_phones(text):
    spans = []
    pattern = re.compile(r'(?:\+\s*91[\s-]*(?:\d[\s-]*){9,10}|\b0\d{2,3}[\s-]*\d{7,8}\b|\b(?:[6-9]\d{9})\b)')
    for m in pattern.finditer(text):
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
    org_suffixes = {'limited', 'ltd', 'pvt', 'private', 'llp', 'inc', 'corporation', 'industries', 'technologies', 'bank'}
    
    for ent in doc.ents:
        val = ent.text.strip()
        if not val or len(val) < 3: continue
        
        if ent.label_ == 'PERSON':
            words = val.split()
            if len(words) >= 2 and all(w and w[0].isupper() for w in words):
                spans.append((ent.start_char, ent.start_char + len(val), 'PERSON', val))
                
        elif ent.label_ == 'ORG':
            lower_val = val.lower()
            has_suffix = any(s in lower_val for s in org_suffixes)
            if has_suffix or len(val.split()) > 1:
                spans.append((ent.start_char, ent.start_char + len(val), 'ORG', val))
    return spans

def detect_addresses(text):
    spans = []
    lower_text = text.lower()
    address_anchors = ['village', 'taluka', 'pin -', 'pin code', 'road', 'floor', 'tower', 'building', 'marg', 'nagar', 'apartment', 'reclamation', 'churchgate']
    
    score = sum(1 for anchor in address_anchors if anchor in lower_text)
    has_pin = bool(re.search(r'\b\d{6}\b|\b\d{3}\s\d{3}\b', text))
    
    if score >= 2 or (score >= 1 and has_pin):
        start = 0
        match = re.match(r'^(?:Registered Office|Corporate Office|Address)[\s:]*', text, re.IGNORECASE)
        if match:
            start = match.end()
        if len(text) - start > 15:
            spans.append((start, len(text), 'ADDRESS', text[start:]))
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
