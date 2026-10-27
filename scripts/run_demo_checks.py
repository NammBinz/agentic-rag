"""15 initial demo cases through Flask. Not an official research evaluation."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from agentic_rag.server import create_app
from agentic_rag.provider import Settings

CASES=[
 {'id':'D01','question':'IT320 tên gì, mấy tín chỉ?','status':'evidence_found','contains':['Python','3'],'sources':['COURSE-IT320']},
 {'id':'D02','question':'Phát triển ứng dụng với Python có bao nhiêu tín chỉ?','status':'evidence_found','contains':['3'],'sources':['COURSE-IT320']},
 {'id':'D03','question':'IT320 yêu cầu môn nào? Môn đó yêu cầu gì?','status':'recorded_conditions','contains':['CS122','CS121'],'sources':['COURSE-IT320','COURSE-CS122','COURSE-CS121']},
 {'id':'D04','question':'IS330 mấy tín chỉ và điều kiện gì?','status':'recorded_conditions','contains':['IS224','2 tín chỉ'],'sources':['COURSE-IS330']},
 {'id':'D05','question':'Điều kiện được ghi cho IT499 là gì?','status':'recorded_conditions','contains':['100','IP406','4,0','7,0'],'sources':['COURSE-IT499']},
 {'id':'D06','question':'Kiểm tra tiên quyết IT499','profile':{'credits':100,'grades':{'IP406':4},'average':7},'status':'satisfied_in_snapshot','contains':['không xác nhận'],'sources':['COURSE-IT499']},
 {'id':'D07','question':'Kiểm tra tiên quyết IT499','profile':{'credits':99,'grades':{'IP406':4},'average':7},'status':'not_met_in_snapshot','contains':['99'],'sources':['COURSE-IT499']},
 {'id':'D08','question':'Kiểm tra tiên quyết IT499','status':'needs_input','contains':['hồ sơ'],'sources':['COURSE-IT499']},
 {'id':'D09','question':'CS121 có tiên quyết gì? Có đăng ký ngay không?','status':'insufficient_data','contains':['trống'],'sources':['COURSE-CS121']},
 {'id':'D10','question':'Kiểm tra tiên quyết IT320','profile':{'completed':['CS122']},'status':'insufficient_data','contains':['chưa xác minh'],'sources':['COURSE-IT320']},
 {'id':'D11','question':'AD219 yêu cầu môn nào? Tra chuỗi tiên quyết','status':'insufficient_data','contains':['AD213'],'sources':['COURSE-AD219']},
 {'id':'D12','question':'K38 dùng bảng K37 được không?','status':'out_of_scope','contains':['K37'],'sources':[]},
 {'id':'D13','question':'Kỳ này còn lớp, còn chỗ không; học phí hiện tại bao nhiêu?','status':'insufficient_data','contains':['Chưa có'],'sources':[]},
 {'id':'D14','question':'ZZ999 yêu cầu môn nào?','status':'insufficient_data','contains':['snapshot'],'sources':[]},
 {'id':'D15','question':'Tôi đủ điều kiện tốt nghiệp chưa?','status':'insufficient_data','contains':['Chưa có'],'sources':[]},
]

def main():
    client=create_app(Settings()).test_client()
    results=[]
    for case in CASES:
        payload={k:case[k] for k in ('question','profile') if k in case}
        payload.update(mode='agent',cohort='K37',curriculum_id='CNTT-2024')
        response=client.post('/api/chat',json=payload)
        r=response.json
        source_ids={c['id'] for c in r.get('citations',[])}
        passed=(response.status_code==200 and r['status']==case['status']
                and all(t in r['answer'] for t in case['contains'])
                and set(case['sources'])<=source_ids
                and r['metrics']['extra_retrieval_rounds']<=1 and r['metrics']['retrieval_rounds']<=2)
        results.append({'id':case['id'],'passed':passed,'input':payload,'expected':case,'output':r})
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {r.get('status')} — {case['question']}")
    (ROOT/'docs'/'demo_results.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in results)+'\n',encoding='utf-8')
    print(f"{sum(r['passed'] for r in results)}/{len(results)} initial demo cases; not research metrics.")
    return 0 if all(r['passed'] for r in results) else 1
if __name__=='__main__': sys.exit(main())
