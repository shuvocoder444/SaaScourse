import re
import csv
import json
import io
import zipfile
import xml.etree.ElementTree as ET
from apps.courses.bijoy_converter import is_bijoy_text, convert_bijoy_to_unicode


def normalize_bengali_digits(text: str) -> str:
    """Converts Bengali numerals to English numerals."""
    bengali_digits = "০১২৩৪৫৬৭৮৯"
    english_digits = "0123456789"
    mapping = str.maketrans("".join(bengali_digits), "".join(english_digits))
    return text.translate(mapping)


def map_option_to_letter(opt_str: str) -> str:
    """
    Maps various Bengali and English option representations to standard 'A', 'B', 'C', 'D'.
    Supports: ক, খ, গ, ঘ | K, L, M, N (Bijoy/OCR) | A, B, C, D | 1, 2, 3, 4 | ১, ২, ৩, ৪
    """
    if not opt_str:
        return "A"
    clean = opt_str.strip().strip("()[]{}.-:/ ").upper()
    
    # Direct mappings
    bengali_map = {
        "ক": "A", "খ": "B", "গ": "C", "ঘ": "D",
        "K": "A", "L": "B", "M": "C", "N": "D",
        "A": "A", "B": "B", "C": "C", "D": "D",
        "১": "A", "২": "B", "৩": "C", "৪": "D",
        "1": "A", "2": "B", "3": "C", "4": "D",
        "I": "A", "II": "B", "III": "C", "IV": "D",
    }
    
    for key, val in bengali_map.items():
        if clean == key or clean.startswith(key):
            return val
            
    return "A"


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts text paragraphs and table contents from a .docx file.
    Critically preserves tabs (<w:tab/>), line breaks (<w:br/>, <w:cr/>),
    and table cell boundaries so option splits are never lost.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            xml_content = zf.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            
            def extract_node_text(node):
                chunks = []
                for elem in node.iter():
                    tag = elem.tag.split("}")[-1]
                    if tag == "t" and elem.text:
                        chunks.append(elem.text)
                    elif tag == "tab":
                        chunks.append("    ")
                    elif tag in ("br", "cr"):
                        chunks.append("\n")
                return "".join(chunks)

            output_lines = []
            
            # Find document body
            body = tree.find(".//w:body", namespaces)
            if body is None:
                body = tree

            for child in body:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    p_text = extract_node_text(child).strip()
                    if p_text:
                        output_lines.append(p_text)
                elif tag == "tbl":
                    # Extract table rows
                    for row in child.findall(".//w:tr", namespaces):
                        cell_texts = []
                        for cell in row.findall(".//w:tc", namespaces):
                            c_text = extract_node_text(cell).strip()
                            if c_text:
                                cell_texts.append(c_text)
                        if cell_texts:
                            # Join cells with 4 spaces to mimic tabs
                            output_lines.append("    ".join(cell_texts))
                            
            return "\n".join(output_lines)
    except Exception as e:
        # Fallback to plain decoding
        return file_bytes.decode("utf-8", errors="ignore")


def parse_mcq_text(raw_text: str, encoding_mode: str = "auto") -> list[dict]:
    """
    High-accuracy parser for raw Bengali (Avro & Bijoy) & English MCQ text.
    - If encoding_mode is 'bijoy' or auto-detected as Bijoy/SutonnyMJ, automatically converts to Avro/Unicode Bengali!
    - Handles inline & multi-line options (ক, খ, গ, ঘ or K, L, M, N or A, B, C, D or (1), (2), (3), (4))
    - Auto-extracts correct answers and explanations
    """
    if not raw_text or not raw_text.strip():
        return []

    # Auto-convert Bijoy (SutonnyMJ) to Unicode (Avro standard) if detected or requested
    if encoding_mode == "bijoy" or (encoding_mode == "auto" and is_bijoy_text(raw_text)):
        raw_text = convert_bijoy_to_unicode(raw_text)

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []

    # Regex patterns for Question start: e.g. "১।", "1.", "1|", "1)", "(1)", "[1]", "(১)", "প্রশ্ন ১:", "Q1.", "Q1:"
    q_start_regex = re.compile(
        r"^(?:(?:প্রশ্ন|Q(?:uestion)?)\s*[-:]?\s*)?(?:\(|\[)?([০-৯0-9]{1,4})(?:\)|\]|[।|.:\-\/])\s*(.*)",
        re.IGNORECASE | re.UNICODE
    )

    # Regex for options splitters (matches ক. / (ক) / [ক] / ক) / ক: / ক- / K. / (K) / A. / (A) / 1. / (1))
    inline_options_regex = re.compile(
        r"(?:[\s\t]+|^)(?:(?:\(|\[)?([কখগঘKLMNabcdABCD১-৪1-4])(?:\)|\]|[.:।\-\/]))\s*",
        re.UNICODE
    )

    # Single option on a line regex
    single_opt_regex = re.compile(
        r"^(?:\(|\[)?([কখগঘKLMNabcdABCD১-৪1-4])(?:\)|\]|[.:।\-\/])\s*(.*)",
        re.UNICODE
    )

    # Regex for Answer lines
    ans_line_regex = re.compile(
        r"^(?:সঠিক\s*উত্তর|উত্তর|Ans(?:wer)?|Correct\s*Option|Correct\s*Ans)\s*[:।\-]?\s*([কখগঘKLMNabcdABCD১-৪1-4A-Da-d])",
        re.IGNORECASE
    )

    # Regex for Explanation lines
    exp_line_regex = re.compile(
        r"^(?:ব্যাখ্যা|সমাধান|Explanation|Solution|Notes?)\s*[:।\-]?\s*(.*)",
        re.IGNORECASE
    )

    parsed_questions = []
    current_q = None

    def finalize_question(q_data):
        if not q_data:
            return None
        
        q_text = " ".join(q_data.get("question_lines", [])).strip()
        options = q_data.get("options", {})
        correct_opt = q_data.get("correct_option", "A")
        
        # If options weren't parsed as multi-line, check for inline options in question text
        if len(options) < 2 and q_text:
            parts = inline_options_regex.split(q_text)
            if len(parts) >= 5: # text, opt1_lbl, opt1_val, opt2_lbl, opt2_val...
                base_text = parts[0].strip()
                labels_and_vals = []
                for i in range(1, len(parts), 2):
                    lbl = parts[i]
                    val = parts[i+1].strip() if i+1 < len(parts) else ""
                    labels_and_vals.append((lbl, val))
                
                if len(labels_and_vals) >= 2:
                    q_text = base_text
                    for lbl, val in labels_and_vals:
                        letter = map_option_to_letter(lbl)
                        options[letter] = val

        # Clean trailing answers from option D or the last option
        if "D" in options and not q_data.get("has_explicit_ans"):
            last_val = options["D"]
            trailing_ans_match = re.search(r"[\s\t]+(?:Ans(?:wer)?[:।\-]?\s*)?([কখগঘKLMNabcdABCD১-৪1-4A-Da-d])$", last_val, re.IGNORECASE)
            if trailing_ans_match:
                correct_opt = map_option_to_letter(trailing_ans_match.group(1))
                options["D"] = last_val[:trailing_ans_match.start()].strip()

        # If question text exists and at least option A & B exist
        if q_text:
            opt_a = options.get("A", "").strip()
            opt_b = options.get("B", "").strip()
            opt_c = options.get("C", "").strip() or opt_a
            opt_d = options.get("D", "").strip() or opt_b

            # If still missing options but question has text, fill fallbacks so no question is dropped
            if not opt_a and not opt_b:
                opt_a = "অপশন ক"
                opt_b = "অপশন খ"
                opt_c = "অপশন গ"
                opt_d = "অপশন ঘ"

            return {
                "question_text": q_text,
                "option_a": opt_a,
                "option_b": opt_b,
                "option_c": opt_c,
                "option_d": opt_d,
                "correct_option": correct_opt,
                "explanation": q_data.get("explanation", "").strip(),
                "marks": q_data.get("marks", 1.0),
                "order": len(parsed_questions) + 1,
            }
        return None

    i = 0
    while i < len(lines):
        line = lines[i]

        # 1. Check if line starts a new question
        q_match = q_start_regex.match(line)
        if q_match:
            # Finalize previous question
            finalized = finalize_question(current_q)
            if finalized:
                parsed_questions.append(finalized)

            q_first_line = q_match.group(2).strip()
            current_q = {
                "question_lines": [q_first_line] if q_first_line else [],
                "options": {},
                "correct_option": "A",
                "explanation": "",
                "marks": 1.0,
                "order": len(parsed_questions) + 1,
                "has_explicit_ans": False,
            }
            i += 1
            continue

        if current_q is None:
            # Initial text before numbered question start
            current_q = {
                "question_lines": [line],
                "options": {},
                "correct_option": "A",
                "explanation": "",
                "marks": 1.0,
                "order": len(parsed_questions) + 1,
                "has_explicit_ans": False,
            }
            i += 1
            continue

        # 2. Check for explicit Answer line
        ans_match = ans_line_regex.match(line)
        if ans_match:
            current_q["correct_option"] = map_option_to_letter(ans_match.group(1))
            current_q["has_explicit_ans"] = True
            i += 1
            continue

        # 3. Check for Explanation line
        exp_match = exp_line_regex.match(line)
        if exp_match:
            current_q["explanation"] = exp_match.group(1).strip()
            i += 1
            continue

        # 4. Check for inline options on the current line (e.g., "ক. অপশন ১  খ. অপশন ২  গ. অপশন ৩  ঘ. অপশন ৪  খ")
        parts = inline_options_regex.split(" " + line)
        if len(parts) >= 5: # text, opt1_lbl, opt1_val, opt2_lbl, opt2_val...
            labels_and_vals = []
            for k in range(1, len(parts), 2):
                lbl = parts[k]
                val = parts[k+1].strip() if k+1 < len(parts) else ""
                labels_and_vals.append((lbl, val))

            if len(labels_and_vals) >= 2:
                for lbl, val in labels_and_vals:
                    letter = map_option_to_letter(lbl)
                    current_q["options"][letter] = val
                
                # Check trailing answer at the end of the line
                last_val = labels_and_vals[-1][1]
                trailing_ans_match = re.search(r"[\s\t]+(?:Ans(?:wer)?[:।\-]?\s*)?([কখগঘKLMNabcdABCD১-৪1-4A-Da-d])$", last_val, re.IGNORECASE)
                if trailing_ans_match:
                    last_letter = map_option_to_letter(labels_and_vals[-1][0])
                    current_q["correct_option"] = map_option_to_letter(trailing_ans_match.group(1))
                    current_q["options"][last_letter] = last_val[:trailing_ans_match.start()].strip()
                    current_q["has_explicit_ans"] = True
                
                i += 1
                continue

        # 5. Check for single option on a line (e.g. "ক. অপশন ক" or "(A) Option A")
        single_opt_match = single_opt_regex.match(line)
        if single_opt_match and (len(current_q["options"]) < 4):
            opt_letter = map_option_to_letter(single_opt_match.group(1))
            opt_val = single_opt_match.group(2).strip()

            trailing_ans_match = re.search(r"[\s\t]+(?:Ans(?:wer)?[:।\-]?\s*)?([কখগঘKLMNabcdABCD১-৪1-4A-Da-d])$", opt_val, re.IGNORECASE)
            if trailing_ans_match and (opt_letter == "D" or len(current_q["options"]) == 3):
                current_q["correct_option"] = map_option_to_letter(trailing_ans_match.group(1))
                opt_val = opt_val[:trailing_ans_match.start()].strip()
                current_q["has_explicit_ans"] = True

            current_q["options"][opt_letter] = opt_val
            i += 1
            continue

        # 6. Otherwise, if we haven't started collecting options yet, append to question lines
        if len(current_q["options"]) == 0:
            current_q["question_lines"].append(line)
        else:
            if "D" in current_q["options"]:
                if not current_q["explanation"]:
                    current_q["explanation"] = line
                else:
                    current_q["explanation"] += " " + line
            else:
                last_key = list(current_q["options"].keys())[-1]
                current_q["options"][last_key] += " " + line

        i += 1

    # Finalize last question
    finalized = finalize_question(current_q)
    if finalized:
        parsed_questions.append(finalized)

    return parsed_questions


def parse_csv_file(file_content: str) -> list[dict]:
    """
    Parses CSV format: Question, Option A, Option B, Option C, Option D, Correct Option, Explanation, Marks
    """
    questions = []
    reader = csv.reader(io.StringIO(file_content))
    rows = list(reader)
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    start_idx = 1 if any("question" in h or "প্রশ্ন" in h for h in header) else 0

    for idx, row in enumerate(rows[start_idx:], start=1):
        if not row or len(row) < 3:
            continue
        q_text = row[0].strip()
        opt_a = row[1].strip() if len(row) > 1 else ""
        opt_b = row[2].strip() if len(row) > 2 else ""
        opt_c = row[3].strip() if len(row) > 3 else ""
        opt_d = row[4].strip() if len(row) > 4 else ""
        correct = map_option_to_letter(row[5]) if len(row) > 5 else "A"
        exp = row[6].strip() if len(row) > 6 else ""
        try:
            marks = float(row[7]) if len(row) > 7 and row[7].strip() else 1.0
        except ValueError:
            marks = 1.0

        if q_text and opt_a and opt_b:
            questions.append({
                "question_text": q_text,
                "option_a": opt_a,
                "option_b": opt_b,
                "option_c": opt_c or opt_a,
                "option_d": opt_d or opt_b,
                "correct_option": correct,
                "explanation": exp,
                "marks": marks,
                "order": len(questions) + 1,
            })

    return questions


def parse_json_file(file_content: str) -> list[dict]:
    """
    Parses JSON array of MCQ questions.
    """
    try:
        data = json.loads(file_content)
        if isinstance(data, dict) and "questions" in data:
            data = data["questions"]
        if not isinstance(data, list):
            return []

        questions = []
        for item in data:
            if not isinstance(item, dict):
                continue
            q_text = item.get("question_text") or item.get("question") or item.get("title") or ""
            opt_a = item.get("option_a") or item.get("a") or item.get("opt_a") or ""
            opt_b = item.get("option_b") or item.get("b") or item.get("opt_b") or ""
            opt_c = item.get("option_c") or item.get("c") or item.get("opt_c") or ""
            opt_d = item.get("option_d") or item.get("d") or item.get("opt_d") or ""
            correct = map_option_to_letter(item.get("correct_option") or item.get("answer") or item.get("ans") or "A")
            exp = item.get("explanation") or item.get("solution") or ""
            try:
                marks = float(item.get("marks", 1.0))
            except (ValueError, TypeError):
                marks = 1.0

            if q_text and opt_a and opt_b:
                questions.append({
                    "question_text": q_text.strip(),
                    "option_a": opt_a.strip(),
                    "option_b": opt_b.strip(),
                    "option_c": opt_c.strip() or opt_a.strip(),
                    "option_d": opt_d.strip() or opt_b.strip(),
                    "correct_option": correct,
                    "explanation": exp.strip(),
                    "marks": marks,
                    "order": len(questions) + 1,
                })
        return questions
    except Exception:
        return []


def parse_uploaded_file_or_text(file_obj=None, raw_text: str = "", encoding_mode: str = "auto") -> list[dict]:
    """
    Universal dispatcher that handles file upload (txt, docx, csv, json) or direct text.
    Supports 'auto', 'unicode' (Avro), and 'bijoy' (SutonnyMJ) encoding modes.
    """
    if file_obj:
        filename = getattr(file_obj, "name", "").lower()
        file_bytes = file_obj.read()
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        if filename.endswith(".docx"):
            text = extract_text_from_docx(file_bytes)
            return parse_mcq_text(text, encoding_mode=encoding_mode)
        elif filename.endswith(".csv"):
            text = file_bytes.decode("utf-8-sig", errors="ignore")
            return parse_csv_file(text)
        elif filename.endswith(".json"):
            text = file_bytes.decode("utf-8-sig", errors="ignore")
            return parse_json_file(text)
        else:
            # .txt, .doc, or plain text
            text = file_bytes.decode("utf-8-sig", errors="ignore")
            return parse_mcq_text(text, encoding_mode=encoding_mode)

    if raw_text:
        return parse_mcq_text(raw_text, encoding_mode=encoding_mode)

    return []


def to_bengali_numeral(n) -> str:
    eng_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return str(n).translate(eng_to_bn)


def map_letter_to_bengali_option(letter: str) -> str:
    mapping = {"A": "ক", "B": "খ", "C": "গ", "D": "ঘ"}
    return mapping.get(str(letter).upper(), "ক")


def generate_exam_txt(exam) -> str:
    """
    Generates a cleanly formatted Bengali/English text question paper
    matching the standard exam format.
    """
    lines = []
    lines.append(f"পরীক্ষা: {exam.title}")
    if exam.course:
        lines.append(f"কোর্স: {exam.course.title}")
    lines.append(f"সময়: {to_bengali_numeral(exam.duration_minutes)} মিনিট | পূর্ণমান: {to_bengali_numeral(int(exam.calculated_total_marks))} | পাস মার্ক: {to_bengali_numeral(int(exam.pass_mark))}% | নেগেটিভ মার্কিং: {to_bengali_numeral(exam.negative_mark_per_question)}")
    if exam.description:
        lines.append(f"নির্দেশনা: {exam.description}")
    lines.append("=" * 70)
    lines.append("")

    questions = exam.questions.all().order_by("order", "id")
    for idx, q in enumerate(questions, 1):
        bn_num = to_bengali_numeral(idx)
        lines.append(f"{bn_num}। {q.question_text}")
        
        correct_bn = map_letter_to_bengali_option(q.correct_option)
        opt_line = f"ক. {q.option_a}    খ. {q.option_b}    গ. {q.option_c}    ঘ. {q.option_d}    {correct_bn}"
        lines.append(opt_line)
        if q.explanation:
            lines.append(f"ব্যাখ্যা: {q.explanation}")
        lines.append("")

    return "\n".join(lines)


def generate_exam_csv(exam) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Question", "Option A", "Option B", "Option C", "Option D", "Correct Option", "Explanation", "Marks"])
    
    for q in exam.questions.all().order_by("order", "id"):
        writer.writerow([
            q.question_text,
            q.option_a,
            q.option_b,
            q.option_c,
            q.option_d,
            map_letter_to_bengali_option(q.correct_option),
            q.explanation or "",
            q.marks
        ])
        
    return output.getvalue()


def generate_exam_json(exam) -> str:
    items = []
    for q in exam.questions.all().order_by("order", "id"):
        items.append({
            "order": q.order,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "correct_option_bn": map_letter_to_bengali_option(q.correct_option),
            "explanation": q.explanation or "",
            "marks": q.marks
        })
    return json.dumps({
        "exam_title": exam.title,
        "total_questions": len(items),
        "duration_minutes": exam.duration_minutes,
        "pass_mark": exam.pass_mark,
        "questions": items
    }, ensure_ascii=False, indent=2)
