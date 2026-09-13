import re

def clean_ocr_text(text: str) -> str:
    """
    Safely clean and normalize raw OCR text while strictly preserving:
    - Currency symbols (₹, Rs., Rs, INR)
    - Numbers, decimals, percentages, dates (DD/MM/YYYY, MM/YYYY, DD.MM.YY)
    - Units (g, gm, gms, kg, ml, l, ltr, litre, liter, pcs, N)
    - Contact info (phone numbers, email addresses, websites)
    - Statutory terms (FSSAI, Lic No, Mfg, Exp, MRP, Batch)
    - No hallucinated words or text alteration.
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove non-printing characters and replacement unicode characters
    text = re.sub(r'[\uFFFD\u2022\u2023\u25E6\u2043\u2219\ufeff]+', ' ', text)

    lines = []
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        # Remove isolated stray punctuation symbols that are not numbers/currency/delimiters
        # e.g., isolated pipes, tildes, underscores, backslashes, carets
        line = re.sub(r'(?<!\S)[|~_§¤\^\\><]{1,2}(?!\S)', ' ', line)

        # Normalize FSSAI OCR misreads like FSSA1 -> FSSAI
        line = re.sub(r'\bFSSA[1lI]\b', 'FSSAI', line, flags=re.IGNORECASE)

        # Normalize spaces
        line = re.sub(r'[ \t]+', ' ', line).strip()

        # Discard lines that contain only 1-2 punctuation characters and no alphanumeric
        if len(line) <= 2 and not any(c.isalnum() for c in line):
            continue

        lines.append(line)

    return '\n'.join(lines)
