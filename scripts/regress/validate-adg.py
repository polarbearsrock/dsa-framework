#!/usr/bin/env python3
"""Compare a DSE-produced ADG against a dsagen2-printed reference ADG, per node type.
Reports keys missing in the candidate, scalar type mismatches, and array element-type/depth mismatches."""
import json, sys, collections
ref=json.load(open(sys.argv[1])); cand=json.load(open(sys.argv[2]))
def bytype(d):
    out={}
    for k,v in d['DSAGenNodes'].items(): out.setdefault(k.split('.')[0], v)
    return out
def shape(v):
    if isinstance(v, list):
        if not v: return 'list[empty]'
        return 'list[' + shape(v[0]) + ']'
    return type(v).__name__
def walk(o, prefix=''):
    res={}
    for k,v in o.items():
        if k in ('ConfigBitEncode','comment'): continue
        if isinstance(v, dict): res.update(walk(v, prefix+k+'/'))
        else: res[prefix+k]=shape(v)
    return res
R=bytype(ref); C=bytype(cand); problems=0
print('candidate nodes:', dict(collections.Counter(k.split('.')[0] for k in cand['DSAGenNodes'])), 'edges:', len(cand['DSAGenEdges']))
for t in sorted(C):
    if t not in R: print(f"  {t}: no reference node type"); continue
    r=walk(R[t]); c=walk(C[t])
    for k in sorted(set(r)-set(c)): print(f"  {t}: MISSING {k} ({r[k]})"); problems+=1
    for k in sorted(set(r)&set(c)):
        if r[k]!=c[k] and not (r[k].startswith('list[empty]') and c[k].startswith('list[')) and not (c[k].startswith('list[empty]') and r[k].startswith('list[')):
            print(f"  {t}: TYPE {k} reference={r[k]} candidate={c[k]}"); problems+=1
        elif r[k]!=c[k]:
            print(f"  {t}: note {k} reference={r[k]} candidate={c[k]} (empty vs non-empty list)")
# hardware rules beyond the schema
import collections as _c
comp=set(k for k in cand['DSAGenNodes'] if k.split('.')[0] in ('ProcessingElement','Switch','InputVectorPort','OutputVectorPort'))
adj=_c.defaultdict(set)
for e in cand['DSAGenEdges']:
    a=f"{e['SourceNodeType']}.{e['SourceNodeId']}"; b=f"{e['SinkNodeType']}.{e['SinkNodeId']}"
    if a in comp and b in comp: adj[a].add(b); adj[b].add(a)
seen=set(); ncomp=0
for n in comp:
    if n in seen: continue
    ncomp+=1; stack=[n]
    while stack:
        x=stack.pop()
        if x in seen: continue
        seen.add(x); stack.extend(adj[x]-seen)
if ncomp!=1: print(f"  RULE: compute fabric has {ncomp} disconnected components"); problems+=1
for k,v in cand['DSAGenNodes'].items():
    for key,val in v.items():
        if key.endswith('IVPNode$') or key.endswith('OVPNode$'):
            d=val['depthByte']
            if d!=-1 and (d<=0 or d&(d-1)): print(f"  RULE: {k} depthByte {d} not a power of two"); problems+=1
# datapath granularity must be uniform across compute nodes
gran=set(); leaves_per_node=_c.Counter()
for k,v in cand['DSAGenNodes'].items():
    if k.split('.')[0] in ('ProcessingElement','Switch'):
        cn=v['dsagen2.comp.config.CompKeys$CompNode$']; gran.add((cn['compBits'], cn['compUnitBits']))
if len(gran)>1: print(f"  RULE: mixed compute granularity {sorted(gran)}"); problems+=1
deg={n: len(adj[n]) for n in comp}
for n in comp:
    leaves=[m for m in adj[n] if deg[m]==1]
    if len(leaves)>2: print(f"  RULE: {n} has {len(leaves)} single-link neighbours (fan-out-2 tree impossible)"); problems+=1
types=set(k.split('.')[0] for k in cand['DSAGenNodes'])
for need in ('DirectMemoryAccess','InputVectorPort','OutputVectorPort','ProcessingElement'):
    if need not in types: print(f"  RULE: no {need} node in the ADG"); problems+=1
# rules learned from dsagen2 elaboration/simulation failures (2026-09-08/09)
indeg=collections.Counter(); outdeg=collections.Counter()
for e in cand['DSAGenEdges']:
    indeg[e['SinkNodeType']+'.'+str(e['SinkNodeId'])]+=1; outdeg[e['SourceNodeType']+'.'+str(e['SourceNodeId'])]+=1
    if e['SourceNodeType']=='RegisterEngine' and e['SinkNodeType']=='InputVectorPort':
        print(f"  RULE: register engine feeds {e['SinkNodeType']}.{e['SinkNodeId']} (REGImpl allows OVPs only)"); problems+=1
for k,v in cand['DSAGenNodes'].items():
    blocks=[vv for vv in v.values() if isinstance(vv,dict)]
    if k.startswith('ProcessingElement'):
        mc=[b for b in blocks if 'inputLSBCtrl' in b]; ops=[b for b in blocks if 'OperationDataTypeSet' in b]; ob=[b for b in blocks if 'staticOutputBuffer' in b]
        if mc and mc[0]['inputLSBCtrl'] and indeg[k]<2: print(f"  RULE: {k} is input-controlled but has {indeg[k]} input(s) (needs >= 2)"); problems+=1
        if ops and not ops[0].get('isDynamic',True): print(f"  RULE: {k} is a static PE (combinational loop with register file)"); problems+=1
        if ob and ob[0].get('staticOutputBuffer'): print(f"  RULE: {k} has a static output buffer (drops data under backpressure)"); problems+=1
        if outdeg[k]<1: print(f"  RULE: {k} has no output"); problems+=1
    if k.startswith('Switch'):
        ob=[b for b in blocks if 'staticOutputBuffer' in b]
        if ob and ob[0].get('staticOutputBuffer'): print(f"  RULE: {k} has a static output buffer (drops data under backpressure)"); problems+=1
    if k.startswith('OutputVectorPort'):
        vp=[b for b in blocks if 'vpStated' in b]
        if vp and vp[0]['vpStated'] and indeg[k]<2: print(f"  RULE: {k} is stated but has {indeg[k]} compute input(s)"); problems+=1
    if k.startswith('ScratchpadMemory'):
        m=[b for b in blocks if 'readWidth' in b]
        if m and m[0]['readWidth']<32: print(f"  RULE: {k} bus width {m[0]['readWidth']} B < 32 B corrupted results on RTL"); problems+=1
mems=[k for k in cand['DSAGenNodes'] if any(x in k for x in ('Memory','Access','Engine'))]
indirect=[k for k,v in cand['DSAGenNodes'].items() if any(isinstance(vv,dict) and vv.get('IndirectIndexStream') for vv in v.values())]
novp=sum(1 for k in cand['DSAGenNodes'] if k.startswith('OutputVectorPort'))
if indirect and novp<2: print(f"  RULE: indirect-capable memory but only {novp} OVP (needs > 1)"); problems+=1
for need in ('RegisterEngine',):
    if not any(k.startswith(need) for k in cand['DSAGenNodes']): print(f"  RULE: no {need} (ss_recv scalar read-back needs it)"); problems+=1
# vector ports must carry the seed's parameters: the DSE model's defaults (vpImpl 2 = NonXBarVP,
# no repeat/broadcast) are hardware the bitstream never configures and the ISA's repeat ports rely on
for k,v in cand['DSAGenNodes'].items():
    if k.startswith('InputVectorPort') or k.startswith('OutputVectorPort'):
        vp=list(v.values())[0]
        if vp.get('vpImpl')!=0: print(f"  RULE: {k} vpImpl {vp.get('vpImpl')} (0 = FullXBarVP expected; 2 = NonXBarVP hangs)"); problems+=1
        if k.startswith('InputVectorPort') and not (vp.get('repeatedIVP') and vp.get('broadcastIVP')):
            print(f"  RULE: {k} repeatedIVP={vp.get('repeatedIVP')} broadcastIVP={vp.get('broadcastIVP')} (compiler needs repeat ports)"); problems+=1
# memory bus widths must stay at the seed's 32 B: 8 B (SPM) corrupted all kernels, 64 B (DMA) corrupted solver/matadd-style streams on RTL
for k,v in cand['DSAGenNodes'].items():
    if k.startswith('DirectMemoryAccess') or k.startswith('ScratchpadMemory'):
        m=list(v.values())[0]
        for f in ('readWidth','writeWidth'):
            if m.get(f)!=32: print(f"  RULE: {k} {f} {m.get(f)} != 32 (DSE bus-width changes corrupt data on RTL)"); problems+=1
print('schema/rule problems:', problems)
sys.exit(1 if problems else 0)
