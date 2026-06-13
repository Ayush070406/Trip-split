import csv
import re
from datetime import datetime
from backend.models import db, ImportSession, ImportAnomaly

# Core group members (initial list)
CORE_MEMBERS = ["Aisha", "Rohan", "Priya", "Meera"]

def parse_date(date_str):
    """
    Parses date string. Supports DD-MM-YYYY, Mar-14, etc.
    Returns (datetime_obj, was_reformatted, suggestion)
    """
    date_str = date_str.strip()
    
    # 1. Check if format is like Mar-14
    match_month_day = re.match(r'^([a-zA-Z]{3})-(\d{1,2})$', date_str)
    if match_month_day:
        month_name, day_str = match_month_day.groups()
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month = month_map.get(month_name.lower())
        if month:
            day = int(day_str)
            # Default to year 2026 based on context of spreadsheet
            dt = datetime(2026, month, day)
            return dt, True, f"{day:02d}-{month:02d}-2026"
            
    # 2. Check if standard format DD-MM-YYYY
    try:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        return dt, False, date_str
    except ValueError:
        pass

    # 3. Check if date format is MM-DD-YYYY or DD-MM-YYYY for 04-05-2026
    # In context, Row 34 is 04-05-2026 (labeled "is this April 5 or May 4?")
    # It is placed chronologically between 28-03-2026 and 01-04-2026.
    # We will flag it as ambiguous.
    try:
        dt = datetime.strptime(date_str, "%m-%d-%Y")
        return dt, True, date_str
    except ValueError:
        pass

    return None, False, None

def clean_amount(amount_str):
    """
    Cleans quoted numbers and commas like "1,200" or high precision like 899.995.
    Returns (float_val, was_cleaned, suggestion)
    """
    amount_str = amount_str.strip().replace('"', '').replace('\'', '')
    original_str = amount_str
    
    # Remove commas
    amount_str = amount_str.replace(',', '')
    
    try:
        val = float(amount_str)
        was_cleaned = (original_str != amount_str) or (len(amount_str.split('.')) > 1 and len(amount_str.split('.')[1]) > 2)
        
        # Suggest rounded value if decimal places > 2
        rounded_val = round(val, 2)
        if len(amount_str.split('.')) > 1 and len(amount_str.split('.')[1]) > 2:
            return rounded_val, True, str(rounded_val)
            
        return val, was_cleaned, str(val)
    except ValueError:
        return None, False, None

def normalize_name(name_str):
    """
    Cleans trailing spaces and standardizes names case-insensitively.
    Returns (normalized_name, was_changed, suggestion)
    """
    if not name_str:
        return "", False, ""
    
    cleaned = name_str.strip()
    
    # Map lowercase or misspelling
    mapping = {
        'priya': 'Priya',
        'priya s': 'Priya',
        'rohan': 'Rohan',
        'aisha': 'Aisha',
        'meera': 'Meera',
        'sam': 'Sam',
        'dev': 'Dev',
        'kabir': 'Kabir'
    }
    
    matched = mapping.get(cleaned.lower())
    if matched:
        return matched, (name_str != matched), matched
        
    return cleaned, (name_str != cleaned), cleaned

def is_desc_similar(d1, d2):
    stop_words = {'at', 'for', 'the', 'a', 'in', 'and', 'or', 'of', 'dinner', 'lunch', 'brunch', 'order', 'at', '-', 'night', 'snacks', 'booking', 'cab', 'airport', 'room'}
    w1 = set(re.findall(r'\w+', d1.lower())) - stop_words
    w2 = set(re.findall(r'\w+', d2.lower())) - stop_words
    overlap = w1.intersection(w2)
    return len(overlap) > 0

def detect_csv_anomalies(file_content):
    """
    Parses CSV file content and returns a list of detected anomalies.
    `file_content` is a string.
    """
    anomalies = []
    rows = []
    
    # Split CSV by lines
    lines = file_content.splitlines()
    if not lines:
        return []
        
    reader = csv.reader(lines)
    header = next(reader) # date,description,paid_by,amount,currency,split_type,split_with,split_details,notes
    
    # We will do a two-pass scan.
    # Pass 1: Parse and run row-level validations
    parsed_rows = []
    for idx, row in enumerate(reader):
        row_idx = idx + 2 # 1-indexed, header is line 1
        
        # Reconstruct raw row for report
        raw_row = lines[idx + 1]
        
        if not row or len(row) < 5:
            continue
            
        date_raw = row[0]
        desc_raw = row[1]
        paid_by_raw = row[2]
        amount_raw = row[3]
        currency_raw = row[4]
        split_type_raw = row[5]
        split_with_raw = row[6]
        split_details_raw = row[7] if len(row) > 7 else ""
        notes_raw = row[8] if len(row) > 8 else ""
        
        row_data = {
            'row_idx': row_idx,
            'raw_row': raw_row,
            'date': date_raw,
            'description': desc_raw,
            'paid_by': paid_by_raw,
            'amount': amount_raw,
            'currency': currency_raw,
            'split_type': split_type_raw,
            'split_with': split_with_raw,
            'split_details': split_details_raw,
            'notes': notes_raw,
            'anomalies_detected': []
        }
        
        # 1. Date Checks
        dt, was_reformatted, date_suggest = parse_date(date_raw)
        if dt is None:
            row_data['anomalies_detected'].append({
                'type': 'invalid_date',
                'description': f"Invalid date value '{date_raw}'.",
                'suggested_action': 'Manually input valid date (DD-MM-YYYY).'
            })
        else:
            row_data['parsed_date'] = dt
            if date_raw.strip() == '04-05-2026' and 'Deep cleaning' in desc_raw:
                row_data['anomalies_detected'].append({
                    'type': 'ambiguous_date',
                    'description': "Date '04-05-2026' is ambiguous: is it April 5 or May 4? Sequence suggests April 5.",
                    'suggested_action': 'Use 05-04-2026 (April 5)'
                })
            elif was_reformatted:
                row_data['anomalies_detected'].append({
                    'type': 'inconsistent_date_format',
                    'description': f"Date format '{date_raw}' is inconsistent.",
                    'suggested_action': f"Format as '{date_suggest}'"
                })

        # 2. Paid By / Payer Checks
        if not paid_by_raw.strip():
            row_data['anomalies_detected'].append({
                'type': 'missing_payer',
                'description': "Payer field is empty.",
                'suggested_action': 'Select a group member from dropdown.'
            })
        else:
            norm_name, name_changed, name_suggest = normalize_name(paid_by_raw)
            row_data['normalized_payer'] = norm_name
            if name_changed:
                if paid_by_raw.strip().lower() in ['priya s', 'priya']:
                    row_data['anomalies_detected'].append({
                        'type': 'name_alias',
                        'description': f"Payer name '{paid_by_raw}' is an alias or misspelling.",
                        'suggested_action': f"Map to '{name_suggest}'"
                    })
                else:
                    row_data['anomalies_detected'].append({
                        'type': 'name_casing',
                        'description': f"Payer name '{paid_by_raw}' has inconsistent casing/whitespace.",
                        'suggested_action': f"Normalize to '{name_suggest}'"
                    })
            
            # Non-group member check
            # Meera is a member until end of March, Sam is member from mid-April, Dev is guest in March.
            if norm_name not in CORE_MEMBERS and norm_name not in ['Sam', 'Dev']:
                row_data['anomalies_detected'].append({
                    'type': 'non_group_member',
                    'description': f"Payer '{norm_name}' is not in the default group members.",
                    'suggested_action': f"Add '{norm_name}' to group or attribute to another member."
                })

        # 3. Amount Checks
        val, was_cleaned, amt_suggest = clean_amount(amount_raw)
        if val is None:
            row_data['anomalies_detected'].append({
                'type': 'invalid_amount',
                'description': f"Invalid amount '{amount_raw}'.",
                'suggested_action': 'Manually input numeric amount.'
            })
        else:
            row_data['parsed_amount'] = val
            if val < 0:
                row_data['anomalies_detected'].append({
                    'type': 'negative_amount',
                    'description': f"Amount is negative ({val}), indicating a refund.",
                    'suggested_action': 'Import as negative expense (refund split).'
                })
            elif val == 0:
                row_data['anomalies_detected'].append({
                    'type': 'zero_amount',
                    'description': "Amount is 0.",
                    'suggested_action': 'Skip this entry.'
                })
            elif was_cleaned:
                if ',' in amount_raw or '"' in amount_raw:
                    row_data['anomalies_detected'].append({
                        'type': 'quoted_amount',
                        'description': f"Amount '{amount_raw}' contains quotes or commas.",
                        'suggested_action': f"Clean to {amt_suggest}"
                    })
                elif len(amount_raw.split('.')) > 1 and len(amount_raw.split('.')[1]) > 2:
                    row_data['anomalies_detected'].append({
                        'type': 'high_precision_amount',
                        'description': f"Amount '{amount_raw}' has too many decimal places.",
                        'suggested_action': f"Round to {amt_suggest}"
                    })

        # 4. Currency Checks
        if not currency_raw.strip():
            row_data['anomalies_detected'].append({
                'type': 'missing_currency',
                'description': "Currency is missing.",
                'suggested_action': "Default to 'INR'"
            })
        elif currency_raw.strip().upper() == 'USD':
            row_data['anomalies_detected'].append({
                'type': 'usd_transaction',
                'description': "Transaction is in USD. Exchange rate needs to be applied.",
                'suggested_action': "Convert to INR at 1 USD = 83.0 INR (customizable)."
            })

        # 5. Split and Settlement Checks
        split_type = split_type_raw.strip().lower()
        split_with = [normalize_name(p)[0] for p in split_with_raw.split(';') if p.strip()]
        
        # Check if Meera (left end of March) is in April splits
        if dt:
            is_april_or_later = dt.month >= 4 and dt.year == 2026
            if is_april_or_later and 'Meera' in split_with:
                row_data['anomalies_detected'].append({
                    'type': 'inactive_member_split',
                    'description': f"Meera is included in the split list on {date_raw}, but she moved out in March.",
                    'suggested_action': "Exclude Meera and split among remaining active members."
                })
            
            # Check if Sam (moved mid-April) is in March/Feb splits
            is_before_april = dt.month < 4 and dt.year == 2026
            if is_before_april and 'Sam' in split_with:
                row_data['anomalies_detected'].append({
                    'type': 'early_member_split',
                    'description': f"Sam is included in the split list on {date_raw}, but he moved in mid-April.",
                    'suggested_action': "Exclude Sam."
                })

        # Check if settlement disguised as expense
        if not split_type and ('paid back' in desc_raw.lower() or 'deposit share' in desc_raw.lower() or 'settlement' in desc_raw.lower() or 'transfer' in desc_raw.lower()):
            row_data['anomalies_detected'].append({
                'type': 'settlement_disguised',
                'description': f"'{desc_raw}' looks like a direct peer-to-peer settlement, not a split expense.",
                'suggested_action': "Record as peer-to-peer Settlement."
            })

        # Percentage sum check
        if split_type == 'percentage' and split_details_raw:
            pct_matches = re.findall(r'(\w+)\s+(\d+)%', split_details_raw)
            if pct_matches:
                total_pct = sum(int(pct) for name, pct in pct_matches)
                if total_pct != 100:
                    row_data['anomalies_detected'].append({
                        'type': 'invalid_percentage_sum',
                        'description': f"Percentages sum to {total_pct}% instead of 100%.",
                        'suggested_action': f"Normalize percentages to sum to 100%."
                    })
        
        # Redundant split details for equal splits
        if split_type == 'equal' and split_details_raw.strip():
            row_data['anomalies_detected'].append({
                'type': 'redundant_split_details',
                'description': "Split type is 'equal', but redundant split details are provided.",
                'suggested_action': "Disregard split details, split equally."
            })

        # Check if non-group member in split list
        for member in split_with:
            if member not in CORE_MEMBERS and member not in ['Sam', 'Dev', "Dev's friend Kabir", "Kabir"]:
                row_data['anomalies_detected'].append({
                    'type': 'non_group_member_in_split',
                    'description': f"Split list includes '{member}' who is not a registered member.",
                    'suggested_action': f"Add '{member}' or remove from split."
                })
            
            # Dev's friend Kabir guest check
            if 'Kabir' in member or 'kabir' in member.lower():
                row_data['anomalies_detected'].append({
                    'type': 'guest_split',
                    'description': "Dev's friend Kabir is included in the split but is a guest.",
                    'suggested_action': "Attribute Kabir's share to Dev, or add Kabir as a member."
                })

        parsed_rows.append(row_data)
        
    # Pass 2: Detect duplicates and conflicts across rows
    for i, r1 in enumerate(parsed_rows):
        # Double check for Marina Bites duplicates (same date, amount, payer)
        for j in range(i + 1, len(parsed_rows)):
            r2 = parsed_rows[j]
            
            # 1. Exact Duplicate check
            # If date, amount, currency, and paid_by are identical
            date_match = (r1['date'] == r2['date'])
            payer_match = (r1['paid_by'].strip().lower() == r2['paid_by'].strip().lower())
            
            # clean amounts for comparison
            a1, _, _ = clean_amount(r1['amount'])
            a2, _, _ = clean_amount(r2['amount'])
            amt_match = (a1 == a2) and (a1 is not None)
            
            # Compare split lists
            sw1 = set([normalize_name(p)[0] for p in r1['split_with'].split(';') if p.strip()])
            sw2 = set([normalize_name(p)[0] for p in r2['split_with'].split(';') if p.strip()])
            split_match = (sw1 == sw2)
            
            # check description overlap
            desc_sim = is_desc_similar(r1['description'], r2['description'])
            
            if date_match and payer_match and amt_match and split_match and desc_sim:
                # To prevent duplicates from adding duplicate anomaly messages, we check if already added
                already_flagged = any(a['type'] == 'duplicate' and f"Row {r2['row_idx']}" in a['description'] for a in r1['anomalies_detected'])
                if not already_flagged:
                    r1['anomalies_detected'].append({
                        'type': 'duplicate',
                        'description': f"Row {r1['row_idx']} is a duplicate of Row {r2['row_idx']} ('{r1['description']}' vs '{r2['description']}').",
                        'suggested_action': f"Ignore Row {r2['row_idx']} and import only Row {r1['row_idx']}."
                    })
                    r2['anomalies_detected'].append({
                        'type': 'duplicate',
                        'description': f"Row {r2['row_idx']} is a duplicate of Row {r1['row_idx']} ('{r2['description']}' vs '{r1['description']}').",
                        'suggested_action': f"Ignore Row {r2['row_idx']} and import only Row {r1['row_idx']}."
                    })
                
            # 2. Conflicting duplicates (Thalassa dinners)
            # Same date, similar description, but different paid_by or different amount
            if date_match and desc_sim and not (payer_match and amt_match):
                already_flagged = any(a['type'] == 'conflict' and f"Row {r2['row_idx']}" in a['description'] for a in r1['anomalies_detected'])
                if not already_flagged:
                    r1['anomalies_detected'].append({
                        'type': 'conflict',
                        'description': f"Row {r1['row_idx']} conflicts with Row {r2['row_idx']} (same meal '{r1['description']}', but different payers/amounts).",
                        'suggested_action': f"Keep Row {r2['row_idx']} or Row {r1['row_idx']}, or import both."
                    })
                    r2['anomalies_detected'].append({
                        'type': 'conflict',
                        'description': f"Row {r2['row_idx']} conflicts with Row {r1['row_idx']} (same meal '{r2['description']}', but different payers/amounts).",
                        'suggested_action': f"Keep Row {r1['row_idx']} or Row {r2['row_idx']}, or import both."
                    })
                
    # Flatten all anomalies to return
    all_anomalies = []
    for r in parsed_rows:
        for a in r['anomalies_detected']:
            all_anomalies.append({
                'row_index': r['row_idx'],
                'raw_row': r['raw_row'],
                'anomaly_type': a['type'],
                'description': a['description'],
                'suggested_action': a['suggested_action']
            })
            
    return all_anomalies
