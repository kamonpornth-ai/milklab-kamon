"""MilkLab Agent Harness (S2).

Usage:
    python agent_harness.py --cmd "บันทึกขายนนมมี 2 ขวด ขวดละ 65"

รับคำสั่งภาษาไทย ส่งให้ Gemini พร้อม tool schema parse response เป็น tool call
เรียก tool จริง print trace log
"""

import argparse
import datetime
import json
import logging
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ตั้งค่า Logging สำหรับเขียนไฟล์ agent_trace.log
logging.basicConfig(
    filename='agent_trace.log',
    level=logging.INFO,
    format='%(message)s',
    encoding='utf-8'
)

TOOL_SCHEMA = [
  {
    "name": "log_sale",
    "description": "บันทึกการขายลง Google Sheets และส่ง notification",
    "parameters": {
      "type": "object",
      "properties": {
        "menu": { "type": "string", "description": "ชื่อเมนู" },
        "qty": { "type": "integer", "description": "จำนวนที่ขาย" },
        "price": { "type": "number", "description": "ราคาต่อหน่วย" }
      },
      "required": ["menu", "qty", "price"]
    }
  },
  {
    "name": "query_sales",
    "description": "ดูยอดขายของวันที่ระบุ",
    "parameters": {
      "type": "object",
      "properties": {
        "date": { "type": "string", "description": "วันที่ format YYYY-MM-DD" }
      },
      "required": ["date"]
    }
  },
  {
    "name": "send_alert",
    "description": "ส่ง message แจ้งเตือนผ่าน Bot",
    "parameters": {
      "type": "object",
      "properties": {
        "message": { "type": "string", "description": "ข้อความแจ้งเตือน" }
      },
      "required": ["message"]
    }
  }
]

def log_event(event_type: str, message: str):
    """ฟังก์ชันช่วยบันทึก Log ในรูปแบบ YYYY-MM-DD HH:MM | event_type | message"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    log_str = f"{timestamp} | {event_type} | {message}"
    logging.info(log_str)


def parse_command(cmd: str, api_key: str | None = None) -> dict:
    """TODO 1: ส่ง cmd ไป Gemini พร้อม TOOL_SCHEMA ขอให้ตอบเป็น JSON {tool, args}"""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=key)

    system_instruction = f"""
    คุณเป็น AI Router ที่รับคำสั่งภาษาไทยแล้วต้องตอบกลับเป็น JSON เท่านั้น
    เลือกใช้ Tool และดึง Parameters จาก Schema ต่อไปนี้:
    {json.dumps(TOOL_SCHEMA, ensure_ascii=False)}

    รูปแบบคำตอบต้องส่งเป็น JSON ตัวอย่าง:
    {{"tool": "ชื่อ_tool", "args": {{"param1": "value1"}}}}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=cmd,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text.strip())
    except Exception as e:
        raise RuntimeError(f"Parse command failed: {str(e)}")


def dispatch_tool(tool_call: dict) -> str:
    """TODO 2: เรียก tool ตาม tool_call["tool"] ด้วย args จริง พร้อม Guardrail / Input Validation"""
    tool_name = tool_call.get("tool")
    args = tool_call.get("args", {})

    # Guardrail Validation
    if tool_name == "log_sale":
        menu = args.get("menu")
        qty = args.get("qty")
        price = args.get("price")

        # Reject empty menu
        if not menu or not str(menu).strip():
            raise ValueError("menu name cannot be empty")

        # Reject negative or zero qty
        if qty is None or int(qty) <= 0:
            raise ValueError("quantity must be positive")

        if price is None or float(price) < 0:
            raise ValueError("price must be non-negative")

        # จำลองผลลัพธ์การรัน Tool สำเร็จ
        return f"row appended at Sheet (Menu: {menu}, Qty: {qty})"

    elif tool_name == "query_sales":
        date = args.get("date")
        if not date:
            raise ValueError("date is required")
        return f"รายการขายวันที่ {date}: รวม 5 รายการ"

    elif tool_name == "send_alert":
        message = args.get("message")
        if not message or not str(message).strip():
            raise ValueError("message cannot be empty")
        return f"sent alert: {message}"

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, help="คำสั่งภาษาไทย")
    args = parser.parse_args()

    print(f"[USER] {args.cmd}")

    # TODO 3: บันทึก user_input trace log, parse command, dispatch tool และจัดการ error/result
    log_event("user_input", args.cmd)

    try:
        # 1. Parse Command
        tool_call = parse_command(args.cmd)
        
        # บันทึก llm_response ลง trace log
        log_event("llm_response", json.dumps(tool_call, ensure_ascii=False))
        print(f"[LLM]  tool={tool_call.get('tool')} args={tool_call.get('args')}")

        # 2. Dispatch Tool (เรียกใช้เครื่องมือและผ่าน Guardrail)
        result = dispatch_tool(tool_call)

        # บันทึก tool_result ลง trace log
        log_event("tool_result", result)
        print(f"[TOOL] {tool_call.get('tool')} {result}")
        print(f"[USER] ← {result}")

    except Exception as e:
        # บันทึก tool_error ลง trace log
        error_msg = f"{type(e).__name__} {str(e)}"
        log_event("tool_error", error_msg)
        print(f"[ERROR] {error_msg}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
