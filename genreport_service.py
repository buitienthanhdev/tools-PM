"""
GenReport Service - Word Document Generator & Ollama AI Integration
Generates professional Vietnamese work reports from user's raw notes.
Uses Ollama qwen3:32b with a professional system prompt to expand terse notes
into detailed, expert-level corporate report content.
"""

import json
import re
import uuid
from pathlib import Path

import docx
import requests

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
TEMPLATE_PATH = BASE_DIR / "templates" / "report_template.docx"
DESKTOP_TEMPLATE = Path(
    r"C:\Users\TIEN THANH\Desktop\BÁO CÁO TUẦN\Báo cáo công việc T7.01.08.2026 BÙI TIẾN THÀNH.docx"
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:32b"

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


def call_ollama_qwen(prompt_text, system_text=None, timeout=180):
    """
    Calls local Ollama qwen3:32b with system prompt + user prompt.
    Returns the raw text response.
    """
    if system_text is None:
        system_text = SYSTEM_PROMPT + "\n\n" + REPORT_SYSTEM_PROMPT

    payload = {
        "model": MODEL_NAME,
        "system": system_text,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.35, "top_p": 0.9, "num_predict": 4000},
    }
    try:
        print(f"[Ollama LLM] Sending prompt to {MODEL_NAME}...")
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            print(f"[Ollama Error] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(
            f"[Ollama Warning] LLM call failed ({type(e).__name__}). Using smart fallback."
        )
        return None


def extract_json_from_llm(raw_text):
    """
    Robustly extract JSON object from LLM output which may contain thinking/preamble text.
    Handles <think>...</think> tags and other preamble before JSON.
    """
    if not raw_text:
        return None

    # Remove thinking blocks
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # Try to find JSON object
    # First try: look for ```json ... ```
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except Exception:
            pass

    # Second try: find the last/largest { ... } block
    brace_start = raw_text.rfind("{")
    if brace_start == -1:
        brace_start = raw_text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(raw_text)):
            if raw_text[i] == "{":
                depth += 1
            elif raw_text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw_text[brace_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # Try fixing common issues
                        fixed = candidate.replace("\n", "\\n").replace("\r", "")
                        try:
                            return json.loads(fixed)
                        except Exception:
                            break

    return None


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

    raw_response = call_ollama_qwen(prompt, timeout=240)
    if not raw_response:
        print("[GenReport] Ollama unavailable, using smart rule-based expansion...")
        return None

    parsed = extract_json_from_llm(raw_response)
    if parsed and "daily_tasks" in parsed and "general_summary" in parsed:
        print(f"[GenReport AI] ✅ Successfully enriched report with {MODEL_NAME}!")
        return parsed
    else:
        print(f"[GenReport AI] JSON parse failed. Raw snippet: {raw_response[:400]}")
        return None


def smart_expand_note(raw_note, progress):
    """
    Rule-based smart expansion of a raw note into a professional result description.
    Used as fallback when Ollama fails or times out.
    """
    note = raw_note.strip()
    p = int(re.search(r"\d+", progress).group()) if re.search(r"\d+", progress) else 100

    # Professional content map — ORDERED list of tuples: most specific rules first, generic AFP last
    expansions = [
        (
            r"RAG|BM25|vector search|Retrieval-Augmented",
            f"Thử nghiệm nâng cấp hệ thống RAG (Retrieval-Augmented Generation) sử dụng AI Local Qwen 3.6 (Ollama) làm mô hình suy luận chính. Xây dựng dữ liệu sơn dạng JSON, kết hợp Rule Engine, Knowledge Graph và thuật toán BM25 (Vector Search + Ranking) để đánh giá khả năng gợi ý sản phẩm sơn. Đạt {p}%, cần bổ sung thêm ràng buộc nghiệp vụ.",
        ),
        (
            r"flowchart|sơ đồ|flow",
            "Xây dựng và hoàn thiện các Flowchart mô tả ảnh hưởng của các yếu tố bên ngoài (Chính phủ, Học thuật, Công nghệ, Thời tiết) đến kiến trúc và định hướng phát triển dự án AFP.",
        ),
        (
            r"diện tích.*object|object.*diện tích|logic.*diện tích|sửa.*diện tích",
            f"Chỉnh sửa thuật toán tính diện tích các Object trong mô hình 3D. Đã xử lý khoảng {p}% logic; các Object chưa có Category sẽ được AI nội suy, độ chính xác phụ thuộc vào chất lượng phân loại.",
        ),
        (
            r"Ba Son",
            "Thực hiện khảo sát thực tế tại khu vực Ba Son phục vụ nghiên cứu dự án, thu thập dữ liệu không gian và yêu cầu kỹ thuật thực địa.",
        ),
        (
            r"KTS|kiến trúc sư|Phụng",
            "Trao đổi với kiến trúc sư để thu thập yêu cầu nghiệp vụ, bổ sung kinh nghiệm thực tế vào thiết kế hệ thống.",
        ),
        (
            r"anh Tú|bức tranh hệ thống|lộ trình|kiến trúc.*họ p|họp.*kiến trúc",
            "Họp với cấp trên để làm rõ kiến trúc tổng thể của hệ thống AFP, xác định lộ trình triển khai khả thi cho các module chính.",
        ),
        (
            r"Marketing|chiến dịch",
            "Tham gia họp về chiến dịch Marketing mới, thảo luận định hướng phối hợp giữa các bộ phận.",
        ),
        (
            r"Rule Engine|Knowledge Graph",
            "Tìm hiểu Rule Engine và Knowledge Graph, đánh giá khả năng tích hợp vào kiến trúc AFP để nâng cao khả năng suy luận có cấu trúc.",
        ),
        (
            r"Object Model",
            "Nghiên cứu tầm quan trọng của Object Model trong kiến trúc hệ thống AFP, làm nền tảng mở rộng và suy luận.",
        ),
        (
            r"Database|cơ sở dữ liệu",
            "Tìm hiểu cách thiết kế Database phù hợp cho hệ thống AI, đánh giá các mô hình lưu trữ dữ liệu hiệu quả.",
        ),
        (
            r"study|tìm hiểu.*AI|nghiên cứu.*mô hình|học.*AI",
            "Nghiên cứu các xu hướng và công nghệ AI hiện đại cần quan tâm; tìm hiểu Database, Object Model và vai trò của Rule Engine, Knowledge Graph đối với kiến trúc AFP nhằm xây dựng nền tảng suy luận có khả năng mở rộng.",
        ),
        (
            r"ràng buộc|constraint",
            f"Bổ sung các ràng buộc nghiệp vụ để nâng cao tính chính xác và độ tinh vi của hệ thống. Đạt {p}%.",
        ),
        (
            r"data.*json|json.*data",
            "Xây dựng và cấu trúc dữ liệu sơn dạng JSON, phục vụ quá trình huấn luyện và suy luận của AI Local.",
        ),
        (
            r"lắp.*máy|lắp ráp|phụ.*lắp",
            "Hỗ trợ lắp ráp, cấu hình và kiểm thử máy tính, đảm bảo phần cứng vận hành ổn định.",
        ),
        (r"họp", "Tham gia họp nội bộ, thảo luận tiến độ và định hướng công việc."),
        # AFP generic rule LAST — only matches if nothing else matched above
        (
            r"AFP|ai for finishing",
            "Tiếp tục phát triển hệ thống AI For Finishing Platform (AFP), triển khai các tính năng mới theo đúng kiến trúc đã định.",
        ),
    ]

    for pattern, expansion in expansions:
        if re.search(pattern, note, re.IGNORECASE):
            return expansion

    # Generic expansion
    p_text = f"Đạt {p}%." if p < 100 else "Hoàn thành."
    return f"{note.capitalize()}. {p_text}"


def build_smart_fallback(days_data, full_name, department, start_date, end_date):
    """
    Build a professional report structure from user's parsed notes without Ollama.
    Uses smart rule-based expansion to produce professional content.
    """
    enriched_days = []
    for d in days_data:
        subtasks = []
        for st in d.get("subtasks", []):
            raw = st.get("content", "")
            prog = st.get("progress", "100%")
            result = smart_expand_note(raw, prog)

            # Use full content as title (no truncation)
            title = raw

            p_num = (
                int(re.search(r"\d+", prog).group()) if re.search(r"\d+", prog) else 100
            )
            note = (
                "Hoàn thành"
                if p_num >= 100
                else ("Cần tiếp tục tối ưu" if p_num >= 70 else "Đang nghiên cứu")
            )

            subtasks.append(
                {"content": title, "result": result, "progress": prog, "note": note}
            )

        # Build day label with date — only once, not duplicated
        date_str = d.get("date_str", "")
        day_name = d.get("day", "")
        day_label = f"{day_name} ({date_str})" if date_str else day_name

        enriched_days.append(
            {
                "day_idx": d["day_idx"],
                "day": day_name,
                "date_str": date_str,
                "day_label": day_label,
                "subtasks": subtasks,
            }
        )

    # Build general summary — scan results for keywords to make it more meaningful
    task_count = sum(
        len(d.get("subtasks", [])) for d in enriched_days if d.get("subtasks")
    )
    all_raw = " ".join(n["raw"] for d in days_data for n in d.get("raw_notes", []))
    topics = []
    if re.search(r"AFP|ai for finishing|RAG|BM25", all_raw, re.IGNORECASE):
        topics.append("phát triển hệ thống AI For Finishing Platform (AFP)")
    if re.search(r"study|nghiên cứu|tìm hiểu", all_raw, re.IGNORECASE):
        topics.append("nghiên cứu công nghệ AI")
    if re.search(r"khảo sát|Ba Son|KTS|kiến trúc", all_raw, re.IGNORECASE):
        topics.append("khảo sát thực tế và thu thập yêu cầu nghiệp vụ")
    if re.search(r"flowchart|sơ đồ", all_raw, re.IGNORECASE):
        topics.append("xây dựng Flowchart kiến trúc hệ thống")
    if re.search(r"họp.*Tú|Marketing|họp", all_raw, re.IGNORECASE):
        topics.append("họp định hướng và phối hợp liên bộ phận")

    topic_str = (
        ", ".join(topics)
        if topics
        else "phát triển hệ thống, nghiên cứu công nghệ và họp định hướng"
    )
    summary = (
        (
            f"Trong tuần tập trung triển khai các công việc chính bao gồm {topic_str}. "
            f"Song song với việc phát triển hệ thống, tiếp tục khảo sát thực tế, nghiên cứu các công nghệ AI mới "
            f"nhằm nâng cao chất lượng tư vấn và khả năng suy luận của AI."
        )
        if len(topics) >= 2
        else (
            f"Trong tuần tập trung triển khai {task_count} đầu công việc chính bao gồm {topic_str}, "
            f"đảm bảo tiến độ và chất lượng theo kế hoạch đề ra."
        )
    )

    # Build section 3 (project progress bullets)
    s3 = []
    for d in enriched_days:
        for st in d.get("subtasks", []):
            if st.get("result"):
                s3.append(st["result"])

    # Build section 4 (short evaluation) — use results text not raw content
    s4 = []
    done = [
        st
        for d in enriched_days
        for st in d.get("subtasks", [])
        if st.get("progress", "100%") == "100%"
    ]
    ongoing = [
        st
        for d in enriched_days
        for st in d.get("subtasks", [])
        if st.get("progress", "100%") != "100%"
    ]
    for st in done[:5]:
        # Use the expanded result text for evaluation
        result_text = st.get("result", st["content"])
        s4.append(f"• {result_text}")
    for st in ongoing:
        p = st.get("progress", "?%")
        result_text = st.get("result", st["content"])
        s4.append(f"• Đang thực hiện ({p}): {result_text} — cần tiếp tục tối ưu.")

    # Build section 5 (next week plan) — use results as basis, not raw truncated content
    s5 = []
    for st in ongoing:
        result_text = st.get("result", st["content"])
        # Extract first sentence as basis for next week plan
        first_sentence = (
            result_text.split(".")[0] if "." in result_text else result_text
        )
        s5.append(f"Tiếp tục hoàn thiện: {first_sentence}.")
    # Add standard items
    if re.search(r"AFP|RAG|BM25", all_raw, re.IGNORECASE):
        s5.append(
            "Hoàn thiện kiến trúc tổng thể AFP và xây dựng lộ trình triển khai các module chính."
        )
        s5.append(
            "Tiếp tục huấn luyện và tối ưu RAG với dữ liệu sơn và dữ liệu nghiệp vụ."
        )
    s5.append(
        "Tiếp tục nghiên cứu các công nghệ AI mới phục vụ định hướng phát triển lâu dài của hệ thống."
    )

    return {
        "general_summary": summary,
        "daily_tasks": enriched_days,
        "section_3_items": (
            s3[:8]
            if s3
            else [
                "Hoàn thành các nhiệm vụ công việc theo đúng yêu cầu đề ra trong tuần."
            ]
        ),
        "section_4_items": (
            s4[:8]
            if s4
            else ["Đảm bảo tiến độ và chất lượng công việc theo đúng kế hoạch."]
        ),
        "section_5_items": s5[:6],
    }


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

    # --- Step 2: Enrich with Ollama AI or smart fallback ---
    print("[GenReport] Step 2: Enriching content with Ollama Qwen 3.6 AI...")
    enriched = enrich_with_ollama(
        days_data, start_date, end_date, full_name, position, department, company
    )

    if enriched is None:
        print("[GenReport] Step 2b: Using smart rule-based expansion as fallback...")
        enriched = build_smart_fallback(
            days_data, full_name, department, start_date, end_date
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
        # Build day_label only if not already set by fallback
        if not ed.get("day_label"):
            date_str = ed.get("date_str", "")
            day_name = ed.get("day", "")
            ed["day_label"] = f"{day_name} ({date_str})" if date_str else day_name

    # --- Step 3: Fill Word template ---
    print("[GenReport] Step 3: Filling Word template...")
    target_template = DESKTOP_TEMPLATE if DESKTOP_TEMPLATE.exists() else TEMPLATE_PATH
    if not target_template.exists():
        raise FileNotFoundError(f"Template file not found at {target_template}")

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
