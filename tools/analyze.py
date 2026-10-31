import librosa, numpy as np, subprocess, os, sys, json
R=["Yasser_Ad-Dussary_128kbps","Minshawy_Mujawwad_192kbps","Minshawy_Murattal_128kbps","Abdul_Basit_Mujawwad_128kbps","Maher_AlMuaiqly_64kbps","Nasser_Alqatami_128kbps","Hani_Rifai_192kbps","Fares_Abbad_64kbps","Abdullah_Matroud_128kbps","Muhammad_Jibreel_128kbps","Salah_Al_Budair_128kbps"]
verses={"20:46":[(20,46)],"94:5-6":[(94,5),(94,6)],"12:86":[(12,86)],"11:6":[(11,6)],"39:53":[(39,53)],"93:3-5":[(93,3),(93,4),(93,5)],"50:16":[(50,16)]}
out={}
for k,vs in verses.items():
  out[k]={}
  for r in R:
    ys=[]
    for s,a in vs:
      p=f"{r}/{s:03d}{a:03d}.mp3"
      if not os.path.exists(p):
        os.makedirs(r,exist_ok=True); subprocess.run(["curl","-sf","-m","60","-o",p,f"https://everyayah.com/data/{r}/{s:03d}{a:03d}.mp3"])
      y,sr=librosa.load(p,sr=16000); ys.append(y)
    y=np.concatenate(ys); dur=len(y)/16000
    f0,vf,_=librosa.pyin(y,fmin=70,fmax=500,sr=16000,frame_length=1024)
    f=f0[~np.isnan(f0)]; st=12*np.log2(f/np.median(f))
    # pitch range (p95-p5 semitones), melodic movement, voiced share
    out[k][r.split('_')[0]+('M' if 'Mujawwad' in r else '')]=dict(dur=round(dur,1),range=round(float(np.percentile(st,95)-np.percentile(st,5)),1),move=round(float(np.mean(np.abs(np.diff(st)))),3),voiced=round(float(np.mean(vf)),2))
  print(k, json.dumps(out[k]), flush=True)
json.dump(out,open('/home/claude/reels/analysis.json','w'))
