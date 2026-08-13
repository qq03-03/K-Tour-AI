from pathlib import Path
import json, re, collections

SEASONS=("봄","여름","가을","겨울")

def safe_name(v):
    s=re.sub(r"[^0-9A-Za-z가-힣_-]+","_",str(v)).strip("_")
    return s or "video"

def mode_for_duration(d):
    if d<=60:return "short_scene_change"
    if d<=120:return "medium_highlight"
    if d<=600:return "long_highlight"
    if d<=1800:return "very_long_highlight"
    return "huge_coarse_highlight"

def main():
    root=Path(__file__).resolve().parent
    data_path=root/"data_inbox"/"drama_video_data_tagged_최종.json"
    manifest_path=root/"preprocessing_manifest.json"
    data=json.loads(data_path.read_text(encoding="utf-8-sig"))
    old=json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    records=[]
    for g in data:
        prefix=str(g.get("video_id_prefix") or ""); title=str(g.get("drama_title") or "")
        for p in g.get("places",[]) or []:
            for s in p.get("segments",[]) or []:
                yt=str(p.get("youtube_id") or "").strip(); sid=str(s.get("segment_id") or "").strip(); st=float(s.get("start_time") or 0); en=float(s.get("end_time")); seasons=s.get("season") or []; seasons=seasons if isinstance(seasons,list) else [seasons]; seasons=[str(x) for x in seasons if str(x) in SEASONS]
                records.append({"video_id_prefix":prefix,"video_id":f"{prefix}_{safe_name(yt)}" if prefix else safe_name(yt),"source_segment_id":sid,"youtube_id":yt,"source_url":str(p.get("source_url") or ""),"drama_title":title,"place_id":str(p.get("place_id") or ""),"place_name":str(p.get("place_name") or ""),"place_candidates":[str(p.get("place_name") or "")],"region":str(p.get("region") or ""),"city":str(p.get("city") or ""),"season":seasons,"expected_seasons":seasons,"time_of_day":s.get("time_of_day") or [],"mood":s.get("mood") or [],"scene_elements":s.get("scene_elements") or [],"k_culture_elements":s.get("k_culture_elements") or [],"activity":s.get("activity") or [],"description":str(s.get("description") or ""),"input_keyframe_path":str(s.get("keyframe_path") or ""),"candidate_ranges":[{"source_segment_id":sid,"start_time":st,"end_time":en,"description":str(s.get("description") or "")}],"input_range_duration":round(en-st,3),"expected_processing_mode":mode_for_duration(en-st),"processing_state":"pending","runtime_time_validation":True,"season_match_required":False,"theme_match_required":False})
    counts=collections.Counter(r["source_segment_id"] for r in records)
    dup=[k for k,v in counts.items() if v>1]
    if dup: raise ValueError(f"중복 segment_id: {dup}")
    old["records"]=records; old["record_count"]=len(records); old["unique_source_video_count"]=len({r["youtube_id"] for r in records}); old["source_data_file"]="data_inbox/drama_video_data_tagged_최종.json"
    manifest_path.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"매니페스트 재생성 완료: {len(records)}개")

if __name__=="__main__": main()
