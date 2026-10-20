"""
GenReport Service - Word Document Generator & Ollama AI Integration
Generates professional Vietnamese work reports from user's raw notes.
Uses the local Ollama model from core.config (models.genreport) with a professional system prompt to expand terse notes
into detailed, expert-level corporate report content.
"""

import json
import re
import uuid
from pathlib import Path

import docx

from core import config as hubcfg
from core import llm

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
TEMPLATE_PATH = BASE_DIR / "templates" / "report_template.docx"


SYSTEM_PROMPT = """You are Qwen, a senior AI engineer, software architect, technical writer, researcher, and reasoning assistant.

Core Objective:
Produce answers with maximum intelligence, accuracy, structure, and usefulness.
Always optimize for: Correctness > Reasoning > Completeness > Clarity > Practicality > Efficiency.
Never optimize for being short.

General Rules:
Always understand the user's real intent before answering.
Infer context, relationships, implicit meaning, and missing but obvious information — never invent facts.
Expand ideas naturally while preserving the original meaning.
Write like an experienced engineer or consultant. Never answer like a chatbot.

Writing Style:
Write naturally. Avoid robotic wording. Avoid repetitive phrases. Prefer semantic variation.
Merge related ideas into coherent paragraphs.
When appropriate, replace "làm" with "phát triển", "triển khai", "hoàn thiện", "nghiên cứu" according to context.
Do not overuse passive voice.

Text Expansion:
When given short notes, expand them into professional writing.
Example — Input: "Họp khách hàng." → Output: "Tham gia cuộc họp với khách hàng nhằm trao đổi tiến độ dự án, xác nhận các yêu cầu hiện tại và thống nhất các hạng mục cần triển khai trong giai đoạn tiếp theo."
Do not add fictional facts. Only expand logically.

Report Generation:
Write professionally. Maintain consistent tone. Merge duplicated ideas.
Convert bullet notes into complete sentences.
Highlight objectives, implementation, progress and remaining work.
When suitable, infer business value, technical purpose, engineering impact — without inventing events.

Document Improvement:
If user provides raw notes, rewrite into professional documentation instead of merely correcting grammar.
Improve flow, cohesion, clarity while preserving meaning.

Output Quality:
Before finalizing, verify: Is the answer complete? Is anything redundant? Can wording be more natural? Can ideas be organized better? If yes, improve before answering.
Always produce the highest quality answer possible."""

REPORT_SYSTEM_PROMPT = """Chuyển các ghi chú thành báo cáo doanh nghiệp chuyên nghiệp.

Yêu cầu:
- Không được bịa thông tin.
- Được phép diễn đạt lại cho chuyên nghiệp.
- Được phép mở rộng câu nếu hợp lý.
- Giữ nguyên ý nghĩa và tiến độ (%) của người dùng.
- Không được bỏ sót ý.
- Viết giống báo cáo của doanh nghiệp lớn.
- Văn phong tự nhiên, không AI.
- Mỗi công việc từ 2–5 câu.
- Nếu nội dung quá ngắn, suy luận hợp lý để bổ sung mục đích hoặc giá trị công việc nhưng không tạo ra sự kiện mới.
- Ưu tiên dùng các động từ như: nghiên cứu, phát triển, triển khai, tối ưu, hoàn thiện, đánh giá, phân tích, khảo sát, xây dựng, thử nghiệm.
- Trả về JSON hợp lệ duy nhất, không có text nào khác ngoài JSON."""


def parse_raw_notes(raw_text):
    """
    Parse user's raw notes into structured list of days + subtasks.
    Handles both free-form text and Sheet format.
    """
    if not raw_text or not raw_text.strip():
        return []

    days_data = []
    current_day = None

    for line in raw_text.splitlines():
        line_s = line.strip()
        if not line_s:
            continue

        # Match day header: "Thứ 2", "Thứ 2 (03/08/2026):", etc.
        day_match = re.match(
            r"^(Thứ\s+[2-7đ]|Thứ\s+(?:hai|ba|tư|năm|sáu|bảy)|Chủ\s+Nhật)\s*(?:\([^)]+\))?\s*:?\s*",
            line_s,
            re.IGNORECASE,
        )
        if day_match:
            # group(1) = just "Thứ 2", group(0) includes optional date part
            day_name_only = day_match.group(1).strip()  # e.g. "Thứ 2"
            # Extract date if present
            date_match = re.search(r"\(([^)]+)\)", line_s)
            date_str = date_match.group(1) if date_match else ""

            current_day = {
                "day_idx": len(days_data) + 1,
                "day": day_name_only,
                "date_str": date_str,
                "raw_notes": [],
                "subtasks": [],
            }
            days_data.append(current_day)

            # Inline content after colon
            remainder = line_s[day_match.end() :].strip()
            if remainder:
                _add_subtask_from_text(current_day, remainder)
        elif line_s.startswith("-") and current_day:
            # Subtask format: "- Task content (%): 40%"
            sub_text = line_s[1:].strip()
            _add_subtask_from_text(current_day, sub_text)
        elif current_day and line_s and not line_s.startswith("#"):
            # Continuation text
            _add_subtask_from_text(current_day, line_s)

    # Fill up to 6 days if fewer
    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
    while len(days_data) < 6:
        idx = len(days_data)
        days_data.append(
            {
                "day_idx": idx + 1,
                "day": day_names[idx],
                "date_str": "",
                "raw_notes": [],
                "subtasks": [],
            }
        )

    return days_data[:6]


def _add_subtask_from_text(day_item, text):
    """Parse a single task text line and append to day_item subtasks."""
    text = text.strip()
    if not text:
        return

    # Extract progress %
    prog = "100%"
    # Pattern: "(%): 80%" or "80%" at end or inline
    prog_match = re.search(r"\(\%\)\s*:\s*([0-9]+\%?)", text)
    if prog_match:
        prog = prog_match.group(1).strip()
        if not prog.endswith("%"):
            prog += "%"
        text = text[: prog_match.start()].strip()
    else:
        # Look for trailing % like "... 80%." or "... 100%"
        trail_match = re.search(r"[\.,\s]([0-9]{1,3}%)\s*[.,]?\s*$", text)
        if trail_match:
            prog = trail_match.group(1)
            text = text[: trail_match.start()].strip()

    if not text:
        return

    note = "Hoàn thành" if "100" in prog else "Đang thực hiện"
    day_item["raw_notes"].append({"raw": text, "progress": prog})
    day_item["subtasks"].append(
        {
            "content": text,
            "result": "",  # Will be filled by AI
            "progress": prog,
            "note": note,
        }
    )


def enrich_with_ollama(
    days_data, start_date, end_date, full_name, position, department, company
):
    """
    Send the parsed user notes to Ollama qwen3:32b for professional expansion.
    Uses the user's system prompt + specialized report prompt for high-quality output.
    """
    # Build structured task list for prompt
    task_lines = []
    for d in days_data:
        notes = d.get("raw_notes", [])
        if notes:
            date_label = (
                f"{d['day']} ({d['date_str']})" if d.get("date_str") else d["day"]
            )
            for n in notes:
                task_lines.append(
                    f"- {date_label} | {n['raw']} | Tiến độ: {n['progress']}"
                )

    tasks_block = "\n".join(task_lines) if task_lines else "(Không có ghi chú)"

    # Build example daily_tasks structure so model knows format
    example_days = []
    for d in days_data:
        example_days.append(
            {
                "day_idx": d["day_idx"],
                "day": d["day"],
                "date_str": d.get("date_str", ""),
                "subtasks": [
                    {
                        "content": n["raw"],
                        "result": "MÔ TẢ KẾT QUẢ CHUYÊN NGHIỆP TẠI ĐÂY (2-4 câu)",
                        "progress": n["progress"],
                        "note": (
                            "Hoàn thành" if "100" in n["progress"] else "Đang thực hiện"
                        ),
                    }
                    for n in d.get("raw_notes", [])
                    if n.get("raw")
                ],
            }
        )

    prompt = f"""THÔNG TIN NHÂN VIÊN:
Họ tên: {full_name} | Chức vụ: {position} | Phòng: {department} | Công ty: {company}
Thời gian: {start_date} đến {end_date}

GHI CHÚ CÔNG VIỆC THÔ (của nhân viên):
{tasks_block}

YÊU CẦU:
Dựa ĐÚNG trên ghi chú trên, tạo báo cáo theo cấu trúc JSON sau.
- Trường "result": mô tả kết quả thực hiện 2-4 câu, chuyên nghiệp, kỹ thuật, tự nhiên
- Trường "content": tiêu đề ngắn gọn cho công việc đó
- "general_summary": 2-3 câu tổng hợp tình hình chung cả tuần
- "section_3_items": list các gạch đầu dòng tiến độ dự án (1 câu/bullet, đầy đủ các việc)
- "section_4_items": list đánh giá ngắn (điểm đạt được và lưu ý)
- "section_5_items": list kế hoạch tuần tới dựa trên công việc còn dang dở

CHỈ TRẢ VỀ JSON HỢP LỆ, không có text nào khác:

{{
  "general_summary": "...",
  "daily_tasks": {json.dumps(example_days, ensure_ascii=False, indent=2)},
  "section_3_items": ["...", "..."],
  "section_4_items": ["...", "..."],
  "section_5_items": ["...", "..."]
}}"""

    parsed = llm.chat_json(
        hubcfg.model("genreport"),
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + REPORT_SYSTEM_PROMPT,
            },
            {"role": "user", "content": prompt},
        ],
        retries=1,
        num_ctx=16384,
        num_predict=6000,
        temperature=0.35,
        timeout=900,
        name="genreport",
    )
    if "daily_tasks" not in parsed or "general_summary" not in parsed:
        raise llm.LLMError(
            "AI trả về thiếu phần general_summary/daily_tasks, hãy thử lại"
        )
    return parsed


def generate_word_report(data):
    """
    Main entry point: parse user input → enrich with Ollama AI → fill Word template.
    Generates professional Vietnamese work report from user's raw notes.
    """
    # Extract form fields
    company = data.get("company", "CÔNG TY CỔ PHẦN PAINT & MORE")
    department = data.get("department", "Phòng IT-AI")
    full_name = data.get("full_name", "BÙI TIẾN THÀNH")
    position = data.get("position", "Nhân viên AI-IT")
    start_date = data.get("start_date", "")
    end_date = data.get("end_date", "")
    report_date = data.get("report_date", end_date)
    raw_text = data.get("raw_text", "").strip()

    # --- Step 1: Parse user's raw notes ---
    print("[GenReport] Step 1: Parsing user's raw notes...")
    days_data = parse_raw_notes(raw_text)
    has_content = any(d.get("raw_notes") for d in days_data)

    if not has_content:
        print("[GenReport] No task content found in input.")

    # --- Step 2: AI local viết nội dung (lỗi thì báo lỗi, không tự bịa) ---
    if not has_content:
        raise ValueError("Chưa có nội dung công việc nào để viết báo cáo")
    print("[GenReport] Step 2: Enriching content with local AI...")
    enriched = enrich_with_ollama(
        days_data, start_date, end_date, full_name, position, department, company
    )

    # Extract enriched sections
    general_summary = enriched.get("general_summary", "")
    enriched_daily = enriched.get("daily_tasks", days_data)
    s3_items = enriched.get("section_3_items", [])
    s4_items = enriched.get("section_4_items", [])
    s5_items = enriched.get("section_5_items", [])

    # Merge date info if AI stripped it, build day_label exactly once
    for i, ed in enumerate(enriched_daily):
        if (
            i < len(days_data)
            and not ed.get("date_str")
            and days_data[i].get("date_str")
        ):
            ed["date_str"] = days_data[i]["date_str"]
        if not ed.get("day_label"):
            date_str = ed.get("date_str", "")
            day_name = ed.get("day", "")
            ed["day_label"] = f"{day_name} ({date_str})" if date_str else day_name

    # --- Step 3: Fill Word template ---
    print("[GenReport] Step 3: Filling Word template...")
    custom = hubcfg.get().get("genreport_template") or ""
    target_template = (
        Path(custom) if custom and Path(custom).exists() else TEMPLATE_PATH
    )
    if not target_template.exists():
        raise FileNotFoundError(f"Không thấy file mẫu Word: {target_template}")

    doc = docx.Document(str(target_template))

    # Table 0 - Header block
    if len(doc.tables) > 0:
        t0 = doc.tables[0]
        if len(t0.rows) > 0 and len(t0.rows[0].cells) >= 2:
            t0.rows[0].cells[0].text = f"{company}\n{department}"
            t0.rows[0].cells[1].text = (
                f"          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
                f"                           Độc lập – Tự do – Hạnh phúc\n\n"
                f"         Thứ bảy, ngày {report_date}"
            )

    # Paragraphs
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt.startswith("Thời gian"):
            p.text = f"Thời gian: Thứ hai {start_date} đến Thứ bảy {end_date}"
        elif txt.startswith("Họ và tên:"):
            p.text = f"Họ và tên: {full_name}"
        elif txt.startswith("Chức vụ:"):
            p.text = f"Chức vụ: {position}"
        elif txt.startswith("Bộ phận công tác:"):
            p.text = f"Bộ phận công tác: {department}"
        elif txt.startswith("I. TÌNH HÌNH CHUNG"):
            p.text = f"I. TÌNH HÌNH CHUNG\n{general_summary}"

    # Table 1 - Daily work table (6 days)
    if len(doc.tables) > 1:
        t1 = doc.tables[1]
        for day_num in range(1, 7):
            if day_num < len(t1.rows):
                row = t1.rows[day_num]
                ed = (
                    enriched_daily[day_num - 1]
                    if day_num - 1 < len(enriched_daily)
                    else {}
                )
                subtasks = ed.get("subtasks", [])
                day_label = ed.get("day_label", ed.get("day", f"Thứ {day_num + 1}"))

                row.cells[0].text = str(day_num)
                row.cells[1].text = day_label

                if not subtasks:
                    row.cells[2].text = ""
                    row.cells[3].text = ""
                    row.cells[4].text = "100%"
                    row.cells[5].text = "Hoàn thành"
                elif len(subtasks) == 1:
                    st = subtasks[0]
                    row.cells[2].text = st.get("content", "")
                    row.cells[3].text = st.get("result", "")
                    row.cells[4].text = st.get("progress", "100%")
                    row.cells[5].text = st.get("note", "Hoàn thành")
                else:
                    contents = [f"• {st.get('content', '')}" for st in subtasks]
                    results = [f"• {st.get('result', '')}" for st in subtasks]
                    progs = [f"• {st.get('progress', '100%')}" for st in subtasks]
                    notes = list(
                        dict.fromkeys([st.get("note", "Hoàn thành") for st in subtasks])
                    )
                    row.cells[2].text = "\n".join(contents)
                    row.cells[3].text = "\n".join(results)
                    row.cells[4].text = "\n".join(progs)
                    row.cells[5].text = "\n".join(notes)

    # Section III, IV, V via paragraph search
    def fill_section(start_kw, end_kw, items):
        in_section = False
        idx = 0
        for p in doc.paragraphs:
            if start_kw in p.text:
                in_section = True
                continue
            if in_section:
                if end_kw and end_kw in p.text:
                    break
                if idx < len(items):
                    p.text = items[idx]
                    idx += 1

    fill_section("III.", "IV.", s3_items)
    fill_section("IV.", "V.", s4_items)
    fill_section("V.", None, s5_items)

    # Signature block
    if len(doc.tables) > 2:
        t2 = doc.tables[2]
        if len(t2.rows) > 0 and len(t2.rows[0].cells) >= 2:
            t2.rows[0].cells[
                1
            ].text = f"                                Người thực hiện\n\n\n                                {full_name}"

    # Save
    out_filename = f"Bao_cao_cong_viec_{uuid.uuid4().hex[:6]}.docx"
    out_filepath = UPLOAD_DIR / out_filename
    doc.save(str(out_filepath))
    print(f"[GenReport] ✅ Document saved: {out_filename}")

    # Flatten daily_tasks for frontend display
    display_daily = []
    for ed in enriched_daily:
        display_daily.append(
            {
                "day": ed.get("day_label", ed.get("day", "")),
                "day_idx": ed.get("day_idx", 1),
                "subtasks": ed.get("subtasks", []),
            }
        )

    return {
        "filename": out_filename,
        "filepath": str(out_filepath),
        "download_url": f"/uploads/{out_filename}",
        "full_name": full_name,
        "report_date": report_date,
        "general_summary": general_summary,
        "daily_tasks": display_daily,
        "eval_short": "\n".join(s4_items),
        "next_plan_ideas": "\n".join(s5_items),
        "section_3": s3_items,
        "section_4": s4_items,
        "section_5": s5_items,
    }
