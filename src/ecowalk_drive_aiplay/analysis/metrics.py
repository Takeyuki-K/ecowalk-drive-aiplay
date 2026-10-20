import json
import math
import statistics as st
from pathlib import Path
from ..config import DATA
from ..recording import write_json

def rows(p):
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
def mean(xs): return st.mean(xs) if xs else None
def report(session):
    session=Path(session)
    controls=rows(session/'logs/controls.jsonl'); loc=rows(session/'logs/localization.jsonl')
    events=rows(session/'logs/events.jsonl'); records=rows(session/'logs/results.jsonl')
    expected=json.loads((DATA/'reference/experiment11/expected-results.json').read_text())
    oldmetrics=json.loads((DATA/'reference/experiment11/trial_metrics.json').read_text())
    metrics=[]
    for rec in records:
        result=rec['result'] or {}; name=rec['name']
        cs=[x for x in controls if x['name']==name]; ls=[x for x in loc if x['name']==name]
        gaps=[b['command_wall']-a['command_wall'] for a,b in zip(cs,cs[1:])]
        errors=[x['navigation']['cross_track'] for x in cs if 'cross_track' in x['navigation']]
        cls=[x['navigation']['clearance_m'] for x in cs if 'clearance_m' in x['navigation']]
        moving=[x for x in cs if x['command']['v']!=0 or x['command']['w']!=0]
        stops=[x['reason'] for x in events if x.get('name')==name and x.get('kind')=='neutral']
        verified=False
        if rec['run_id']:
            p=session/'game-runs'/rec['run_id']/'result.json'
            verified=p.exists() and json.loads(p.read_text())==result
        m=dict(name=name,stage=result.get('stage'),outcome=result.get('outcome','unknown'),
            collisions=result.get('collisions'),fall_events=rec['fall_events'],energy_wh=result.get('energy_wh'),
            elapsed_s=result.get('elapsed_s'),average_power_w=result.get('average_power_w'),
            lower_hz=1/mean(gaps) if gaps else None,period_mean_s=mean(gaps),period_max_s=max(gaps,default=None),
            period_p95_s=sorted(gaps)[int(.95*(len(gaps)-1))] if gaps else None,
            max_cross_track_m=max(errors,default=None),rms_cross_track_m=math.sqrt(mean([x*x for x in errors])) if errors else None,
            min_clearance_m=min(cls,default=None),first_command_sim_s=moving[0]['sim_t'] if moving else None,
            neutral_acknowledged=rec['stop']['acknowledged'],stop_reasons=stops,result_verified=verified,error=rec.get('error'))
        metrics.append(m)
    write_json(session/'analysis/metrics.json',metrics)
    text=['# 実験11 固定条件比較','',
          '判定基準（実走前に固定）：9/9完走・衝突0・転倒0・終了中立ACKを必須。Wh平均差±5%、sim時間平均差±10%を比較目安とする。元3回のSDは保証区間ではない。',
          '制御周期は目標20Hz、平均18〜22Hzを目安とし最大・p95も保存。経路誤差は元値との差を報告し、許容corridorを超えないことを確認。','',
          '|Stage|完走/試行|衝突|転倒イベント|Wh 平均±標本SD|元Wh|差%|sim秒 / 元|Hz|最大経路誤差m / 元|停止ACK|',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(x): return '未測定' if x is None else f'{x:.6f}'
    for stage in (1,2,3):
        ms=[m for m in metrics if m['stage']==stage]; old=[m for m in expected if m['stage']==stage]
        om=[m for m in oldmetrics if m['stage']==stage and m['phase']=='final']
        wh=[m['energy_wh'] for m in ms if m['energy_wh'] is not None]; ow=mean([m['energy_wh'] for m in old]); nw=mean(wh)
        elapsed=mean([m['elapsed_s'] for m in ms if m['elapsed_s'] is not None]); ot=mean([m['elapsed_s'] for m in old])
        text.append(f"|{stage}|{sum(m['outcome']=='finished' for m in ms)}/{len(ms)}|{sum(m['collisions'] or 0 for m in ms)}|{sum(m['fall_events'] for m in ms)}|{fmt(nw)} ± {fmt(st.stdev(wh) if len(wh)>1 else None)}|{fmt(ow)}|{fmt((nw/ow-1)*100 if nw is not None else None)}|{fmt(elapsed)} / {fmt(ot)}|{fmt(mean([m['lower_hz'] for m in ms if m['lower_hz'] is not None]))}|{fmt(max((m['max_cross_track_m'] for m in ms if m['max_cross_track_m'] is not None),default=None))} / {fmt(max(m['max_cross_track_m'] for m in om))}|{sum(m['neutral_acknowledged'] for m in ms)}/{len(ms)}|")
    text+=['','## 各試行','', '|試行|結果|Wh|sim秒|平均周期ms|p95 ms|最大ms|最大誤差m|原結果照合|停止理由|', '|---|---|---:|---:|---:|---:|---:|---:|---|---|']
    for m in metrics:
        text.append('|'+ '|'.join([m['name'],m['outcome'],fmt(m['energy_wh']),fmt(m['elapsed_s']),*[fmt(m[k]*1000 if m[k] is not None else None) for k in ('period_mean_s','period_p95_s','period_max_s')],fmt(m['max_cross_track_m']),str(m['result_verified']),', '.join(dict.fromkeys(m['stop_reasons']))])+'|')
    failures=list(session.glob('*.failure.json'))
    assessment=dict(complete_nine=len(metrics)==9 and all(sum(m['stage']==stage for m in metrics)==3 for stage in (1,2,3)),
        all_finished=bool(metrics) and all(m['outcome']=='finished' for m in metrics),
        zero_collisions=bool(metrics) and all(m['collisions']==0 for m in metrics),
        zero_falls=bool(metrics) and all(m['fall_events']==0 for m in metrics),
        stop_ack=bool(metrics) and all(m['neutral_acknowledged'] for m in metrics),
        original_results_verified=bool(metrics) and all(m['result_verified'] for m in metrics),
        no_recorded_failures=not failures and all(not m['error'] for m in metrics),stages={})
    for stage in (1,2,3):
        ms=[m for m in metrics if m['stage']==stage]; old=[m for m in expected if m['stage']==stage]
        def relative(key):
            values=[m[key] for m in ms if m[key] is not None]
            return mean(values)/mean([m[key] for m in old])-1 if values else None
        wh_delta=relative('energy_wh'); time_delta=relative('elapsed_s')
        hz=mean([m['lower_hz'] for m in ms if m['lower_hz'] is not None])
        assessment['stages'][str(stage)]=dict(wh_relative=wh_delta,time_relative=time_delta,
            wh_within_5pct=wh_delta is not None and abs(wh_delta)<=.05,
            time_within_10pct=time_delta is not None and abs(time_delta)<=.1,
            mean_hz_18_to_22=hz is not None and 18<=hz<=22)
    assessment['primary_pass']=all(v for k,v in assessment.items() if k!='stages')
    write_json(session/'analysis/assessment.json',assessment)
    text+=['', '基本条件の判定: '+('PASS' if assessment['primary_pass'] else '未達／試行不足（assessment.jsonを参照）')]

    text+=['',f'失敗記録: {len(failures)}。未完走試行を平均から除外しない。転倒数はstatusで観測したfalse→true遷移数であり、画像だけから推測していない。',
           'JPEGとstatusは非同期。取得開始・受信時刻、状態と画像の時刻差、SHA256をframes.jsonlへ保存。古いJPEGの再送を完全には識別できない。',
           'MuJoCo真値姿勢を使用。Whはゲームの推定23モータ消費量でPC電力ではない。',
           '環境とファイルハッシュ: manifest.json / environment-game.json。実行はwall時計のためCPU負荷と描画・I/Oで差が出る。']
    (session/'analysis/comparison.md').write_text('\n'.join(text)+'\n')
    return metrics
