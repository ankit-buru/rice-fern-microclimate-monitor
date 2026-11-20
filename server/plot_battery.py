"""Battery plot for one board, from the test server's CSV (GET /device/<id>.csv).

    python3 plot_battery.py <board.csv> <out.png>

Needs matplotlib and numpy (pip install matplotlib numpy). Uses battery-only rows (usb false, fuel gauge present):
  top:          state of charge for each run, with a straight-line projection to empty for the latest firmware run
  bottom left:  cell voltage from "bringup" firmware (gauge in hibernate: 45 s samples, so the dips are artefacts)
  bottom right: "bringup-2" rest voltage (pre_mv, before the modem powers on) vs loaded (reg_mv, just registered)
Times are shown in this machine's local timezone.
"""
import csv, sys, datetime as dt, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt, matplotlib.dates as md
R=[r for r in csv.DictReader(open(sys.argv[1])) if r["usb"]=="False" and r["fg"]=="True"]
def T(r): return dt.datetime.fromisoformat(r["rx_time"]).astimezone().replace(tzinfo=None)
run1=[r for r in R if r["fw"]=="bringup"]; run2=[r for r in R if r["fw"]=="bringup-2"]
blue,orange,ink,sec,mut,surf,grid="#2a78d6","#eb6834","#0b0b0b","#52514e","#898781","#fcfcfb","#e6e5e1"
def style(a):
  a.set_facecolor(surf); [a.spines[s].set_visible(False) for s in ("top","right")]
  [a.spines[s].set_color(mut) for s in ("left","bottom")]; a.tick_params(colors=sec,labelsize=9); a.grid(color=grid,lw=.8); a.set_axisbelow(True)
  a.xaxis.set_major_formatter(md.DateFormatter("%a %H:%M"))
fig=plt.figure(figsize=(11,10),facecolor=surf); gs=fig.add_gridspec(2,2,height_ratios=[1.1,1])
a1=fig.add_subplot(gs[0,:]); a2=fig.add_subplot(gs[1,0]); a3=fig.add_subplot(gs[1,1],sharey=a2)
for a in (a1,a2,a3): style(a)
# --- SOC, both runs, projection from run 2
t2=np.array([T(r) for r in run2]); s2=np.array([int(r["soc_pct_x100"])/100 for r in run2])
h2=np.array([(x-t2[0]).total_seconds()/3600 for x in t2]); fit=h2>=min(1.0,h2[-1]/3)   # skip the first hour (gauge settling)
m,b=np.polyfit(h2[fit],s2[fit],1); h0=-b/m; end=t2[0]+dt.timedelta(hours=h0)
for run in (run1,run2):
  a1.plot([T(r) for r in run],[int(r["soc_pct_x100"])/100 for r in run],color=blue,lw=2)
hp=np.linspace(h2[fit][0],h0,50); a1.plot([t2[0]+dt.timedelta(hours=x) for x in hp],m*hp+b,color=sec,lw=1.5,ls="--")
a1.annotate(f"projected empty ≈ {end:%a %d %b %H:%M} \n({m:.2f} %/h, fit to run 2 after its first hour)",(end,0),xytext=(0,150),textcoords="offset points",ha="right",color=ink,fontsize=10,arrowprops=dict(arrowstyle="-",color=mut))
a1.text(T(run1[-1]),72,"run 1 (old firmware)",color=sec,fontsize=9,va="top",ha="right"); a1.text(t2[0],103,"  run 2 (recharged, bringup-2)",color=sec,fontsize=9,va="bottom")
a1.set_ylim(0,110); a1.set_ylabel("State of charge (%)",color=sec)
a1.set_title(f"Board {R[0]['id'][:4]}…{R[0]['id'][-4:]} on battery",color=ink,loc="left",fontsize=12)
# --- run 1: the gauge in hibernate
a2.plot([T(r) for r in run1],[int(r["vcell_mv"]) for r in run1],color=blue,lw=1.5,marker="o",ms=2.5)
a2.set_title("Run 1: one reading, gauge hibernating (45 s samples)",color=ink,loc="left",fontsize=10); a2.set_ylabel("Cell voltage (mV)",color=sec)
# --- run 2: rest vs loaded
a3.plot(t2,[int(r["pre_mv"]) for r in run2],color=blue,lw=1.5,marker="o",ms=2.5,label="at rest: before modem on")
a3.plot(t2,[int(r["reg_mv"]) for r in run2],color=orange,lw=1.5,marker="o",ms=2.5,label="loaded: just registered")
a3.legend(frameon=False,fontsize=9,labelcolor=sec,loc="upper right")
a3.set_title("Run 2: rest vs loaded, gauge kept active",color=ink,loc="left",fontsize=10)
for a in (a2,a3): a.xaxis.set_major_locator(md.AutoDateLocator(maxticks=6)); a.xaxis.set_major_formatter(md.DateFormatter("%H:%M"))
fig.tight_layout(); fig.savefig(sys.argv[2],dpi=120,facecolor=surf)
d=np.array([int(r["pre_mv"])-int(r["reg_mv"]) for r in run2]); off=np.array([int(r["prev_off_mv"])-int(r["pre_mv"]) for r in run2[1:]])
print(f"run2 {h2[-1]:.2f} h, {len(run2)} reports, SOC {s2[0]}->{s2[-1]}; slope {m:.2f} %/h; empty {end:%a %d %b %H:%M} (+{h0-h2[-1]:.1f} h)")
print(f"rest-loaded drop: median {np.median(d):.0f} mV, range {d.min()}..{d.max()}; off-vs-next-pre median {np.median(off):.0f}")
pre=np.array([int(r["pre_mv"]) for r in run2]); print("rest step-to-step max jump",np.abs(np.diff(pre)).max(),"mV")
cyc=[int(r["prev_cycle_ms"]) for r in run2 if int(r["prev_cycle_ms"])>0]; print("cycle ms median",np.median(cyc),"min",min(cyc),"max",max(cyc))
cr=np.array([int(r["crate_raw"]) for r in run2])*0.208; print(f"crate mean {cr.mean():.2f} %/h")
tx=[int(r["prev_post_tx"]) for r in run2]; print("post tx values",sorted(set(tx)))
print("reg_ms median",np.median([int(r["reg_ms"]) for r in run2]),"csq99",sum(r["csq"]=="99" for r in run2))
