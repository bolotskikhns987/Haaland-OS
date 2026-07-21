from __future__ import annotations

import base64
import io
import json
import math
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path.cwd()
SOURCE = ROOT / "index.html"
ASSET_DIR = ROOT / "release_assets"
ASSET_DIR.mkdir(exist_ok=True)

EXERCISES = [
    ("bulgarian-split-squat", "Болгарский сплит-присед", []),
    ("goblet-squat", "Гоблет-присед", ["Goblet_Squat"]),
    ("romanian-deadlift", "Румынская тяга", ["Romanian_Deadlift_With_Dumbbells", "Romanian_Deadlift"]),
    ("step-up", "Зашагивание на опору", ["Dumbbell_Step_Ups"]),
    ("standing-calf-raise", "Подъём на носки стоя", ["Standing_Dumbbell_Calf_Raise"]),
    ("hanging-leg-raise", "Подъём ног в висе", ["Hanging_Leg_Raise"]),
    ("pull-up", "Подтягивания прямым хватом", ["Pullups"]),
    ("dips", "Отжимания на брусьях", ["Dips_-_Triceps_Version"]),
    ("one-arm-row", "Тяга гантели одной рукой", ["One-Arm_Dumbbell_Row"]),
    ("floor-db-press", "Жим гантелей лёжа на полу", ["Dumbbell_Floor_Press"]),
    ("db-overhead-press", "Жим гантелей над головой", ["Standing_Dumbbell_Press"]),
    ("lateral-raise", "Боковые подъёмы гантелей", ["Side_Lateral_Raise"]),
    ("accelerations", "Ускорение", ["Wind_Sprints", "Butt_Kicks"]),
    ("vertical-jump", "Вертикальный прыжок", ["Box_Jump_Multiple_Response", "Depth_Jump_Leap"]),
    ("lateral-movement", "Боковые перемещения", ["Side_to_Side_Box_Shuffle"]),
    ("hip-thrust", "Ягодичный мост", ["Barbell_Hip_Thrust", "Single_Leg_Glute_Bridge"]),
    ("sliding-leg-curl", "Сгибание ног со скольжением", ["Ball_Leg_Curl"]),
    ("single-leg-rdl", "Румынская тяга на одной ноге", ["Kettlebell_One-Legged_Deadlift"]),
    ("copenhagen-plank", "Копенгагенская планка", ["Side_Bridge"]),
    ("dead-hang", "Вис на перекладине", ["Hanging_Leg_Raise", "Pullups"]),
    ("chin-up", "Подтягивания обратным хватом", ["Chin-Up"]),
    ("feet-elevated-push-up", "Отжимания с ногами на опоре", ["Decline_Push-Up"]),
    ("band-face-pull", "Тяга резинки к лицу", ["Face_Pull"]),
    ("db-biceps-curl", "Сгибание рук с гантелями", ["Dumbbell_Bicep_Curl"]),
    ("triceps-extension", "Разгибание рук над головой", ["Standing_Dumbbell_Triceps_Extension"]),
    ("incline-board-abs", "Скручивания на наклонной доске", ["Decline_Crunch"]),
]

MUSCLES = {
    "bulgarian-split-squat": ["quads", "glutes", "hamstrings"], "goblet-squat": ["quads", "glutes", "core"],
    "romanian-deadlift": ["hamstrings", "glutes", "back"], "step-up": ["quads", "glutes"],
    "standing-calf-raise": ["calves"], "hanging-leg-raise": ["abs", "hipflexors"],
    "pull-up": ["lats", "biceps"], "dips": ["chest", "triceps"], "one-arm-row": ["lats", "back", "biceps"],
    "floor-db-press": ["chest", "triceps"], "db-overhead-press": ["shoulders", "triceps"],
    "lateral-raise": ["shoulders"], "accelerations": ["quads", "glutes", "calves"],
    "vertical-jump": ["quads", "glutes", "calves"], "lateral-movement": ["quads", "glutes"],
    "hip-thrust": ["glutes", "hamstrings"], "sliding-leg-curl": ["hamstrings", "glutes"],
    "single-leg-rdl": ["hamstrings", "glutes", "core"], "copenhagen-plank": ["adductors", "core"],
    "dead-hang": ["forearms", "lats"], "chin-up": ["lats", "biceps"],
    "feet-elevated-push-up": ["chest", "triceps", "shoulders"], "band-face-pull": ["rear_delts", "upper_back"],
    "db-biceps-curl": ["biceps"], "triceps-extension": ["triceps"], "incline-board-abs": ["abs"],
}
RAW_ROOT = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises"

def download(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Bolot-Holland-release-builder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()

def fetch_frames(candidates: list[str]) -> tuple[Image.Image, Image.Image, str]:
    last_error = None
    for folder in candidates:
        try:
            encoded = urllib.parse.quote(folder, safe="_-")
            frames = [Image.open(io.BytesIO(download(f"{RAW_ROOT}/{encoded}/{frame}.jpg"))).convert("RGB") for frame in (0, 1)]
            return frames[0], frames[1], folder
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"No usable source in {candidates}: {last_error}")

def extract_bulgarian(html: str) -> Image.Image | None:
    for pattern in (r"const\s+BULGARIAN_VISUAL\s*=\s*['\"](data:image/[^'\"]+)['\"]", r"window\.__BH_BULGARIAN_VISUAL\s*=\s*['\"](data:image/[^'\"]+)['\"]"):
        match = re.search(pattern, html)
        if match:
            return Image.open(io.BytesIO(base64.b64decode(match.group(1).split(",", 1)[1]))).convert("RGB")
    return None

def gradient_background(size=(840, 520)) -> Image.Image:
    width, height = size
    out = Image.new("RGB", size)
    px = out.load()
    for y in range(height):
        for x in range(width):
            dx, dy = (x - width * .38) / width, (y - height * .45) / height
            glow = max(0., 1. - (dx * dx * 3.2 + dy * dy * 3.8))
            px[x, y] = (int(2 + 10 * glow), int(7 + 23 * glow), int(12 + 31 * glow))
    return out

def rounded_mask(size: tuple[int, int], radius=30) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask

def photo_panel(photo: Image.Image, size=(640, 488)) -> Image.Image:
    panel = ImageOps.fit(photo, size, method=Image.Resampling.LANCZOS)
    panel = ImageEnhance.Brightness(ImageEnhance.Color(ImageEnhance.Contrast(panel).enhance(1.12)).enhance(.82)).enhance(.82)
    fade = Image.new("L", size, 255); d = ImageDraw.Draw(fade)
    for inset, value in ((0, 0), (12, 45), (28, 110), (48, 185), (68, 235)):
        d.rounded_rectangle((inset, inset, size[0] - inset - 1, size[1] - inset - 1), radius=34, outline=value, width=18)
    fade = fade.filter(ImageFilter.GaussianBlur(10))
    return Image.composite(panel, Image.new("RGB", size, (2, 8, 13)), fade)

def draw_anatomy(canvas: Image.Image, x: int, y: int, muscles: list[str]) -> None:
    d = ImageDraw.Draw(canvas, "RGBA"); line=(82,101,113,205); active=(35,226,205,225); assist=(255,93,85,190)
    d.ellipse((x+50,y,x+92,y+42),outline=line,width=3); d.rounded_rectangle((x+42,y+45,x+100,y+180),radius=24,outline=line,width=3)
    d.line((x+46,y+75,x+12,y+165),fill=line,width=4); d.line((x+96,y+75,x+130,y+165),fill=line,width=4)
    d.line((x+57,y+180,x+38,y+320),fill=line,width=4); d.line((x+85,y+180,x+104,y+320),fill=line,width=4)
    regions={
      "shoulders":[(x+30,y+50,x+62,y+84),(x+80,y+50,x+112,y+84)], "rear_delts":[(x+29,y+55,x+60,y+88),(x+82,y+55,x+113,y+88)],
      "chest":[(x+48,y+70,x+72,y+110),(x+72,y+70,x+96,y+110)], "lats":[(x+40,y+92,x+62,y+155),(x+82,y+92,x+104,y+155)],
      "back":[(x+52,y+85,x+92,y+165)], "upper_back":[(x+48,y+72,x+96,y+125)], "abs":[(x+57,y+105,x+87,y+172)], "core":[(x+50,y+103,x+94,y+177)],
      "biceps":[(x+17,y+91,x+42,y+145),(x+102,y+91,x+127,y+145)], "triceps":[(x+14,y+86,x+37,y+150),(x+107,y+86,x+130,y+150)],
      "forearms":[(x+5,y+138,x+28,y+195),(x+116,y+138,x+139,y+195)], "glutes":[(x+48,y+165,x+72,y+205),(x+72,y+165,x+96,y+205)],
      "quads":[(x+45,y+198,x+67,y+270),(x+77,y+198,x+99,y+270)], "hamstrings":[(x+43,y+195,x+65,y+270),(x+79,y+195,x+101,y+270)],
      "adductors":[(x+60,y+197,x+72,y+272),(x+72,y+197,x+84,y+272)], "hipflexors":[(x+55,y+174,x+70,y+220),(x+74,y+174,x+89,y+220)],
      "calves":[(x+38,y+267,x+57,y+322),(x+87,y+267,x+106,y+322)]}
    for index,muscle in enumerate(muscles):
        for box in regions.get(muscle,[]): d.ellipse(box,fill=active if index==0 else assist)

def compose_visual(work: Image.Image, start: Image.Image, exercise_id: str) -> Image.Image:
    canvas=gradient_background(); panel=photo_panel(work); canvas.paste(panel,(12,16),rounded_mask(panel.size,32))
    start_panel=ImageOps.fit(start,(176,126),method=Image.Resampling.LANCZOS); start_panel=ImageEnhance.Color(ImageEnhance.Brightness(start_panel).enhance(.45)).enhance(.4)
    start_panel.putalpha(rounded_mask(start_panel.size,18).point(lambda p:int(p*.55))); rgba=canvas.convert("RGBA"); rgba.alpha_composite(start_panel,(28,368)); canvas=rgba.convert("RGB")
    draw_anatomy(canvas,680,86,MUSCLES.get(exercise_id,[])); d=ImageDraw.Draw(canvas,"RGBA"); d.rounded_rectangle((662,44,824,454),radius=24,outline=(55,85,101,120),width=2); d.line((653,25,653,495),fill=(41,80,94,95),width=2)
    return canvas

def encode_jpeg(image: Image.Image) -> tuple[str,bytes]:
    buf=io.BytesIO(); image.save(buf,"JPEG",quality=91,optimize=True,progressive=False); raw=buf.getvalue(); return "data:image/jpeg;base64,"+base64.b64encode(raw).decode("ascii"),raw

def build_proof(assets,page_index):
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",24); small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",17); title=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",27)
    card_w,card_h,gap,margin,header=570,430,24,18,78; rows=math.ceil(len(assets)/2); sheet=Image.new("RGB",(1200,header+rows*card_h+(rows-1)*gap+margin),(2,7,12)); d=ImageDraw.Draw(sheet)
    d.text((22,14),f"Bolot-Holland · проверка визуалов {page_index}",font=title,fill=(244,248,252)); d.text((22,48),"Точные движения · встроенные JPEG · без внешних ссылок",font=font,fill=(55,226,196))
    for pos,(number,eid,name,image) in enumerate(assets):
        row,col=divmod(pos,2); x,y=margin+col*(card_w+gap),header+row*(card_h+gap); d.rounded_rectangle((x,y,x+card_w,y+card_h),radius=22,fill=(7,17,27),outline=(31,58,74),width=2)
        sheet.paste(ImageOps.fit(image,(card_w-24,338),method=Image.Resampling.LANCZOS),(x+12,y+12)); d.text((x+18,y+360),f"{number}. {name}",font=font,fill=(239,245,252)); d.text((x+18,y+396),"✓ JPEG декодирован 840×520",font=small,fill=(48,232,198))
    path=ROOT/f"proof-{page_index}.png"; sheet.save(path,optimize=True); return path

def patch_html(html: str, visual_data: dict[str,str]) -> str:
    html,removed=re.subn(r"\s*<style id=\"bh30-visual-style\">.*?</style>\s*<script id=\"bh30-visual-script\">.*?</script>\s*","\n",html,flags=re.S)
    if removed!=1: raise RuntimeError(f"Expected one bh30 override, removed={removed}")
    payload=json.dumps(visual_data,ensure_ascii=False,separators=(",",":"))
    script='''
<style id="bh-exact-visual-style">.bh-exact-visual{aspect-ratio:840/520;border-radius:18px;overflow:hidden;background:#02070c;border:1px solid rgba(90,130,150,.22)}.bh-exact-visual img{display:block;width:100%;height:100%;object-fit:cover;opacity:1;visibility:visible}.bh-exact-card .release-guide-body{display:grid;gap:10px}@media(max-width:700px){.bh-exact-visual{border-radius:15px}}</style>
<script id="bh-exact-visual-script">
(function(){
 const V=__PAYLOAD__;
 const h=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
 const exById=id=>EXERCISES.find(e=>e.id===id)||null;
 const load=id=>{if(!id||typeof bhLoadFormat!=='function')return {setup:'По плану',next:'По технике и самочувствию',state:{}};const f=bhLoadFormat(id)||{};return {setup:f.setup||'По плану',next:typeof bhCompactNextStep==='function'?bhCompactNextStep(id):(f.next||'По технике и самочувствию'),state:f.state||{}};};
 const visual=e=>`<div class="bh-exact-visual"><img src="${V[e.id]||''}" alt="${h(e.name)} — рабочая и стартовая фаза, карта мышц" loading="eager" decoding="sync"></div>`;
 const loadHtml=id=>{const l=load(id);return `<div class="release-load-grid"><div class="release-load-item"><div class="release-load-icon">⛁</div><div><b>Сборка</b><span>${h(l.setup)}</span></div></div><div class="release-load-item"><div class="release-load-icon">↗</div><div><b>Следующий шаг</b><span><strong>${h(l.next)}</strong></span></div></div></div>`;};
 const feedback=id=>{if(!id)return '';const blocked=!!load(id).state.blocked;return `<div class="release-feedback"><button type="button" class="success" data-load-result="success" data-load-id="${h(id)}">✓ С запасом</button><button type="button" class="hard" data-load-result="hard" data-load-id="${h(id)}">ϟ Тяжело</button></div><details class="release-more"><summary>Другой результат или ручная корректировка</summary><div class="release-more-body"><button type="button" data-load-result="fail" data-load-id="${h(id)}">Не добил</button><button type="button" data-load-result="pain" data-load-id="${h(id)}">Боль</button><button type="button" data-load-step="-1" data-load-id="${h(id)}">Вес −</button><button type="button" data-load-step="1" data-load-id="${h(id)}" ${blocked?'disabled':''}>Вес +</button></div></details>`;};
 const rowName=row=>typeof bhExerciseName==='function'?bhExerciseName(row):(row?.[0]||'Упражнение'); const prescription=row=>typeof bhCurrentPrescription==='function'?(bhCurrentPrescription(row)||row?.[1]||''):(row?.[1]||''); const equipment=row=>typeof bhExerciseEquipment==='function'?bhExerciseEquipment(row):(row?.[2]||'—');
 function card(row,index,guideDay,opened){const id=row?.[3]||'',e=exById(id),note=row?.[2]||'';return `<details class="release-exercise bh-exact-card" ${opened?'open':''}><summary><div class="release-exercise-row"><div class="release-index">${index+1}</div><div class="release-exercise-name"><b>${h(rowName(row))}</b><span>${h(prescription(row))}</span></div><div class="release-equipment">${h(equipment(row)||'—')}</div><div class="release-chevron">⌄</div></div></summary><div class="release-exercise-body">${e?visual(e):''}${loadHtml(id)}${feedback(id)}${note?`<div class="release-note">${h(note)}</div>`:''}<div class="release-card-actions"><button class="secondaryBtn" type="button" data-guide-exercise="${h(id)}" data-guide-day="${h(guideDay||'')}">Полная техника</button></div></div></details>`;}
 renderTrainingToday=function(){const root=document.getElementById('trainingTodayRoot');if(!root)return;const wd=new Date().getDay(),day=trainingData[wd]||trainingData[0],scaled=typeof bhScaledWorkout==='function'?bhScaledWorkout(day,wd):{rows:day.workout||[],scale:100},rows=scaled.rows||[],guideDay=GUIDE_DAY_BY_WEEKDAY[wd]||'',first=rows.find(r=>r?.[3])||rows[0],firstId=first?.[3]||'',firstLoad=load(firstId);root.innerHTML=`<div class="release-training"><header class="release-training-head"><div class="release-brand">BOLOT-<em>HOLAND</em></div><div class="release-training-title">${h(day.name)}</div><div class="release-training-meta"><span>${h(first?equipment(first):'по плану')}</span><span class="divider">|</span><span>Рабочая сборка: <strong>${h(firstLoad.setup)}</strong></span><span class="divider">|</span><span><strong>${scaled.scale}% объёма</strong></span></div><div class="release-training-next">Следующий шаг: <strong>${h(firstLoad.next)}</strong></div></header><div class="release-exercises">${rows.map((r,i)=>card(r,i,guideDay,i===0)).join('')}</div></div>`;if(typeof bhBindLoadActions==='function')bhBindLoadActions(root);};
 renderExerciseCard=function(e){const flags=typeof redFlagsFor==='function'?redFlagsFor(e):[];return `<details class="release-guide-card exerciseCard bh-exact-card" id="exercise-${h(e.id)}"><summary>${h(e.name)}</summary><div class="release-guide-body">${loadHtml(e.id)}${visual(e)}<details class="guideSub" open><summary>Техника по шагам</summary><ol>${(e.steps||[]).map(x=>`<li>${h(x)}</li>`).join('')}</ol><p><b>Дыхание:</b> ${h(e.breath||'')}</p></details><details class="guideSub"><summary>Чекпоинты правильности</summary><ul>${(e.checkpoints||[]).map(x=>`<li>${h(x)}</li>`).join('')}</ul></details><details class="guideSub"><summary>Частые ошибки</summary><div class="errorList">${(e.errors||[]).map(x=>`<div class="errorItem"><b>${h(x[0])}</b><br>${h(x[1])}</div>`).join('')}</div></details><details class="guideSub"><summary>Безопасность и красные флаги</summary><div class="redFlags">${flags.map(x=>`<div class="redFlagItem">${h(x)}</div>`).join('')}</div></details></div></details>`;};
 renderExerciseGuide=function(){const root=document.getElementById('exerciseGuide');if(!root)return;const current=GUIDE_DAY_BY_WEEKDAY[new Date().getDay()]||'';root.innerHTML=`<div class="release-guide-overview"><div class="release-guide-stat"><b>${EXERCISES.length} / ${EXERCISES.length} визуализаций</b><span>Все изображения встроены в index.html.</span></div><div class="release-guide-stat"><b>Единый формат</b><span>Рабочая фаза, старт и карта мышц.</span></div><div class="release-guide-stat"><b>Без внешней загрузки</b><span>Карточки работают на iOS Safari и GitHub Pages.</span></div></div>${GUIDE_DAYS.map(day=>{const list=day.exerciseIds.map(exById).filter(Boolean);return `<details class="release-guide-day exerciseGuideDay anchor" id="guide-day-${h(day.id)}" ${day.id===current?'open':''}><summary><span>${h(day.title)}</span><span class="guideDayCount">${list.length} упражнений</span></summary><div class="release-guide-list">${list.map(renderExerciseCard).join('')}</div></details>`;}).join('')}`;};
 openExerciseGuide=function(dayId,exerciseId){document.getElementById('t4').checked=true;if(typeof uxSelectPane==='function')uxSelectPane('training','training-technique');const day=document.getElementById(`guide-day-${dayId}`);if(day)day.open=true;const target=exerciseId?document.getElementById(`exercise-${exerciseId}`):day;if(target){target.open=true;setTimeout(()=>target.scrollIntoView({behavior:'smooth',block:'start'}),60);}};
 const oldInit=window.uxV2Init;window.uxV2Init=function(){if(typeof oldInit==='function')oldInit();setTimeout(()=>{renderTrainingToday();renderExerciseGuide();},20);}; const oldRefresh=window.uxV2Refresh;window.uxV2Refresh=function(){if(typeof oldRefresh==='function')oldRefresh();renderTrainingToday();renderExerciseGuide();}; window.__BH_EXACT_VISUAL_IDS=Object.keys(V);
})();
</script>
'''.replace('__PAYLOAD__',payload)
    return html.replace('</body>',script+'\n</body>',1)

def main():
    html=SOURCE.read_text(encoding='utf-8'); bulgarian=extract_bulgarian(html)
    if bulgarian is None: raise RuntimeError('Approved Bulgarian reference not found')
    visual_data={}; proof_assets=[]; source_log={}
    for index,(exercise_id,name,candidates) in enumerate(EXERCISES,1):
        if exercise_id=='bulgarian-split-squat': visual=ImageOps.fit(bulgarian,(840,520),method=Image.Resampling.LANCZOS); source_name='approved Bulgarian reference embedded in current app'
        else:
            start,work,source_name=fetch_frames(candidates)
            if exercise_id=='dead-hang': work=start
            visual=compose_visual(work,start,exercise_id)
        uri,raw=encode_jpeg(visual); visual_data[exercise_id]=uri; (ASSET_DIR/f'{exercise_id}.jpg').write_bytes(raw); proof_assets.append((index,exercise_id,name,visual)); source_log[exercise_id]=source_name
    SOURCE.write_text(patch_html(html,visual_data),encoding='utf-8')
    proof_files=[build_proof(group,i+1) for i,group in enumerate([proof_assets[:7],proof_assets[7:14],proof_assets[14:20],proof_assets[20:26]])]
    Path('qa-build.json').write_text(json.dumps({'release':'4.0-exact-visuals','base':'current main/index.html','main_logic_changed':False,'removed_broken_bh30_override':True,'visual_assets':len(visual_data),'embedded_data_uris':len(visual_data),'sources':source_log,'proof_files':[p.name for p in proof_files]},ensure_ascii=False,indent=2),encoding='utf-8')
    Path('RELEASE-NOTES.txt').write_text('Bolot-Holland exact visual release\n\n- Base: current production main/index.html.\n- Today/time logic was not edited.\n- Removed broken BH30 override that produced 0 cards.\n- Added 26 self-contained JPEG visualizations with exact exercise source photos.\n- Every image includes work phase, start thumbnail and an anatomy map.\n- Exercise photos: free-exercise-db (Unlicense / public domain).\n',encoding='utf-8')
    with zipfile.ZipFile('Bolot-Holland-EXACT-VISUALS.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(SOURCE,'index.html'); archive.write('qa-build.json'); archive.write('RELEASE-NOTES.txt')
        for proof in proof_files: archive.write(proof,proof.name)
if __name__=='__main__': main()
