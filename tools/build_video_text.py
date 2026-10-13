"""Offline BIKi subtitle overlay with original encoded audio packets retained."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import struct

from resource_bink import parse,members,replace_video,audio_digest


def sha(data):return hashlib.sha256(data).hexdigest()


def run(args,commands):
    p=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace')
    commands.append(dict(command=subprocess.list2cmdline(args),stdout=p.stdout,stderr=p.stderr,exit_status=p.returncode))
    if p.returncode:raise ValueError('offline video command failed: '+p.stderr[-2000:])
    return p


def build(source,plans_path,font,font_sha,encoder,encoder_sha,output):
    import shutil
    source,output=Path(source).resolve(strict=True),Path(output).resolve()
    paths=[Path(plans_path).resolve(strict=True),Path(font).resolve(strict=True),Path(encoder).resolve(strict=True)]
    if (output.exists() or output.is_relative_to(source) or source.is_relative_to(output)
            or any(p.is_relative_to(output) for p in paths)):
        raise ValueError('video output must be a new separate directory')
    snapshots={p:p.read_bytes() for p in paths};plan=json.loads(snapshots[paths[0]])
    if plan.get('schema')!=1 or sha(snapshots[paths[1]])!=font_sha or sha(snapshots[paths[2]])!=encoder_sha:
        raise ValueError('video plans, outline or encoder identity mismatch')
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:raise ValueError('offline FFmpeg tools are missing')
    output.mkdir(parents=True);work=output/'work';work.mkdir();commands=[];reports=[];seen=set()
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    outline=TTFont(paths[1],recalcTimestamp=False)
    cmap=outline.getBestCmap()
    rows=plan.get('videos')
    if not isinstance(rows,list) or not rows or any(not isinstance(row,dict) for row in rows):
        raise ValueError('invalid video plan list')
    for row in rows:
        if not isinstance(row.get('texts'),list) or not row['texts'] or any(not isinstance(t,dict) for t in row['texts']):
            raise ValueError('invalid video text list')
        for text in row['texts']:
            target=text.get('target')
            if not isinstance(target,str) or not target or any(ord(c) not in cmap for c in target if not c.isspace()):
                raise ValueError('outline font does not cover video target')
    if 'fvar' in outline:
        axes={a.axisTag:(min(a.maxValue,max(a.minValue,600)) if a.axisTag=='wght' else a.defaultValue)
              for a in outline['fvar'].axes}
        outline=instantiateVariableFont(outline,axes,inplace=True)
    for item in outline['name'].names:
        if item.nameID in (1,4,6,16,25):
            item.string='Locale Video Overlay'.encode(item.getEncoding())
        elif item.nameID in (2,17):item.string='Regular'.encode(item.getEncoding())
    render_font=work/'LocaleVideoOverlay.ttf';outline.save(render_font);outline.close()
    originals={};pak_outputs={}
    for row in plan.get('videos',[]):
        relative=row['resource']
        if (not isinstance(relative,str) or ':' in relative or '\\' in relative
                or Path(relative).is_absolute() or '..' in Path(relative).parts):raise ValueError('invalid video resource path')
        path=source/relative
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):raise ValueError('linked video resource')
        raw=path.read_bytes();originals[path]=raw
        if sha(raw)!=row['source_sha256']:raise ValueError('original video source digest mismatch')
        index=row.get('member_index');key=(relative,index)
        if key in seen:raise ValueError('duplicate video target')
        seen.add(key)
        if index is not None:
            pieces=members(raw)
            if type(index) is not int or not 0<=index<len(pieces):raise ValueError('video member index outside PAK')
            start,original=pieces[index]
            if start!=row['source_offset']:raise ValueError('PAK member offset mismatch')
        else:original=raw;start=0
        if sha(original)!=row['member_sha256']:raise ValueError('video member digest mismatch')
        table=parse(original);label=row['id'];folder=work/label
        if not isinstance(label,str) or Path(label).name!=label or ':' in label:raise ValueError('invalid video target label')
        folder.mkdir();input_path=folder/'original.bik';input_path.write_bytes(original)
        filters=[]
        for ordinal,text in enumerate(row['texts']):
            if (not isinstance(text.get('target'),str) or not text['target'] or '\0' in text['target']
                    or not text.get('source_text_evidence')
                    or type(text.get('start_frame')) is not int or type(text.get('end_frame')) is not int
                    or not 0<=text['start_frame']<=text['end_frame']<len(table['frames'])):
                raise ValueError('invalid or unreviewed video text target')
            caption=folder/f'caption-{ordinal:03}.txt';caption.write_text(text['target'],encoding='utf8')
            fp=render_font.as_posix().replace(':','\\:')
            fontsize=text.get('font_size',22)
            if type(fontsize) is not int or not 10<=fontsize<=64:raise ValueError('invalid video font size')
            y=text.get('y',table['height']-48)
            if type(y) is not int or not 0<=y<table['height']-fontsize:raise ValueError('video caption outside safe area')
            lines=text['target'].split('\n')
            if y+len(lines)*(fontsize+8)>table['height']-16:raise ValueError('video caption block exceeds bottom safe area')
            from PIL import ImageFont
            face=ImageFont.truetype(str(render_font),fontsize)
            for line_number,line in enumerate(lines):
                if face.getlength(line)>table['width']-48:raise ValueError('video caption exceeds horizontal safe area')
                line_path=folder/f'caption-{ordinal:03}-line-{line_number:02}.txt';line_path.write_text(line,encoding='utf8')
                tp=line_path.as_posix().replace(':','\\:')
                filters.append(f"drawtext=fontfile='{fp}':textfile='{tp}':expansion=none:fontsize={fontsize}:fontcolor=white:"
                               f"borderw=2:bordercolor=black:x=(w-tw)/2:y={y+line_number*(fontsize+8)}:enable='between(n,{text['start_frame']},{text['end_frame']})'")
        if not filters:raise ValueError('video target has no translated texts')
        intermediate=folder/'overlay.mp4'
        run([ffmpeg,'-v','error','-nostdin','-i',str(input_path),'-map','0:v:0','-an','-vf',','.join(filters),
             '-c:v','libx264','-crf','10','-preset','medium','-pix_fmt','yuv420p','-fps_mode','passthrough',str(intermediate)],commands)
        video_path=folder/'video-only.bik'
        rate=table['fps'][0]/table['fps'][1]
        data_rate=row.get('data_rate',max(100000,int(len(original)*rate/len(table['frames'])*0.9)))
        if type(data_rate) is not int or not 1000<=data_rate<=10000000:raise ValueError('invalid Bink data rate')
        # Hide the compressor helper. Never call BinkPlay, a game executable,
        # installer or the original game DLL.
        startup=None
        if hasattr(subprocess,'STARTUPINFO'):
            startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        args=[str(paths[2]),'binkc',str(intermediate),str(video_path),'/V100',f'/F{rate:g}',f'/D{data_rate}',
              '/L-1','/{0','/:0','/}0','/#']
        p=subprocess.run(args,startupinfo=startup,capture_output=True,text=True,encoding='utf8',errors='replace')
        commands.append(dict(command=subprocess.list2cmdline(args),stdout=p.stdout,stderr=p.stderr,exit_status=p.returncode))
        if p.returncode or not video_path.is_file():raise ValueError('Bink1 compressor failed')
        video=video_path.read_bytes();replacement=replace_video(original,video,len(original) if index is not None else None)
        if audio_digest(replacement)!=audio_digest(original):raise ValueError('original video audio packet changed')
        dest=folder/'remux.bik';dest.write_bytes(replacement)
        run([ffmpeg,'-v','error','-nostdin','-i',str(dest),'-f','null','-'],commands)
        checked=parse(replacement)
        if index is None:
            result=output/relative;result.parent.mkdir(parents=True,exist_ok=True);result.write_bytes(replacement)
        else:
            result=pak_outputs.setdefault(relative,bytearray(raw));result[start:start+len(original)]=replacement
        reports.append(dict(id=label,resource=relative,member_index=index,source_offset=start,
                            original_sha256=sha(original),modified_sha256=sha(replacement),
                            original_size=len(original),modified_size=len(replacement),frames=len(table['frames']),
                            fps=table['fps'],encoded_audio_sha256=audio_digest(original),audio_packets_preserved=True,
                            dimensions=[table['width'],table['height']],full_decode_exit=0,text_count=len(row['texts'])))
    for relative,raw in pak_outputs.items():
        result=output/relative;result.parent.mkdir(parents=True,exist_ok=True);result.write_bytes(raw)
        before,after=members(originals[source/relative]),members(bytes(raw))
        if [o for o,_ in before]!=[o for o,_ in after]:raise ValueError('PAK member offsets changed')
        for i,((_,a),(_,b)) in enumerate(zip(before,after)):
            if (relative,i) not in seen and a!=b:raise ValueError('untargeted video PAK member changed')
    if any(p.read_bytes()!=b for p,b in {**snapshots,**originals}.items()):raise ValueError('video build input drift')
    report=dict(schema=1,kind='offline_bink1_text_candidate',resources=reports,commands=commands,
                encoder_sha256=encoder_sha,font_sha256=font_sha,render_font_sha256=sha(render_font.read_bytes()),source_unchanged=True,
                all_game_text_complete=False,deployed=False,commercial_code_executed=False,game_started=False)
    (output/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('source','plans','font','encoder','output'):p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--font-sha256',required=True);p.add_argument('--encoder-sha256',required=True);a=p.parse_args()
    r=build(a.source,a.plans,a.font,a.font_sha256,a.encoder,a.encoder_sha256,a.output)
    print(f'VIDEO_TEXT_BUILD PASS videos={len(r["resources"])} frames={sum(x["frames"] for x in r["resources"])} '
          'audio_packets_preserved=true full_decode=true source_unchanged=true deployed=false game_started=false')
