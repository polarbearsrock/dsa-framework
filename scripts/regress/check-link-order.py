#!/usr/bin/env python3
"""Detect cycles in the link partial order that dsagen2's topologicalSortLink builds
(same source with higher SourceIndex => later; same sink with higher SinkIndex => later)."""
import json, sys, collections
a = json.load(open(sys.argv[1])); E = a['DSAGenEdges']
key = lambda e: (e['SourceNodeType'], e['SourceNodeId'], e['SourceIndex'], e['SinkNodeType'], e['SinkNodeId'], e['SinkIndex'])
succ = collections.defaultdict(set)
for i, l in enumerate(E):
    for j, c in enumerate(E):
        if i == j: continue
        src = c['SourceNodeType'] == l['SourceNodeType'] and c['SourceNodeId'] == l['SourceNodeId'] and c['SourceIndex'] > l['SourceIndex']
        snk = c['SinkNodeType'] == l['SinkNodeType'] and c['SinkNodeId'] == l['SinkNodeId'] and c['SinkIndex'] > l['SinkIndex']
        if src or snk: succ[i].add(j)
state = {}
cyc = []
def dfs(u, path):
    state[u] = 1; path.append(u)
    for v in succ[u]:
        if state.get(v) == 1:
            cyc.append(path[path.index(v):] + [v]); return True
        if state.get(v) is None and dfs(v, path): return True
    path.pop(); state[u] = 2; return False
for i in range(len(E)):
    if state.get(i) is None and dfs(i, []): break
if cyc:
    print("CYCLE among links:"); 
    for i in cyc[0]: print("  ", key(E[i]))
    sys.exit(1)
print("link order consistent:", len(E), "edges")
