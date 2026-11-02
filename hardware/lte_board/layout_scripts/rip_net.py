"""Delete a net's unlocked tracks and vias (locked hand routes stay), e.g. before re-routing it with maze_route.py --wide.
usage: rip_net.py board.kicad_pcb NET [NET ...]"""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
tl = list(b.GetTracks())          # one snapshot: GetTracks() can break after Remove() under SWIG
for net in sys.argv[2:]:
    mine = [t for t in tl if t.GetNetname() == net]
    gone = [t for t in mine if not t.IsLocked()]
    for t in gone: b.Remove(t)
    print(net, "removed", len(gone), "kept (locked)", len(mine) - len(gone))
pcbnew.SaveBoard(sys.argv[1], b)
