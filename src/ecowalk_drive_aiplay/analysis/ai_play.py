"""AI Play accounting: keep model latency, failures and original game totals visible."""
import argparse
import json
import statistics
from pathlib import Path
from ..config import DATA
from ..recording import write_json
from .metrics import rows

def summarize(sessions,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((DATA/'reference/experiment11/trial_metrics.json').read_text())
    trials=[]
    for session in map(Path,sessions):
        controls=rows(session/'logs/controls.jsonl'); decisions=rows(session/'logs/decisions.jsonl')
        for record in rows(session/'logs/results.jsonl'):
            name=record['name']; result=record['result'] or {}
            own=[c for c in controls if c['name']==name]
            moving=[c for c in own if c['command']['v']!=0 or c['command']['w']!=0]
            first=moving[0]['sim_t'] if moving else None
            state_rows=rows(session/'game-runs'/record['run_id']/'states.jsonl') if record['run_id'] else []
            before=[r for r in state_rows if first is not None and r['t']<first]
            pre=before[-1]['result']['energy_wh'] if before else None
            period=[b['command_wall']-a['command_wall'] for a,b in zip(own,own[1:])]
            active_period=[b['command_wall']-a['command_wall'] for a,b in zip(own,own[1:])
                           if a['decision_id'] is not None and a['decision_id']==b['decision_id']]
            errors=[c['navigation']['cross_track'] for c in own if 'cross_track' in c['navigation']]
            routes=[d for d in decisions if d['name']==name and d['kind']=='route']
            observations=rows(session/'observations'/name/'frames.jsonl')
            observation_period=[b['image_received_wall']-a['image_received_wall'] for a,b in zip(observations,observations[1:])]
            video=session/'video'/name
            val=json.loads((video/'validation.json').read_text()) if (video/'validation.json').exists() else None
            expected=[b for b in baseline if b['phase']=='final' and b['stage']==result.get('stage')]
            basewh=statistics.mean(b['energy_wh'] for b in expected) if expected else None
            trial=dict(session=str(session.resolve()),name=name,stage=result.get('stage'),result=result,
                success=result.get('outcome')=='finished' and result.get('collisions')==0 and record['fall_events']==0,
                fall_events=record['fall_events'],stop=record['stop'],record_error=record['error'],
                first_motion_sim_s=first,pre_motion_energy_wh=pre,
                motion_to_finish_s=result.get('elapsed_s',0)-first if first is not None else None,
                energy_after_first_motion_wh=result.get('energy_wh',0)-pre if pre is not None else None,
                lower_hz=1/statistics.mean(period) if period else None,
                max_control_interval_s=max(period,default=None),max_cross_track_m=max(errors,default=None),
                active_lower_hz=1/statistics.mean(active_period) if active_period else None,
                active_max_control_interval_s=max(active_period,default=None),
                recorded_observation_frames=len(observations),
                observation_hz=1/statistics.mean(observation_period) if observation_period else None,
                decisions=routes,video=val,baseline11_mean_wh=basewh,
                total_wh_difference_pct=100*(result['energy_wh']/basewh-1) if basewh else None,
                baseline11_motion_energy_wh=statistics.mean(b['energy_wh']-b['prestart_wh'] for b in expected) if expected else None,
                baseline11_motion_time_s=statistics.mean(b['movement_to_finish_s'] for b in expected) if expected else None)
            if record['run_id']:
                saved=json.loads((session/'game-runs'/record['run_id']/'result.json').read_text());trial['game_result_matches']=saved==result
            trials.append(trial)
    write_json(output/'ai-play-results.json',trials)
    text=['# Astra AI Play実験結果','',
          '新規観測に基づく上位判断の試験。固定経路再現試験とは条件が異なる。全試行を保存し、静止・判断・権限待ちもゲーム原結果に含める。',
          '「走行開始後」は最初の非中立指令時点で単純に区切った参考値であり、公式ゲーム得点やWhを改変したものではない。','',
          '|試行|Stage|結果|衝突/転倒|全Wh|元実験11平均Whとの差|全sim秒|走行前sim秒|開始後Wh|開始後sim秒|平均Hz|停止ACK/理由|',
          '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    def f(x):return '未測定' if x is None else f'{x:.6f}'
    for t in trials:
        r=t['result'];text.append('|'+ '|'.join([t['name'],str(t['stage']),r.get('outcome','unknown'),f"{r.get('collisions','?')}/{t['fall_events']}",f(r.get('energy_wh')),f(t['total_wh_difference_pct'])+'%',f(r.get('elapsed_s')),f(t['first_motion_sim_s']),f(t['energy_after_first_motion_wh']),f(t['motion_to_finish_s']),f(t['lower_hz']),str(t['stop']['acknowledged'])+'/'+t['stop']['reason']])+'|')
    text+=['','## 試行数と成功率','']
    for stage in (1,2,3):
        own=[t for t in trials if t['stage']==stage];wins=sum(t['success'] for t in own)
        text.append(f'- Stage{stage}: {wins}/{len(own)}。'+(f'観測成功率{wins/len(own)*100:.1f}%。少数試行で一般化不可。' if own else '未実施。'))
    text+=['','## 動画検証','', '|試行/視点|fps|全フレーム|欠落|元画像複製|復号全画素複製|縮小画像複製|元画像更新Hz|復号全画素Hz|縮小画像Hz|全デコード|総合|','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for t in trials:
        if not t['video']:text.append(f"|{t['name']}|未作成|||||||||");continue
        for view,v in t['video']['views'].items():
            text.append('|'+ '|'.join([t['name']+'/'+view,str(v['fps']),str(v['frames_decoded']),str(v['missing_decoded_frames']),str(v['duplicate_source_frames']),str(v.get('duplicate_decoded_full_frames','未測定')),str(v['duplicate_decoded_sample_frames']),f(v['source_update_hz']),f(v.get('decoded_full_update_hz')),f(v['decoded_sample_update_hz']),str(v['checks']['full_decode_ok']),str(v['pass_all'])])+'|')
    text+=['','判断全文・実閲覧IDは各session/astra/、適用指令はlogs/decisions.jsonl、動画と状態行の対応はvideo/試行/*.frame_map.jsonlを参照。再描画画像はAstraが実際に観測した画像ではない。']
    (output/'ai-play-results.md').write_text('\n'.join(text)+'\n')
    return trials

def main():
    p=argparse.ArgumentParser();p.add_argument('--sessions',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summarize(a.sessions,a.output)
if __name__=='__main__':main()
