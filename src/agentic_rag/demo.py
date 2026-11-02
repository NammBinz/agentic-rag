"""Temporary deployment scope; the research engine retains multi-cohort support."""
import re
from .engine import Engine
from .catalog import normalize, mentions_other_program

class DemoEngine(Engine):
    def answer(self, question, mode='agent', cohort='K37', profile=None, **options):
        if not isinstance(question, str) or not question.strip() or len(question) > 3000:
            raise ValueError('Câu hỏi phải có 1–3000 ký tự')
        mentioned = set(re.findall(r'\bK\s*(\d{2,3})\b', question.upper()))
        mentioned.update(re.findall(r'khoa\s+(\d{2,3})\b', normalize(question)))
        versions = set(re.findall(r'CNTT[- ]?(20\d{2})', question.upper()))
        wrong_program = mentions_other_program(question)
        if cohort != 'K37' or mentioned - {'37'} or versions - {'2024'} or wrong_program or mode == 'llm':
            result = super().answer(question, mode='rag', cohort=None)
            result.update(status='out_of_scope', mode=mode, cohort='K37', context=self.catalog.context,
                answer='Bản demo tạm thời chỉ phục vụ K37 — CNTT-2024. Không dùng bảng này thay cho khóa/ngành/phiên bản khác; không bật LLM không RAG trong demo.',
                notice='Phạm vi nghiên cứu CNTT toàn khóa vẫn giữ nguyên; đây là giới hạn triển khai demo.')
            return result
        return super().answer(question, mode, cohort, profile, **options)
