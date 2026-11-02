"""Deployment scope: the user picks a CNTT cohort first; questions about other scopes are refused."""
import re
from .engine import Engine
from .catalog import SUPPORTED_COHORTS, normalize, mentions_other_program


class DemoEngine(Engine):
    def answer(self, question, mode='agent', cohort=None, profile=None, **options):
        if not isinstance(question, str) or not question.strip() or len(question) > 3000:
            raise ValueError('Câu hỏi phải có 1–3000 ký tự')
        if cohort is None:
            return super().answer(question, mode, None, profile, **options)
        mentioned = set(re.findall(r'\bK\s*(\d{2,3})\b', question.upper()))
        mentioned.update(re.findall(r'khoa\s+(\d{2,3})\b', normalize(question)))
        versions = set(re.findall(r'CNTT[- ]?(20\d{2})', question.upper()))
        selected = cohort[1:] if isinstance(cohort, str) else ''
        frame = (self._frame(cohort) or '')[-4:] if cohort in SUPPORTED_COHORTS else ''
        if (cohort not in SUPPORTED_COHORTS or mentioned - {selected} or versions - {frame}
                or mentions_other_program(question) or mode == 'llm'):
            result = super().answer(question, mode='rag', cohort=None)
            scope = self.for_cohort(cohort).catalog.context if cohort in SUPPORTED_COHORTS else result['context']
            result.update(status='out_of_scope', mode=mode, cohort=cohort, context=scope,
                answer=(f'Bạn đang chọn {cohort} — ngành Công nghệ thông tin. Câu hỏi nhắc khóa, ngành hoặc phiên bản '
                        'chương trình khác; hãy đổi khóa ở đầu trang hoặc hỏi đúng phạm vi. Không dùng dữ liệu khóa này '
                        'thay cho khóa khác; không bật LLM không RAG trong demo.' if cohort in SUPPORTED_COHORTS else
                        'Hãy chọn khóa K35–K39 ngành Công nghệ thông tin trước khi hỏi.'),
                notice='Mỗi khóa dùng đúng chương trình và phiên bản của khóa đó.')
            return result
        return super().answer(question, mode, cohort, profile, **options)

    def _frame(self, cohort):
        # The frame version recorded for the cohort (e.g. CNTT-2023 for K36), even when only provisional.
        bindings = self.for_cohort(cohort).catalog.bindings
        return next((b.get('frame_version') or b.get('curriculum_id') for b in bindings if b.get('cohort') == cohort), None)
