from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
def local_app_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))


def jianying_user_data() -> Path:
    return Path(os.environ.get("JY_USER_DATA", str(local_app_data() / "JianyingPro/User Data")))


def default_subtitle_font() -> str:
    configured = os.environ.get("JJ_FONT_PATH")
    if configured:
        return configured
    cache = jianying_user_data() / "Cache/effect"
    if cache.exists():
        found = next(cache.rglob("三极宋黑体 超粗.ttf"), None)
        if found:
            return str(found)
    return str(jianying_user_data() / "Fonts/三极宋黑体 超粗.ttf")


DEFAULT_SUBTITLE_FONT_PATH = default_subtitle_font()
DEFAULT_SUBTITLE_STYLE = {
    "template": "dalian-zhangge-sanjisonghei-10.7",
    "font": "三极宋黑体超粗",
    "font_path": DEFAULT_SUBTITLE_FONT_PATH,
    "size": 11.0,
    "scale": 1.0,
    "bold": False,
    "color": "#FFFFFF",
    "emphasis_color": "#FFF589",
    "x": 0.0,
    "y": -0.56,
    "shadow": {"enabled": True, "color": "#000000", "alpha": 0.9, "diffuse": 15.0, "distance": 5.0, "angle": -45.0},
    "max_chars": 12,
}
DEFAULT_SCRIPT_FLOW_DURATION = {"target_seconds": 150.0, "min_seconds": 135.0, "max_seconds": 165.0}
STAGES = ["script", "audio", "visual", "overlay"]
MEDIA_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts"}
DEFAULT_BUDGET = {
    "high_model_calls": 2,
    "fast_model_calls": 2,
    "max_candidate_segments": 80,
    "max_text_chars": 30000,
    "max_contact_sheets": 12,
    "max_images_per_batch": 6,
    "max_manifest_bytes": 20480,
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_subtitle_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^(?:好吧|啊|呀|嗯|哦|呃|哎|诶|唉|哈)+[\s，。！？、；：,.!?;~～…—-]*", "", text)
    text = re.sub(r"(?:啊|呀|吧|呗|呢|嘛|嗯|哦|呃|哎|诶|唉|哈)+[\s，。！？、；：,.!?;~～…—-]*$", "", text)
    text = re.sub(r"(?<!\d)[，。！？、；：,.!?;“”‘’（）()【】\[\]《》…—~～](?!\d)", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def has_srt_timecodes(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".srt":
        return False
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:20000]
    return bool(re.search(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}", sample))


def cmd_content_gate(a):
    manifest = Path(a.manifest).resolve() if a.manifest else None
    if manifest and manifest.is_file():
        data = read_json(manifest)
        if data.get("human_approved") is True:
            print(json.dumps({"ok": True, "action": "execute_confirmed_manifest", "manifest": str(manifest), "run_script_flow": False, "media_processing_allowed": True}, ensure_ascii=False))
            return
    srt = Path(a.srt).resolve() if a.srt else None
    if srt and has_srt_timecodes(srt):
        duration = {
            "target_seconds": float(a.target_seconds),
            "min_seconds": float(a.min_seconds),
            "max_seconds": float(a.max_seconds),
        }
        print(json.dumps({
            "ok": True,
            "action": "run_dbs_script_flow",
            "srt": str(srt),
            "duration": duration,
            "required_cut_fields": ["id", "source_start", "source_end", "text", "decision_reason", "flow_risk", "suggested_order"],
            "await_human_confirmation": True,
            "media_processing_allowed": False,
            "blocked_commands": ["ingest", "transcribe", "prepare-visuals"],
        }, ensure_ascii=False))
        return
    print(json.dumps({"ok": False, "action": "request_timed_srt", "reason": "缺少有效的带时间码 SRT 或 human_approved=true 的切点 manifest", "media_processing_allowed": False, "blocked_commands": ["ingest", "transcribe", "prepare-visuals"]}, ensure_ascii=False))


def caption_errors(items: list[dict], max_chars: int = 12) -> list[str]:
    """Validate the one-phrase-per-screen subtitle contract."""
    errors = overlap_errors(items, "target_start", "target_end", "subtitle")
    ordered = sorted(items, key=lambda x: (float(x.get("target_start", 0)), float(x.get("target_end", 0))))
    previous = None
    for item in ordered:
        item_id = item.get("id", "?")
        text = clean_subtitle_text(str(item.get("text", "")))
        if not text:
            errors.append(f"subtitle {item_id}: empty text")
            continue
        if len(text) > max_chars:
            errors.append(f"subtitle {item_id}: {len(text)} chars exceeds template max {max_chars}")
        normalized = re.sub(r"\s+", "", text)
        if previous and normalized == previous[1]:
            errors.append(f"subtitle {previous[0]}/{item_id}: adjacent duplicate text")
        previous = (item_id, normalized)
    return errors


def hex_color(value: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = str(value or "").lstrip("#")
    if len(value) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return fallback
    return tuple(int(value[i:i+2], 16) / 255 for i in (0, 2, 4))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def fast_fingerprint(path: Path) -> dict:
    size = path.stat().st_size
    h = hashlib.sha256()
    block = 4 * 1024 * 1024
    with path.open("rb") as f:
        h.update(f.read(block))
        if size > block:
            f.seek(max(0, size - block))
            h.update(f.read(block))
    # Path is deliberately excluded: renaming an unchanged clip must keep its cache identity.
    payload = f"{size}|{path.stat().st_mtime_ns}|{h.hexdigest()}".encode("utf-8")
    return {"id": sha256_bytes(payload), "size": size, "mtime_ns": path.stat().st_mtime_ns, "edge_sha256": h.hexdigest()}


def ffmpeg_paths() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg:
        try:
            ffmpeg = subprocess.check_output([sys.executable, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"], text=True).strip()
        except Exception as exc:
            raise RuntimeError("找不到 ffmpeg，请安装或安装 imageio-ffmpeg") from exc
    if not ffprobe:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        ffprobe = str(sibling) if sibling.exists() else "ffprobe"
    return ffmpeg, ffprobe


def probe(path: Path) -> dict:
    _, ffprobe = ffmpeg_paths()
    try:
        raw = subprocess.check_output([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate", "-of", "json", str(path)], text=True, encoding="utf-8", errors="replace")
        data = json.loads(raw)
        return {"duration": float(data.get("format", {}).get("duration") or 0), "streams": data.get("streams", [])}
    except Exception:
        ffmpeg, _ = ffmpeg_paths()
        raw = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", raw)
        dur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3)) if m else 0
        return {"duration": dur, "streams": []}


def project(path: str) -> Path:
    p = Path(path).resolve()
    if not (p / "project-state.json").exists():
        raise FileNotFoundError(f"不是工作台项目：{p}")
    return p


def duration_contract(target: float | None, minimum: float | None, maximum: float | None, source: str, reference: str | None = None) -> dict:
    if target is None:
        return {"status":"pending","source":source,"reference":reference}
    target=float(target); tolerance=max(0.5,target*0.125)
    minimum=float(minimum) if minimum is not None else target-tolerance
    maximum=float(maximum) if maximum is not None else target+tolerance
    if target<=0 or minimum<=0 or maximum<minimum or not minimum<=target<=maximum:
        raise ValueError("时长目标必须满足 0 < min <= target <= max")
    return {"status":"configured","target_seconds":round(target,3),"min_seconds":round(minimum,3),"max_seconds":round(maximum,3),"source":source,"reference":reference}


def require_duration(state: dict) -> dict:
    spec=state.get("duration") or {"status":"pending"}
    if spec.get("status")!="configured": raise RuntimeError("尚未配置期望时长；先运行 set-duration，用户明确时长优先于参考成片")
    return spec


def timeline_duration(items: list[dict]) -> float:
    if not items: return 0.0
    return round(max(float(x.get("target_end",0)) for x in items)-min(float(x.get("target_start",0)) for x in items),3)


def duration_result(spec: dict, actual: float) -> dict:
    status="within"
    if actual<spec["min_seconds"]: status="under"
    elif actual>spec["max_seconds"]: status="over"
    return {"status":status,"actual_seconds":round(actual,3),"target_seconds":spec["target_seconds"],"min_seconds":spec["min_seconds"],"max_seconds":spec["max_seconds"],"source":spec["source"]}


def enforce_duration(state: dict, items: list[dict], stage: str) -> dict:
    result=duration_result(require_duration(state),timeline_duration(items))
    if result["status"]!="within": raise RuntimeError(f"{stage} 时长 {result['actual_seconds']} 秒不在 {result['min_seconds']}-{result['max_seconds']} 秒范围；素材不足时停止并报告，不得用重复废话补时长")
    return result


def cmd_set_duration(a):
    p=project(a.project); state=read_json(p/"project-state.json")
    target=a.target_seconds; reference=str(Path(a.reference).resolve()) if a.reference else None; source=a.source
    if target is None and reference:
        target=float(probe(Path(reference)).get("duration",0)); source="reference"
    spec=duration_contract(target,a.min_seconds,a.max_seconds,source,reference)
    if spec["status"]!="configured": raise RuntimeError("需要 --target-seconds 或 --reference")
    if state.get("duration")!=spec: invalidate(state,"script","duration contract changed")
    state["duration"]=spec; write_json(p/"project-state.json",state); print(json.dumps({"ok":True,"duration":spec},ensure_ascii=False))


def cmd_set_delivery_copy(a):
    p=project(a.project); video=a.video_title.strip(); poster=a.poster_title.strip()
    if not video or not poster: raise ValueError("视频标题和海报标题都不能为空")
    if len(poster)>20: raise ValueError("海报标题应控制在20个中文字符以内")
    data={"schema_version":SCHEMA,"video_title":video,"poster_title":poster,"updated_at":now()}
    write_json(p/"qa"/"delivery-copy.json",data); print(json.dumps({"ok":True,**data},ensure_ascii=False))


def require_delivery_copy(p: Path) -> dict:
    path=p/"qa"/"delivery-copy.json"
    if not path.exists(): raise RuntimeError("构建前必须运行 set-delivery-copy，准备视频标题和海报标题")
    data=read_json(path)
    if not data.get("video_title") or not data.get("poster_title"): raise RuntimeError("交付标题不完整")
    return data


def cmd_init(a):
    p = Path(a.project).resolve()
    if p.exists() and any(p.iterdir()):
        raise FileExistsError(f"拒绝覆盖非空目录：{p}")
    p.mkdir(parents=True, exist_ok=True)
    for d in ["transcript", "proxy", "contact-sheets", "manifests", "qa"]:
        (p/d).mkdir()
    reference=str(Path(a.reference).resolve()) if a.reference else None; target=a.target_seconds
    if target is None and reference: target=float(probe(Path(reference)).get("duration",0))
    spec=duration_contract(target,a.min_seconds,a.max_seconds,"user" if a.target_seconds is not None else ("reference" if reference else "pending"),reference)
    state = {"schema_version": SCHEMA, "project_id": sha256_bytes(f"{a.name}|{p}".encode())[:16], "name": a.name, "source": str(Path(a.source).resolve()), "created_at": now(), "duration":spec, "budget": DEFAULT_BUDGET, "usage": {"high_model_calls": 0, "fast_model_calls": 0}, "locks": {s: None for s in STAGES}}
    write_json(p/"project-state.json", state)
    print(json.dumps({"ok": True, "project": str(p), "next": "ingest"}, ensure_ascii=False))


def run_media_command(args: list[str], dst: Path) -> None:
    """Run one media job atomically and never expose an incomplete final file."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(f"{dst.stem}.partial{dst.suffix}")
    partial.unlink(missing_ok=True)
    command = [*args, str(partial)]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(command, creationflags=creationflags)
    try:
        returncode = proc.wait()
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
        os.replace(partial, dst)
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        partial.unlink(missing_ok=True)
        raise


def make_proxy(ffmpeg: str, src: Path, dst: Path):
    run_media_command([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", "scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2", "-r", "15", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-c:a", "aac", "-b:a", "64k"], dst)


def make_sheet(ffmpeg: str, src: Path, dst: Path, duration: float):
    interval = max(1.0, duration / 9.0)
    vf = f"fps=1/{interval},scale=320:-1,tile=3x3"
    run_media_command([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", vf, "-frames:v", "1"], dst)


def cmd_ingest(a):
    p = project(a.project); state = read_json(p/"project-state.json"); src = Path(state["source"])
    files = sorted(x for x in src.rglob("*") if x.is_file() and x.suffix.lower() in MEDIA_EXTS)
    old_items = read_json(p/"source-index.json").get("items", []) if (p/"source-index.json").exists() else []
    old = {x["path"]: x for x in old_items}
    old_by_id = {x.get("fingerprint", {}).get("id"): x for x in old_items}
    ffmpeg, _ = ffmpeg_paths(); items=[]; changed=0
    for f in files:
        fp=fast_fingerprint(f); prior=old.get(str(f.resolve())) or old_by_id.get(fp["id"])
        meta=prior.get("media", {}) if prior and prior.get("fingerprint",{}).get("id")==fp["id"] else probe(f)
        changed += int(not prior or prior.get("fingerprint",{}).get("id") != fp["id"])
        proxy=p/"proxy"/f"{fp['id']}.mp4"; sheet=p/"contact-sheets"/f"{fp['id']}.jpg"
        if a.proxies and not proxy.exists(): make_proxy(ffmpeg,f,proxy)
        if a.contact_sheets and not sheet.exists(): make_sheet(ffmpeg,f,sheet,float(meta.get("duration",0)))
        items.append({"path":str(f.resolve()),"name":f.name,"fingerprint":fp,"media":meta,"proxy":str(proxy) if proxy.exists() else None,"contact_sheet":str(sheet) if sheet.exists() else None})
    write_json(p/"source-index.json", {"schema_version":SCHEMA,"generated_at":now(),"source":str(src),"items":items})
    if changed: invalidate(state, "script", "source-index changed")
    write_json(p/"project-state.json",state)
    print(json.dumps({"ok":True,"media_count":len(items),"changed":changed,"index":str(p/"source-index.json")},ensure_ascii=False))


def cmd_prepare_visuals(a):
    p=project(a.project); state=read_json(p/"project-state.json"); idx_path=p/"source-index.json"
    if not idx_path.exists(): raise RuntimeError("必须先运行 ingest 或 index-manifest-sources")
    if a.scope == "selected" and not (state["locks"].get("audio") or {}).get("valid"):
        raise RuntimeError("selected 画面准备必须先锁定 audio")
    idx=read_json(idx_path); items=idx.get("items",[]); by_path={str(Path(x["path"]).resolve()):x for x in items}
    if a.scope == "selected":
        visual_path=p/"manifests"/"visual.json"
        if not visual_path.exists(): raise RuntimeError("缺少 visual manifest")
        selected={str(Path(x["source_path"]).resolve()) for x in read_json(visual_path).get("items",[])}
    else:
        selected=set(by_path)
    missing=sorted(selected-set(by_path))
    if missing: raise RuntimeError(f"source-index 缺少选中素材：{missing[:3]}")
    ffmpeg,_=ffmpeg_paths(); built_proxy=built_sheet=cache_hits=0
    for path in sorted(selected):
        item=by_path[path]; src=Path(path); fp=item["fingerprint"]
        proxy=p/"proxy"/f"{fp['id']}.mp4"; sheet=p/"contact-sheets"/f"{fp['id']}.jpg"
        if a.proxies:
            if proxy.exists() and proxy.stat().st_size>0: cache_hits+=1
            else: make_proxy(ffmpeg,src,proxy); built_proxy+=1
        if a.contact_sheets:
            if sheet.exists() and sheet.stat().st_size>0: cache_hits+=1
            else: make_sheet(ffmpeg,src,sheet,float(item.get("media",{}).get("duration",0))); built_sheet+=1
        item["proxy"]=str(proxy) if proxy.exists() and proxy.stat().st_size>0 else None
        item["contact_sheet"]=str(sheet) if sheet.exists() and sheet.stat().st_size>0 else None
    idx["generated_at"]=now(); write_json(idx_path,idx)
    print(json.dumps({"ok":True,"scope":a.scope,"selected_count":len(selected),"built_proxies":built_proxy,"built_contact_sheets":built_sheet,"cache_hits":cache_hits},ensure_ascii=False))


def tool_version(module: str) -> str:
    try:
        m=__import__(module); return getattr(m,"__version__","unknown")
    except Exception: return "missing"


def cmd_transcribe(a):
    p=project(a.project); idx=read_json(p/"source-index.json")
    try: from faster_whisper import WhisperModel
    except ImportError as exc: raise RuntimeError("需要安装 faster-whisper") from exc
    model=WhisperModel(a.model,device="cpu",compute_type=a.compute_type); done=hit=0
    for item in idx["items"]:
        if float(item["media"].get("duration",0)) < a.min_duration: continue
        key=sha256_bytes(f"{item['fingerprint']['id']}|{a.model}|{a.compute_type}|{a.language}|{tool_version('faster_whisper')}".encode())
        out=p/"transcript"/f"{key}.json"
        if out.exists():
            cached=read_json(out)
            if cached.get("source_path") != item["path"]:
                cached["source_path"] = item["path"]
                write_json(out, cached)
            hit+=1; continue
        segs,_=model.transcribe(item["path"],language=a.language,beam_size=5,vad_filter=True,word_timestamps=True)
        rows=[]
        for s in segs:
            rows.append({"start":round(s.start,3),"end":round(s.end,3),"text":s.text.strip(),"words":[{"start":round(w.start,3),"end":round(w.end,3),"text":w.word} for w in (s.words or [])]})
        write_json(out,{"schema_version":SCHEMA,"source_id":item["fingerprint"]["id"],"source_path":item["path"],"cache_key":key,"model":a.model,"language":a.language,"segments":rows}); done+=1
    print(json.dumps({"ok":True,"transcribed":done,"cache_hits":hit,"transcript_dir":str(p/"transcript")},ensure_ascii=False))


def cmd_build_audio_preview(a):
    p=project(a.project); state=read_json(p/"project-state.json"); lock=state["locks"].get("audio") or {}
    if not lock.get("valid"): raise RuntimeError("必须先锁定 audio")
    manifest=read_json(Path(lock["input"])); items=sorted(manifest.get("items",[]),key=lambda x:float(x["target_start"]))
    if not items: raise RuntimeError("audio manifest 没有切点")
    ffmpeg,_=ffmpeg_paths(); args=[ffmpeg,"-y","-hide_banner","-loglevel","error"]
    filters=[]; labels=[]; total=0.0
    for i,item in enumerate(items):
        start=float(item["source_start"]); end=float(item["source_end"]); duration=end-start
        if duration<=0: raise RuntimeError(f"audio cut {item.get('id',i)} 时长无效")
        args.extend(["-ss",str(start),"-t",str(duration),"-i",str(item["source_path"])])
        filters.append(f"[{i}:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a{i}]"); labels.append(f"[a{i}]"); total+=duration
    filters.append(f"{''.join(labels)}concat=n={len(items)}:v=0:a=1[outa]")
    output=Path(a.output).resolve() if a.output else p/"qa"/"audio-preview.m4a"
    args.extend(["-filter_complex",";".join(filters),"-map","[outa]","-c:a","aac","-b:a","128k"])
    run_media_command(args,output)
    measured=float(probe(output).get("duration",0)); check=duration_result(require_duration(state),measured)
    if check["status"]!="within": raise RuntimeError(f"声音草稿时长验证失败：{check}")
    result={"ok":True,"output":str(output),"cuts":len(items),"duration_seconds":round(total,3),"measured_duration_seconds":round(measured,3),"duration_check":check,"audio_lock_hash":lock["hash"],"built_at":now()}
    write_json(p/"qa"/"audio-preview.json",result); print(json.dumps(result,ensure_ascii=False))


def cmd_search(a):
    p=project(a.project); keys=[x.strip() for x in a.keywords.split(",") if x.strip()]; results=[]
    for f in (p/"transcript").glob("*.json"):
        d=read_json(f); segs=d.get("segments",[])
        for i,s in enumerate(segs):
            hits=[k for k in keys if k.lower() in s.get("text","").lower()]
            if not hits: continue
            lo=max(0,i-a.context_segments); hi=min(len(segs),i+a.context_segments+1)
            results.append({"source_id":d["source_id"],"source_path":d["source_path"],"start":segs[lo]["start"],"end":segs[hi-1]["end"],"match_start":s["start"],"match_end":s["end"],"text":s["text"],"keywords":hits,"context":"".join(x["text"] for x in segs[lo:hi])})
    results=results[:a.max_results]; out=p/"candidates.json"
    write_json(out,{"schema_version":SCHEMA,"keywords":keys,"count":len(results),"items":results})
    print(json.dumps({"ok":True,"count":len(results),"output":str(out),"truncated":len(results)>=a.max_results},ensure_ascii=False))


def canonical_hash(path: Path) -> str:
    return sha256_bytes(json.dumps(read_json(path),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8"))


def normalize_cut(row: dict, index: int, source_root: Path | None = None) -> dict:
    path = row.get("source_path") or row.get("sound_file") or row.get("file") or row.get("path") or row.get("material")
    source_start = row.get("source_start", row.get("material_start", row.get("material_in", 0)))
    source_end = row.get("source_end", row.get("material_end", row.get("material_out")))
    target_start = row.get("target_start", row.get("final_in", 0))
    target_end = row.get("target_end", row.get("final_out"))
    if source_end is None or target_end is None or not path:
        raise ValueError(f"cut {index} 缺少路径或时间")
    source_path=Path(path)
    if not source_path.is_absolute() and source_root is not None: source_path=source_root/source_path
    return {
        "id": str(row.get("id", f"S{index+1:02}")),
        "source_path": str(source_path.resolve()),
        "source_start": float(source_start),
        "source_end": float(source_end),
        "target_start": float(target_start),
        "target_end": float(target_end),
        "crop": float(row.get("crop", 1.0)),
        "label": row.get("label", ""),
        "project_id": row.get("project_id"),
        "role": row.get("role", "main"),
    }


def normalized_caption_rows(data: dict, cuts: list[dict]) -> list[dict]:
    rows = []
    direct = data.get("captions", [])
    if direct:
        for i, row in enumerate(direct):
            start = row.get("target_start", row.get("start"))
            end = row.get("target_end", row.get("end"))
            if start is None or end is None or not row.get("text"): continue
            cleaned=clean_subtitle_text(row["text"])
            if cleaned: rows.append({"id": f"T{i+1:03}", "text": cleaned, "target_start": float(start), "target_end": float(end), "style": row.get("style", "normal"), "color": row.get("color")})
        return rows
    for i, (raw, cut) in enumerate(zip(data.get("cuts", []), cuts)):
        captions = raw.get("captions", [])
        if not captions: continue
        span = cut["target_end"] - cut["target_start"]
        step = span / len(captions)
        for j, text in enumerate(captions):
            cleaned=clean_subtitle_text(text)
            if cleaned: rows.append({"id": f"T{i+1:02}{j+1:02}", "text": cleaned, "target_start": cut["target_start"] + j*step, "target_end": cut["target_start"] + (j+1)*step - 0.012})
    return rows


def cmd_import_manifest(a):
    p=project(a.project); state=read_json(p/"project-state.json"); src=Path(a.manifest).resolve(); data=read_json(src)
    base=Path(a.source_root).resolve() if a.source_root else Path(state["source"])
    cuts=[normalize_cut(row,i,base) for i,row in enumerate(data.get("cuts",[]))]
    for row in cuts: row["project_id"] = row["project_id"] or state["project_id"]
    captions=normalized_caption_rows(data,cuts)
    cards=data.get("cards", data.get("overlays", []))
    overlay_items=[]
    for i,row in enumerate(cards):
        start=row.get("start",row.get("target_start")); end=row.get("end",row.get("target_end"))
        if start is None or end is None or not row.get("text"): continue
        overlay_items.append({"id":f"O{i+1:02}","kind":row.get("kind",row.get("type","section")),"text":row["text"],"target_start":float(start),"target_end":float(end)})
    manifests=p/"manifests"
    spec=require_duration(state)
    sections=data.get("duration_budget",{}).get("sections") or [{"name":x.get("label") or x["id"],"seconds":round(x["target_end"]-x["target_start"],3)} for x in cuts]
    budget={"target_seconds":spec["target_seconds"],"min_seconds":spec["min_seconds"],"max_seconds":spec["max_seconds"],"source":spec["source"],"sections":sections}
    common={"schema_version":SCHEMA,"project_id":state["project_id"],"human_approved":bool(a.human_approved),"imported_from":str(src)}
    subtitle={**DEFAULT_SUBTITLE_STYLE,**data.get("subtitle",{})}
    subtitle["enabled"] = bool(data.get("subtitle",{}).get("enabled",False))
    script={**common,"stage":"script","duration_budget":budget,"subtitles_enabled":subtitle["enabled"],"items":captions}
    write_json(manifests/"script.json",script)
    script_hash=canonical_hash(manifests/"script.json")
    audio={**common,"stage":"audio","upstream_hash":script_hash,"items":cuts}
    write_json(manifests/"audio.json",audio)
    audio_hash=canonical_hash(manifests/"audio.json")
    visual={**common,"stage":"visual","upstream_hash":audio_hash,"items":[{**x,"evidence_project_id":state["project_id"]} for x in cuts]}
    write_json(manifests/"visual.json",visual)
    visual_hash=canonical_hash(manifests/"visual.json")
    overlay={**common,"stage":"overlay","upstream_hash":visual_hash,"items":overlay_items,"subtitle_style":subtitle,"renderer":"overlay-studio","fallback":"jianying-native-text"}
    write_json(manifests/"overlay.json",overlay)
    delivery=data.get("delivery",{})
    if delivery.get("video_title") and delivery.get("poster_title"):
        write_json(p/"qa"/"delivery-copy.json",{"schema_version":SCHEMA,"video_title":delivery["video_title"],"poster_title":delivery["poster_title"],"updated_at":now()})
    print(json.dumps({"ok":True,"cuts":len(cuts),"captions":len(captions),"overlays":len(overlay_items),"manifests":str(manifests)},ensure_ascii=False))


def cmd_index_manifest_sources(a):
    p=project(a.project); state=read_json(p/"project-state.json"); visual=read_json(p/"manifests"/"visual.json"); seen=set()
    idx_path=p/"source-index.json"; existing=read_json(idx_path) if idx_path.exists() else {"items":[]}
    items=list(existing.get("items",[])); by_path={str(Path(x["path"]).resolve()):x for x in items}; added=0; referenced=[]
    for row in visual.get("items",[]):
        path=Path(row["source_path"])
        resolved=str(path.resolve())
        if resolved in seen: continue
        seen.add(resolved); referenced.append(resolved)
        if not path.exists(): raise FileNotFoundError(path)
        fp=fast_fingerprint(path)
        prior=by_path.get(resolved)
        if prior and prior.get("fingerprint",{}).get("id")==fp["id"]: continue
        item={"path":resolved,"name":path.name,"fingerprint":fp,"media":probe(path),"proxy":None,"contact_sheet":None}
        if prior: items[items.index(prior)]=item
        else: items.append(item); added+=1
        by_path[resolved]=item
    source=existing.get("source") or state["source"]
    write_json(idx_path,{"schema_version":SCHEMA,"generated_at":now(),"source":source,"manifest_sources":referenced,"items":items})
    print(json.dumps({"ok":True,"media_count":len(items),"referenced_count":len(referenced),"added":added,"index":str(idx_path)},ensure_ascii=False))


def cmd_lock_all(a):
    for stage in STAGES:
        ns=argparse.Namespace(project=a.project,stage=stage,input=str(Path(a.project)/"manifests"/f"{stage}.json"),allow_unapproved=a.allow_unapproved)
        cmd_lock(ns)


def sorted_intervals(items: list[dict], start_key: str, end_key: str):
    return sorted([(float(x[start_key]),float(x[end_key]),x.get("id","?")) for x in items],key=lambda x:(x[0],x[1]))


def overlap_errors(items: list[dict], start_key: str, end_key: str, label: str) -> list[str]:
    rows=sorted_intervals(items,start_key,end_key); errors=[]
    for i,(start,end,item_id) in enumerate(rows):
        if end <= start: errors.append(f"{label} {item_id}: non-positive duration")
        if i and start < rows[i-1][1]-0.001: errors.append(f"{label} {rows[i-1][2]}/{item_id}: overlap")
    return errors


def cmd_preflight(a):
    p=project(a.project); state=read_json(p/"project-state.json"); errors=[]; warnings=[]
    for stage in STAGES:
        lock=state["locks"].get(stage)
        if not lock or not lock.get("valid"): errors.append(f"{stage}: not locked"); continue
        path=Path(lock["input"])
        if not path.exists() or canonical_hash(path)!=lock["hash"]: errors.append(f"{stage}: lock hash mismatch")
    manifests=p/"manifests"
    if not errors:
        script=read_json(manifests/"script.json"); audio=read_json(manifests/"audio.json"); visual=read_json(manifests/"visual.json"); overlay=read_json(manifests/"overlay.json")
        stage_data={"script":script,"audio":audio,"visual":visual,"overlay":overlay}
        for i,stage in enumerate(STAGES[1:],start=1):
            expected=state["locks"][STAGES[i-1]]["hash"]
            if stage_data[stage].get("upstream_hash") != expected:
                errors.append(f"{stage}: upstream lock hash mismatch")
        if script.get("subtitles_enabled",True):
            max_chars=int(overlay.get("subtitle_style",{}).get("max_chars",12))
            errors += caption_errors(script.get("items",[]),max_chars=max_chars)
        errors += overlap_errors(audio.get("items",[]),"target_start","target_end","audio")
        main=[x for x in visual.get("items",[]) if x.get("role","main")=="main"]
        errors += overlap_errors(main,"target_start","target_end","main-video")
        spec=require_duration(state)
        for label,items in (("script",script.get("items",[])),("audio",audio.get("items",[])),("visual",main)):
            check=duration_result(spec,timeline_duration(items))
            if check["status"]!="within": errors.append(f"{label} duration {check['actual_seconds']} outside {check['min_seconds']}-{check['max_seconds']}")
        duration_cache={}
        for item in visual.get("items",[]):
            path=Path(item["source_path"])
            if not path.exists(): errors.append(f"missing source: {path}"); continue
            duration_cache.setdefault(str(path),probe(path).get("duration",0))
            if item["source_start"] < 0 or item["source_end"] > duration_cache[str(path)]+0.05: errors.append(f"source range out of bounds: {item.get('id')}")
            if item.get("role")=="broll" and item.get("evidence_project_id") != state["project_id"]: errors.append(f"cross-project broll: {item.get('id')}")
        if not visual.get("items"): warnings.append("visual manifest empty")
    report={"schema_version":SCHEMA,"project_id":state["project_id"],"checked_at":now(),"ok":not errors,"errors":errors,"warnings":warnings}
    write_json(p/"qa"/"preflight.json",report); print(json.dumps(report,ensure_ascii=False))
    if errors: raise SystemExit(2)


def jianying_codec():
    ensure_jianying_module()
    import pyJianYingDraft as jy
    configured = os.environ.get("JY_INSTALL_DIR")
    apps = local_app_data() / "JianyingPro/Apps"
    if configured:
        install = Path(configured)
    else:
        candidates = [x for x in apps.iterdir() if x.is_dir() and (x / "JianyingPro.exe").exists()] if apps.exists() else []
        if not candidates:
            raise RuntimeError("找不到剪映安装目录；请设置 JY_INSTALL_DIR 为含 JianyingPro.exe 的版本目录")
        install = max(candidates, key=lambda x: x.stat().st_mtime)
    if not (install / "JianyingPro.exe").is_file():
        raise RuntimeError("JY_INSTALL_DIR 必须指向含 JianyingPro.exe 的版本目录")
    return jy.JianyingDraftCryptoCodec(jy.DraftCryptoConfig(jy_install_dir=install)),install


def ensure_jianying_module():
    try:
        import pyJianYingDraft  # noqa: F401
        return
    except ImportError:
        pass
    candidates = [
        Path(os.environ.get("PYJY_ROOT", "")) if os.environ.get("PYJY_ROOT") else None,
        Path.home() / ".cache/codex-tools/pyJianYingDraft-aoguai",
        local_app_data() / "Temp/codex-pyJianYingDraft",
        local_app_data() / "Temp/codex-pyJianYingDraft-aoguai",
    ]
    for candidate in candidates:
        if candidate and (candidate / "pyJianYingDraft").is_dir():
            sys.path.insert(0, str(candidate)); return
    raise RuntimeError("找不到 pyJianYingDraft；请设置 PYJY_ROOT 指向其项目根目录")


def verify_jianying_draft(target: Path, draft_root: Path, codec, user_data: Path) -> dict:
    from pyJianYingDraft.draft_codec import load_json_object_with_codec
    import pyJianYingDraft as jy
    errors=[]; required=("draft_info.json","draft_content.json","draft_meta_info.json")
    for name in required:
        path=target/name
        if not path.exists() or path.stat().st_size<=0: errors.append(f"missing required draft file: {name}")
    if errors: return {"ok":False,"errors":errors,"required_files":list(required)}
    try:
        info,info_encoded=load_json_object_with_codec(target/"draft_info.json",content_codec=codec)
        content,content_encoded=load_json_object_with_codec(target/"draft_content.json",content_codec=codec)
        meta,meta_encoded=load_json_object_with_codec(target/"draft_meta_info.json",content_codec=codec)
    except Exception as exc:
        return {"ok":False,"errors":[f"draft decode failed: {exc}"],"required_files":list(required)}
    if info.get("id")!=content.get("id"): errors.append("draft_info/draft_content id mismatch")
    materials=content.get("materials",{}); material_ids={m.get("id") for rows in materials.values() if isinstance(rows,list) for m in rows if isinstance(m,dict) and m.get("id")}
    segments=[s for track in content.get("tracks",[]) for s in track.get("segments",[])]
    refs={s.get("material_id") for s in segments if s.get("material_id")}
    missing_refs=sorted(refs-material_ids)
    if missing_refs: errors.append(f"missing material refs: {missing_refs[:5]}")
    video_paths=[m.get("path") for m in materials.get("videos",[]) if m.get("path")]
    missing_paths=[path for path in video_paths if not Path(path).exists()]
    if missing_paths: errors.append(f"missing source paths: {missing_paths[:3]}")
    track_overlaps=[]
    for track_index,track in enumerate(content.get("tracks",[])):
        if track.get("type") not in ("video","audio"): continue
        rows=[]
        for segment in track.get("segments",[]):
            timerange=segment.get("target_timerange",{}); start=float(timerange.get("start",0)); duration=float(timerange.get("duration",0)); rows.append((start,start+duration,segment.get("id","?")))
        rows.sort()
        for i,row in enumerate(rows[1:],start=1):
            if row[0] < rows[i-1][1]-1: track_overlaps.append(f"track {track_index}: {rows[i-1][2]}/{row[2]}")
    if track_overlaps: errors.append(f"track overlaps: {track_overlaps[:5]}")
    library_load=False
    try:
        folder=jy.DraftFolder(str(draft_root),content_codec=codec,user_data_path=str(user_data))
        loaded=folder.load_template(target.name); library_load=bool(loaded.width and loaded.height)
    except Exception as exc:
        errors.append(f"library load failed: {exc}")
    return {
        "ok":not errors,"errors":errors,"required_files":list(required),
        "encoded":{"draft_info":info_encoded,"draft_content":content_encoded,"draft_meta_info":meta_encoded},
        "same_content_id":info.get("id")==content.get("id"),"library_load":library_load,
        "registration_metadata":bool(meta),"duration_us":content.get("duration",0),
        "video_segments":sum(len(t.get("segments",[])) for t in content.get("tracks",[]) if t.get("type")=="video"),
        "text_segments":sum(len(t.get("segments",[])) for t in content.get("tracks",[]) if t.get("type")=="text"),
        "missing_material_refs":missing_refs,"missing_source_paths":missing_paths,"track_overlaps":track_overlaps,
    }


def cmd_build_jianying(a):
    p=project(a.project)
    cmd_preflight(argparse.Namespace(project=a.project))
    state=read_json(p/"project-state.json"); delivery=require_delivery_copy(p)
    ensure_jianying_module()
    import pyJianYingDraft as jy
    from pyJianYingDraft.draft_codec import write_json_text_with_codec
    codec,install=jianying_codec(); root=Path(a.draft_root).resolve(); target=root/a.name
    if target.exists(): raise FileExistsError(f"拒绝覆盖已有草稿：{target}")
    user=jianying_user_data()
    folder=jy.DraftFolder(str(root),content_codec=codec,user_data_path=str(user)); s=folder.create_draft(a.name,2160,3840,fps=60)
    script=read_json(p/"manifests"/"script.json"); visual=read_json(p/"manifests"/"visual.json"); overlay=read_json(p/"manifests"/"overlay.json")
    subtitles_enabled=bool(script.get("subtitles_enabled",True)); overlay_enabled=bool(overlay.get("items",[]))
    specs=[jy.TrackSpec(jy.TrackType.video,"main"),jy.TrackSpec(jy.TrackType.video,"broll")]
    if subtitles_enabled: specs.append(jy.TrackSpec(jy.TrackType.text,"subtitle"))
    if overlay_enabled: specs.append(jy.TrackSpec(jy.TrackType.text,"overlay"))
    tracks=s.append_tracks(specs); vt,bt=tracks[0],tracks[1]; cursor=2
    st=tracks[cursor] if subtitles_enabled else None; cursor += int(subtitles_enabled)
    ot=tracks[cursor] if overlay_enabled else None
    mats={}
    for item in visual["items"]:
        path=item["source_path"]; mats.setdefault(path,jy.VideoMaterial(path)); dur=item["target_end"]-item["target_start"]
        seg=jy.VideoSegment(mats[path],jy.trange(f"{item['target_start']}s",f"{dur}s"),source_timerange=jy.trange(f"{item['source_start']}s",f"{item['source_end']-item['source_start']}s"),clip_settings=jy.ClipSettings(scale_x=item.get("crop",1),scale_y=item.get("crop",1)))
        s.add_segment(seg,track=bt if item.get("role")=="broll" else vt)
    sty=overlay.get("subtitle_style",{}); font=Path(sty.get("font_path") or DEFAULT_SUBTITLE_FONT_PATH)
    if (subtitles_enabled or overlay_enabled) and not font.exists(): raise FileNotFoundError(f"文字字体不存在：{font}")
    max_chars=int(sty.get("max_chars",12)); subtitle_failures=caption_errors(script.get("items",[]),max_chars=max_chars) if subtitles_enabled else []
    if subtitle_failures: raise RuntimeError(f"字幕模板检查失败：{subtitle_failures[:5]}")
    for item in script["items"] if subtitles_enabled else []:
        dur=item["target_end"]-item["target_start"]
        role=item.get("style","normal"); default_hex=sty.get("emphasis_color","#FFF589") if role=="emphasis" else sty.get("color","#FFFFFF")
        color=hex_color(item.get("color") or default_hex,(1,1,1))
        text_style=jy.TextStyle(size=float(item.get("size",sty.get("size",11.0))),color=color,bold=bool(sty.get("bold",False)),align=1,auto_wrapping=True,max_line_width=float(sty.get("max_line_width",.86)))
        shadow_cfg=sty.get("shadow",{}); shadow=None
        if shadow_cfg.get("enabled",True):
            shadow=jy.TextShadow(alpha=float(shadow_cfg.get("alpha",.9)),color=hex_color(shadow_cfg.get("color","#000000"),(0,0,0)),diffuse=float(shadow_cfg.get("diffuse",15)),distance=float(shadow_cfg.get("distance",5)),angle=float(shadow_cfg.get("angle",-45)))
        scale=float(sty.get("scale",1.0))
        s.add_segment(jy.TextSegment(item["text"],jy.trange(f"{item['target_start']}s",f"{dur}s"),font_path=str(font),style=text_style,clip_settings=jy.ClipSettings(transform_x=float(sty.get("x",0)),transform_y=float(sty.get("y",-.56)),scale_x=scale,scale_y=scale),shadow=shadow),track=st)
    native_fallback=[]
    for item in overlay.get("items",[]):
        asset=item.get("asset_path")
        if asset and Path(asset).exists():
            warnings="rendered Overlay asset recorded; image insertion requires supported pyJianYingDraft image material"
        else:
            native_fallback.append(item["id"]); dur=item["target_end"]-item["target_start"]
            s.add_segment(jy.TextSegment(item["text"],jy.trange(f"{item['target_start']}s",f"{dur}s"),font_path=str(font),style=jy.TextStyle(size=10,bold=True,color=(1,.82,.08),align=1,auto_wrapping=True,max_line_width=.9),clip_settings=jy.ClipSettings(transform_y=.62),border=jy.TextBorder(alpha=.9,color=(0,0,0),width=10)),track=ot)
    s.save()
    info_path=target/"draft_info.json"; meta_path=target/"draft_meta_info.json"
    for path in (info_path,meta_path):
        if not path.exists(): raise FileNotFoundError(f"草稿缺少必要文件：{path}")
    info_text=info_path.read_text(encoding="utf-8")
    write_json_text_with_codec(info_path,info_text,content_codec=codec); shutil.copy2(info_path,target/"draft_info.json.bak")
    content_path=target/"draft_content.json"
    write_json_text_with_codec(content_path,info_text,content_codec=codec); shutil.copy2(content_path,target/"draft_content.json.bak")
    write_json_text_with_codec(meta_path,meta_path.read_text(encoding="utf-8"),content_codec=codec); shutil.copy2(meta_path,target/"draft_meta_info.json.bak")
    validation=verify_jianying_draft(target,root,codec,user)
    if not validation["ok"]: raise RuntimeError(f"草稿构建后验证失败：{validation['errors']}")
    final_seconds=float(validation.get("duration_us",0))/1_000_000; duration_check=duration_result(require_duration(state),final_seconds)
    if duration_check["status"]!="within": raise RuntimeError(f"草稿实际时长验证失败：{duration_check}")
    result={"ok":True,"draft":str(target),"native_overlay_fallback":native_fallback,"duration_check":duration_check,"delivery_copy":delivery,"validation":validation,"built_at":now()}; write_json(p/"qa"/"build.json",result); print(json.dumps(result,ensure_ascii=False))


def cmd_overlay_handoff(a):
    p=project(a.project); overlay=read_json(p/"manifests"/"overlay.json"); allowed={"title","section","keyword","cta"}; rejected=[]; jobs=[]
    for item in overlay.get("items",[]):
        if item.get("kind") not in allowed: rejected.append(item.get("id")); continue
        jobs.append({k:item[k] for k in ["id","kind","text","target_start","target_end"] if k in item})
    ext=Path.home() / ".vscode/extensions"
    installed=any(ext.glob("overlay-studio.overlay-studio-*")) if ext.exists() else False
    packet={"schema_version":SCHEMA,"project_id":overlay["project_id"],"renderer":"overlay-studio","extension_detected":installed,"items":jobs,"rejected":rejected,"allowed_inputs":["locked title","section","keyword","cta"],"fallback":"jianying-native-text"}
    out=p/"manifests"/"overlay-studio-job.json"; write_json(out,packet)
    print(json.dumps({"ok":not rejected,"extension_detected":installed,"jobs":len(jobs),"rejected":rejected,"output":str(out),"fallback":"jianying-native-text"},ensure_ascii=False))


def cmd_record_review(a):
    p=project(a.project); state=read_json(p/"project-state.json"); payload=Path(a.payload); obj=read_json(payload); chars,images,segments=payload_stats(obj); key=f"{a.tier}_model_calls"; limit=state["budget"][key]
    if state["usage"][key] >= limit:
        print(json.dumps({"ok":False,"action":"degrade_to_manifest_only","tier":a.tier,"used":state["usage"][key],"limit":limit},ensure_ascii=False)); raise SystemExit(2)
    state["usage"][key]+=1; write_json(p/"project-state.json",state)
    log=p/"review-metrics.jsonl"; row={"at":now(),"stage":a.stage,"tier":a.tier,"payload":str(payload.resolve()),"bytes":payload.stat().st_size,"text_chars":chars,"images":images,"max_list_items":segments,"duration_seconds":a.duration_seconds,"call_number":state["usage"][key]}
    with log.open("a",encoding="utf-8") as f: f.write(json.dumps(row,ensure_ascii=False)+"\n")
    print(json.dumps({"ok":True,"record":row,"remaining":limit-state["usage"][key]},ensure_ascii=False))


def invalidate(state: dict, stage: str, reason: str):
    start=STAGES.index(stage)
    for s in STAGES[start:]:
        if state["locks"].get(s): state["locks"][s]["valid"]=False; state["locks"][s]["invalid_reason"]=reason


def cmd_lock(a):
    p=project(a.project); state=read_json(p/"project-state.json"); inp=Path(a.input).resolve(); stage=a.stage; pos=STAGES.index(stage)
    if pos and not (state["locks"].get(STAGES[pos-1]) or {}).get("valid"):
        raise RuntimeError(f"必须先锁定 {STAGES[pos-1]}")
    data=read_json(inp)
    if stage=="script":
        require_duration(state)
        if not data.get("duration_budget",{}).get("sections"): raise RuntimeError("script manifest 缺少分段时长预算")
        failures=caption_errors(data.get("items",[]),max_chars=int(data.get("subtitle_max_chars",12))) if data.get("subtitles_enabled",True) else []
        if failures: raise RuntimeError(f"script 字幕检查失败：{failures[:5]}")
    duration_check=None
    if stage in ("script","audio"):
        items=data.get("items",[])
        duration_check=enforce_duration(state,items,stage)
    elif stage=="visual":
        # A malformed visual manifest with no main track must reach preflight,
        # where the concrete material error is reported instead of being masked
        # by a generic zero-duration lock failure.
        items=[x for x in data.get("items",[]) if x.get("role","main")=="main"]
        if items: duration_check=enforce_duration(state,items,stage)
    if pos:
        expected=state["locks"][STAGES[pos-1]]["hash"]
        if data.get("upstream_hash") != expected:
            raise RuntimeError(f"{stage} upstream_hash 与已锁定的 {STAGES[pos-1]} 不一致")
    if not data.get("human_approved",False) and not a.allow_unapproved: raise RuntimeError("manifest 尚未标记 human_approved=true")
    invalidate(state,stage,f"{stage} relocked")
    state["locks"][stage]={"valid":True,"input":str(inp),"hash":canonical_hash(inp),"locked_at":now(),"human_approved":bool(data.get("human_approved")),"duration_check":duration_check if stage in ("script","audio","visual") else None}
    write_json(p/"project-state.json",state)
    print(json.dumps({"ok":True,"stage":stage,"hash":state["locks"][stage]["hash"],"invalidated":STAGES[pos+1:]},ensure_ascii=False))


def payload_stats(obj) -> tuple[int,int,int]:
    text_chars=0; images=0; segments=0
    def walk(x):
        nonlocal text_chars,images,segments
        if isinstance(x,str):
            text_chars += len(x)
            if x.lower().endswith((".jpg",".jpeg",".png",".webp")): images+=1
        elif isinstance(x,list):
            segments=max(segments,len(x))
            for y in x: walk(y)
        elif isinstance(x,dict):
            for y in x.values(): walk(y)
    walk(obj); return text_chars,images,segments


def cmd_gate(a):
    p=project(a.project); state=read_json(p/"project-state.json"); path=Path(a.payload); obj=read_json(path); chars,images,segments=payload_stats(obj); b=state["budget"]
    failures=[]
    if chars>b["max_text_chars"]: failures.append(f"text_chars {chars}>{b['max_text_chars']}")
    if segments>b["max_candidate_segments"]: failures.append(f"segments {segments}>{b['max_candidate_segments']}")
    if images>b["max_contact_sheets"]: failures.append(f"images {images}>{b['max_contact_sheets']}")
    if path.stat().st_size>b["max_manifest_bytes"] and a.stage!="script": failures.append(f"bytes {path.stat().st_size}>{b['max_manifest_bytes']}")
    if state["usage"]["high_model_calls"] > b["high_model_calls"]: failures.append("high model call budget exceeded")
    if state["usage"]["fast_model_calls"] > b["fast_model_calls"]: failures.append("fast model call budget exceeded")
    print(json.dumps({"ok":not failures,"stage":a.stage,"stats":{"bytes":path.stat().st_size,"text_chars":chars,"images":images,"max_list_items":segments},"failures":failures,"action":"review" if not failures else "degrade_to_manifest_only"},ensure_ascii=False))
    if failures: raise SystemExit(2)


def cmd_record_call(a):
    p=project(a.project); state=read_json(p/"project-state.json"); key=f"{a.tier}_model_calls"
    if state["usage"][key] >= state["budget"][key]:
        print(json.dumps({"ok":False,"tier":a.tier,"used":state["usage"][key],"limit":state["budget"][key],"action":"degrade_to_manifest_only"},ensure_ascii=False))
        raise SystemExit(2)
    state["usage"][key]+=1; write_json(p/"project-state.json",state)
    print(json.dumps({"ok":True,"tier":a.tier,"used":state["usage"][key],"remaining":state["budget"][key]-state["usage"][key]},ensure_ascii=False))


def cmd_status(a):
    p=project(a.project); state=read_json(p/"project-state.json"); idx=p/"source-index.json"; candidates=p/"candidates.json"
    out={"project":state["name"],"source":state["source"],"duration":state.get("duration",{"status":"pending"}),"delivery_copy_ready":(p/"qa"/"delivery-copy.json").exists(),"media_count":len(read_json(idx).get("items",[])) if idx.exists() else 0,"transcript_cache_count":len(list((p/"transcript").glob("*.json"))),"candidate_count":read_json(candidates).get("count",0) if candidates.exists() else 0,"usage":state["usage"],"locks":{k:(v and {"valid":v.get("valid"),"hash":v.get("hash","")[:12]}) for k,v in state["locks"].items()}}
    print(json.dumps(out,ensure_ascii=False))


def cmd_validate(a):
    p=project(a.project); errors=[]; state=read_json(p/"project-state.json")
    if state.get("schema_version")!=SCHEMA: errors.append("project-state schema version")
    try: spec=require_duration(state)
    except Exception as exc: errors.append(str(exc)); spec=None
    for s in STAGES:
        lock=state["locks"].get(s)
        if lock and lock.get("valid"):
            path=Path(lock["input"])
            if not path.exists(): errors.append(f"{s}: missing manifest")
            elif canonical_hash(path)!=lock["hash"]: errors.append(f"{s}: manifest changed after lock")
    draft_validation=None; build_path=p/"qa"/"build.json"
    if build_path.exists():
        build=read_json(build_path); target=Path(build.get("draft",""))
        try:
            codec,_=jianying_codec(); draft_validation=verify_jianying_draft(target,target.parent,codec,jianying_user_data())
            errors.extend(draft_validation["errors"])
            if spec and draft_validation.get("duration_us"):
                check=duration_result(spec,float(draft_validation["duration_us"])/1_000_000)
                if check["status"]!="within": errors.append(f"draft duration outside contract: {check}")
        except Exception as exc:
            errors.append(f"draft validation failed: {exc}")
    print(json.dumps({"ok":not errors,"errors":errors,"draft_validation":draft_validation},ensure_ascii=False))
    if errors: raise SystemExit(2)


def parser():
    ap=argparse.ArgumentParser(description="低额度装修视频剪辑工作台")
    sp=ap.add_subparsers(dest="cmd",required=True)
    p=sp.add_parser("content-gate");p.add_argument("--srt");p.add_argument("--manifest");p.add_argument("--target-seconds",type=float,default=DEFAULT_SCRIPT_FLOW_DURATION["target_seconds"]);p.add_argument("--min-seconds",type=float,default=DEFAULT_SCRIPT_FLOW_DURATION["min_seconds"]);p.add_argument("--max-seconds",type=float,default=DEFAULT_SCRIPT_FLOW_DURATION["max_seconds"]);p.set_defaults(func=cmd_content_gate)
    p=sp.add_parser("init"); p.add_argument("--project",required=True);p.add_argument("--source",required=True);p.add_argument("--name",required=True);p.add_argument("--target-seconds",type=float);p.add_argument("--min-seconds",type=float);p.add_argument("--max-seconds",type=float);p.add_argument("--reference");p.set_defaults(func=cmd_init)
    p=sp.add_parser("set-duration");p.add_argument("--project",required=True);p.add_argument("--target-seconds",type=float);p.add_argument("--min-seconds",type=float);p.add_argument("--max-seconds",type=float);p.add_argument("--reference");p.add_argument("--source",choices=["user","reference","inferred"],default="user");p.set_defaults(func=cmd_set_duration)
    p=sp.add_parser("set-delivery-copy");p.add_argument("--project",required=True);p.add_argument("--video-title",required=True);p.add_argument("--poster-title",required=True);p.set_defaults(func=cmd_set_delivery_copy)
    p=sp.add_parser("ingest");p.add_argument("--project",required=True);p.add_argument("--proxies",action="store_true",help="兼容旧流程；新任务应在 audio 锁定后用 prepare-visuals");p.add_argument("--contact-sheets",action="store_true",help="兼容旧流程；新任务应在 audio 锁定后用 prepare-visuals");p.set_defaults(func=cmd_ingest)
    p=sp.add_parser("prepare-visuals");p.add_argument("--project",required=True);p.add_argument("--scope",choices=["selected","all"],default="selected");p.add_argument("--proxies",action="store_true");p.add_argument("--contact-sheets",action="store_true");p.set_defaults(func=cmd_prepare_visuals)
    p=sp.add_parser("transcribe");p.add_argument("--project",required=True);p.add_argument("--model",default="small");p.add_argument("--compute-type",default="int8");p.add_argument("--language",default="zh");p.add_argument("--min-duration",type=float,default=20);p.set_defaults(func=cmd_transcribe)
    p=sp.add_parser("build-audio-preview");p.add_argument("--project",required=True);p.add_argument("--output");p.set_defaults(func=cmd_build_audio_preview)
    p=sp.add_parser("search");p.add_argument("--project",required=True);p.add_argument("--keywords",required=True);p.add_argument("--context-segments",type=int,default=1);p.add_argument("--max-results",type=int,default=80);p.set_defaults(func=cmd_search)
    p=sp.add_parser("lock");p.add_argument("--project",required=True);p.add_argument("--stage",choices=STAGES,required=True);p.add_argument("--input",required=True);p.add_argument("--allow-unapproved",action="store_true");p.set_defaults(func=cmd_lock)
    p=sp.add_parser("gate");p.add_argument("--project",required=True);p.add_argument("--payload",required=True);p.add_argument("--stage",choices=STAGES,required=True);p.set_defaults(func=cmd_gate)
    p=sp.add_parser("record-call");p.add_argument("--project",required=True);p.add_argument("--tier",choices=["high","fast"],required=True);p.set_defaults(func=cmd_record_call)
    p=sp.add_parser("record-review");p.add_argument("--project",required=True);p.add_argument("--stage",choices=STAGES+['final'],required=True);p.add_argument("--tier",choices=["high","fast"],required=True);p.add_argument("--payload",required=True);p.add_argument("--duration-seconds",type=float,default=0);p.set_defaults(func=cmd_record_review)
    p=sp.add_parser("import-manifest");p.add_argument("--project",required=True);p.add_argument("--manifest",required=True);p.add_argument("--source-root");p.add_argument("--human-approved",action="store_true");p.set_defaults(func=cmd_import_manifest)
    p=sp.add_parser("index-manifest-sources");p.add_argument("--project",required=True);p.set_defaults(func=cmd_index_manifest_sources)
    p=sp.add_parser("lock-all");p.add_argument("--project",required=True);p.add_argument("--allow-unapproved",action="store_true");p.set_defaults(func=cmd_lock_all)
    p=sp.add_parser("preflight");p.add_argument("--project",required=True);p.set_defaults(func=cmd_preflight)
    p=sp.add_parser("overlay-handoff");p.add_argument("--project",required=True);p.set_defaults(func=cmd_overlay_handoff)
    p=sp.add_parser("build-jianying");p.add_argument("--project",required=True);p.add_argument("--draft-root",required=True);p.add_argument("--name",required=True);p.set_defaults(func=cmd_build_jianying)
    p=sp.add_parser("status");p.add_argument("--project",required=True);p.set_defaults(func=cmd_status)
    p=sp.add_parser("validate");p.add_argument("--project",required=True);p.set_defaults(func=cmd_validate)
    return ap


if __name__ == "__main__":
    args=parser().parse_args()
    try: args.func(args)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False),file=sys.stderr); raise SystemExit(1)
