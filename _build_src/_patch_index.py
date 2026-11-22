p = 'webapp/static/index.html'; s = open(p, encoding='utf-8').read()
a0 = s.index('          <div class="card">\n            <div class="cardh">Roads</div>')
a1 = s.index('        <div id="existingInputs">')
new = '''          <div class="card">
            <div class="cardh">Existing roads to keep <span class="mini">(optional; default: OpenStreetMap)</span></div>
            <div class="row"><span class="mini">Width</span><select id="exW"><option>30</option><option selected>40</option><option>60</option><option>80</option><option>100</option></select>
              <button class="draw" data-kind="existing" data-shape="polyline">Draw</button><label class="file">Upload<input type="file" data-kind="existing"></label></div>
          </div>
          <div class="card">
            <div class="cardh">Stream / drainage <span class="mini">(optional)</span></div>
            <div class="row"><button class="draw" data-kind="stream" data-shape="polyline">Draw stream</button><button class="draw" data-kind="stream" data-shape="polygon">Draw reserve</button><label class="file">Upload<input type="file" data-kind="stream"></label></div>
            <div class="row"><span class="mini">Buffer each side</span><input id="streamBuf" type="number" value="100" min="0" step="10" style="width:80px"><span class="mini">ft</span></div>
          </div>
          <div class="card">
            <div class="cardh">Roads <span id="roadsState" class="mini"></span></div>
            <div class="mini">Road width (ft)</div>
            <div class="chips" id="widthChips"></div>
            <div class="mini" style="margin-top:8px">Tools</div>
            <div class="tools" id="tools">
              <button data-tool="draw">Draw</button><button data-tool="extend">Extend</button><button data-tool="trim">Trim</button><button data-tool="split">Split</button>
              <button data-tool="offset">Offset</button><button data-tool="width">Set width</button><button data-tool="delete">Delete</button><button data-tool="snap" class="ghost">Snap ends</button>
            </div>
            <div class="row" id="offRow" hidden><span class="mini">Offset distance</span><input id="offDist" type="number" value="230" min="10" step="10" style="width:80px"><span class="mini">ft between centrelines (230 = 200 ft block + 30 ft road)</span></div>
            <p class="hint" id="toolHint">Choose a tool. Esc stops it. Road ends snap onto roads within 12 m.</p>
            <div class="row"><label class="tl"><input type="checkbox" id="showAngles" checked> Show junction angles</label><span class="mini" id="angleSum"></span></div>
            <div class="row"><label class="file">Upload roads<input type="file" data-kind="roads"></label></div>

            <div class="sub">
              <div class="cardh">Design the roads for me</div>
              <div class="grid2">
                <span class="mini">Pattern</span><select id="dPattern"><option value="mixed">Blended (best pattern per parcel)</option><option value="grid">Grid iron</option><option value="curvilinear">Curvilinear (follows the contours)</option><option value="ringband">Ring and band (perimeter loop + inner grid)</option></select>
                <span class="mini">Block depth</span><select id="dBand"><option value="200">200 ft (2 x 100 ft plots)</option><option value="240">240 ft (2 x 120 ft plots)</option></select>
                <span class="mini">Block length</span><select id="dLen"><option value="420">420 ft (6 x 70)</option><option value="490" selected>490 ft (7 x 70)</option><option value="560">560 ft (8 x 70)</option></select>
                <span class="mini">Local roads</span><select id="dLocal"><option>24</option><option selected>30</option><option>40</option></select>
                <span class="mini">Collectors</span><select id="dColl"><option selected>40</option><option>50</option><option>60</option></select>
                <span class="mini">Parcels up to</span><select id="dParcel"><option value="25">25 ac</option><option value="35" selected>35 ac</option><option value="50">50 ac</option></select>
              </div>
              <div class="row"><button id="designBtn">Design the roads for me</button></div>
              <p class="hint">Replaces the current roads with a new design (existing roads and stream / steep reserves are kept). The result loads here for editing.</p>
            </div>
            <div class="sub">
              <div class="cardh">Suggest a redesign</div>
              <p class="hint">Draw the area to redesign, choose how, then Redesign. Roads outside the area and roads you drew or edited yourself are kept; the rest of the area is laid out again and joined to the kept roads. Pattern and block settings come from "Design the roads for me" above.</p>
              <div class="row"><button class="draw" data-kind="zones" data-shape="polygon">Draw redesign area</button><button id="clearZones" class="ghost">Clear areas</button><button id="redesignBtn">Redesign</button></div>
            </div>
          </div>
        </div>
'''
s = s[:a0] + new + s[a1:]
# remove the old existing / stream cards (now placed above) - they followed the old roads card and are gone with the slice
s = s.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>',
              '<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/Turf.js/6.5.0/turf.min.js"></script>')
open(p, 'w', encoding='utf-8').write(s); print('index ok', s.count('Existing roads to keep'), s.count('Stream / drainage'))
c = 'webapp/static/app.css'; t = open(c, encoding='utf-8').read()
t = t.replace('@media (max-width: 800px)', '''.chips, .tools { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.chips button { padding: 3px 9px; background: #fff; color: var(--ink); border-color: var(--line); }
.chips button.on { background: var(--accent); color: #fff; border-color: var(--accent); }
.chips input { width: 64px; padding: 3px 6px; }
.tools button { padding: 4px 10px; background: #fff; color: var(--accent); }
.tools button.on { background: #f5a142; border-color: #f5a142; color: #fff; }
.sub { border-top: 1px dashed var(--line); margin-top: 10px; padding-top: 8px; }
.grid2 { display: grid; grid-template-columns: 90px 1fr; gap: 4px 8px; align-items: center; }
.grid2 select { width: 100%; }
.ang { font: 600 11px/1 "Segoe UI", sans-serif; padding: 2px 4px; border-radius: 4px; color: #fff; white-space: nowrap; box-shadow: 0 0 0 1px rgba(0,0,0,.35); }
.ang.g { background: #2e7d32; } .ang.o { background: #ef6c00; } .ang.r { background: #c62828; }
@media (max-width: 800px)''')
open(c, 'w', encoding='utf-8').write(t); print('css ok')
