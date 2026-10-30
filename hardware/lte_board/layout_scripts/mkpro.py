import json,sys
LONG='''/MDM_PWRKEY /MDM_PWRKEY_CTRL /MDM_PWR_EN /MDM_NETLIGHT /MDM_STATUS /MCU_MDM_STATUS /MDM_BOOT_CFG /NRST /SIM_DET /VDD_EXT /MDM_USB_VBUS /BOOT0 /DBG_TX /DBG_RX /EXP_PA0 /EXP_PA1 /EXP_PA4 /EXP_PA5 /EXP_PA6 /EXP_PA7 /EXP_PB10 /EXP_PB11 /SWDIO /SWCLK /LED_USER'''.split()
p=sys.argv[1]; d=json.load(open(p))
def nc(name,track,clr,via,drill,prio,dpw=0.2,dpg=0.15):
    return {"name":name,"track_width":track,"clearance":clr,"via_diameter":via,"via_drill":drill,
            "diff_pair_width":dpw,"diff_pair_gap":dpg,"diff_pair_via_gap":0.25,"microvia_diameter":0.3,"microvia_drill":0.1,
            "bus_width":12,"wire_width":6,"line_style":0,"pcb_color":"rgba(0, 0, 0, 0.000)",
            "schematic_color":"rgba(0, 0, 0, 0.000)","priority":prio}
ns_new={"meta":{"version":4},
  "classes":[nc("Default",0.15,0.15,0.5,0.3,2147483647),
             nc("VBAT",0.6,0.2,0.6,0.3,0),
             nc("Power",0.3,0.15,0.5,0.3,1),
             nc("RF",0.35,0.2,0.5,0.3,2),
             nc("USB",0.3,0.15,0.5,0.3,3,0.3,0.15),
             nc("Long",0.15,0.15,0.5,0.3,4),
             nc("Batt",0.4,0.15,0.5,0.3,5)],
  "net_colors":None,"netclass_assignments":None,
  "netclass_patterns":[{"netclass":"VBAT","pattern":"+3V8"},
                       {"netclass":"Power","pattern":"+5V"},{"netclass":"Power","pattern":"+3V3"},
                       {"netclass":"Power","pattern":"/BUCK_SW"},
                       {"netclass":"Batt","pattern":"/BATT_IN"},{"netclass":"Batt","pattern":"/BATT_N"},{"netclass":"Batt","pattern":"/VBAT"},{"netclass":"Batt","pattern":"/VSYS"},
                       {"netclass":"RF","pattern":"/MDM_RF"},{"netclass":"RF","pattern":"/LTE_ANT"},
                       {"netclass":"RF","pattern":"/MDM_GNSS"},{"netclass":"RF","pattern":"/GNSS_ANT"},
                       {"netclass":"USB","pattern":"/USB_D*"},{"netclass":"USB","pattern":"/MDM_USB*_D*"}]+[{"netclass":"Long","pattern":n} for n in LONG]}
ns = d.setdefault("net_settings", {})
ns["classes"] = sorted(ns_new["classes"], key=lambda c: (c["name"] != "Default", c["name"]))   # KiCad's order
ns["netclass_patterns"] = ns_new["netclass_patterns"]
for k in ("meta", "net_colors", "netclass_assignments"): ns.setdefault(k, ns_new[k])
ds_new={
  "defaults":{"board_outline_line_width":0.1,"copper_line_width":0.2,"silk_line_width":0.12,"silk_text_size_h":0.6,"silk_text_size_v":0.6,"silk_text_thickness":0.1},
  "rules":{"min_clearance":0.1,"min_track_width":0.1,"min_via_diameter":0.45,"min_via_annular_width":0.1,
           "min_through_hole_diameter":0.2,"min_hole_clearance":0.2,"min_hole_to_hole":0.25,
           "min_copper_edge_clearance":0.25,"min_silk_clearance":0.0,"min_text_height":0.6,"min_text_thickness":0.08,
           "min_microvia_diameter":0.2,"min_microvia_drill":0.1,"solder_mask_to_copper_clearance":0.0,"use_height_for_length_calcs":True,
           "min_resolved_spokes":1,"max_error":0.005},
  "track_widths":[0.0,0.15,0.2,0.35,0.4,0.6,0.8,1.2],
  "via_dimensions":[{"diameter":0.0,"drill":0.0},{"diameter":0.5,"drill":0.3},{"diameter":0.6,"drill":0.3}],
  "diff_pair_dimensions":[],
  "rule_severities":{"silk_overlap":"ignore","silk_over_copper":"ignore","silk_edge_clearance":"ignore","text_height":"ignore","text_thickness":"ignore","lib_footprint_mismatch":"ignore","lib_footprint_issues":"ignore","footprint_symbol_mismatch":"warning"}}
# merge into whatever KiCad saved: only our keys change, every other setting (layer presets, ERC, plot
# options, ...) is kept, so re-running this after a KiCad GUI save gives a minimal diff
ds = d.setdefault("board", {}).setdefault("design_settings", {})
for k, v in ds_new.items():
    if isinstance(v, dict) and isinstance(ds.get(k), dict): ds[k].update(v)
    else: ds[k] = v
d.setdefault("boards", [])
json.dump(d,open(p,"w"),indent=2,sort_keys=True)   # KiCad saves keys sorted: keeps diffs minimal
open(p, "a").write(chr(10))   # KiCad ends the file with a newline
