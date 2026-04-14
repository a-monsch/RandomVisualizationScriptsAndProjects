import os
import json
import shutil
from itertools import combinations
from tqdm import tqdm
import argparse

argument_parser = argparse.ArgumentParser(description="Generate GoF comparison dashboard")
argument_parser.add_argument("--reference-dir", "--classic-dir", dest="reference_dir", type=str, required=True)
argument_parser.add_argument("--new-dir", "--ml-dir", dest="new_dir", type=str)
argument_parser.add_argument("--title", type=str, default=None)
arguments = argument_parser.parse_args()

variables_1d = (
    # ---
    "pt_1",
    "pt_2",
    "jpt_1",
    "jpt_2",
    "pt_vis",
    "pt_dijet",
    "mjj",
    "m_vis",
    "nbtag",
    "njets",
    "m_fastmtt",
    "deltaR_ditaupair",
    "deltaEta_jj",
    "eta_1",
    "eta_2",
    # ---
    "deltaEta_ditaupair",
    "deltaR_jj",
    "jeta_1",
    "jeta_2",
    "pt_ttjj",
    "mt_tot",
    "pt_tt",
    "mt_2",
    "mt_1",
    "met",
    "pzetamissvis",
    "pt_fastmtt",
    # ---
    "deltaR_1j1",
    "deltaR_1j2",
    "deltaR_2j1",
    "deltaR_2j2",
    "deltaR_12j1",
    "deltaR_12j2",
    # ---
    "deltaEta_1j1",
    "deltaEta_1j2",
    "deltaEta_2j1",
    "deltaEta_2j2",
    "deltaEta_12j1",
    "deltaEta_12j2",
    # ---
    "eta_fastmtt",
)


class ParityTuple(tuple):
    def __eq__(self, other):
        if isinstance(other, (ParityTuple, tuple)) and len(self) == 2 and len(other) == 2:
            return (self[0] == other[0] and self[1] == other[1]) or (self[0] == other[1] and self[1] == other[0])
        if isinstance(other, (ParityTuple, tuple)) and len(self) == 1 and len(other) == 1:
            return self[0] == other[0]
        if isinstance(other, str) and len(self) == 2:
            return f"{self[0]}_{self[1]}" == other or f"{self[1]}_{self[0]}" == other
        if isinstance(other, str) and len(self) == 1:
            return self[0] == other
        return super().__eq__(other)

    def __hash__(self):
        if len(self) == 2:
            return hash(frozenset(self))
        if len(self) == 1:
            return hash(self[0])
        return super().__hash__()


class ParityTupleCompatibleDict(dict):
    def __getitem__(self, key):
        if isinstance(key, str):
            for k in self.keys():
                if key == k:
                    return super().__getitem__(k)
        if isinstance(key, (tuple, list)):
            for k in self.keys():
                if tuple(key) == k:
                    return super().__getitem__(k)
        return super().__getitem__(key)


gof_variables = [ParityTuple([it]) for it in variables_1d]
gof_variables += [ParityTuple(it) for it in combinations(variables_1d, 2)]


def get_gofs(path, skip_variables=None):
    prefix = "2018_mt_"
    gofs = ParityTupleCompatibleDict()
    for variable in tqdm([it.replace(prefix, "") for it in os.listdir(path) if it.startswith(prefix)]):
        with open(os.path.join(path, f"{prefix}{variable}", "gof.json"), "r") as f:
            if skip_variables is not None and any(skip in variable for skip in skip_variables):
                continue
            for gof_variable in gof_variables:
                if gof_variable == variable:
                    gofs[gof_variable] = json.load(f)["125.0"]["p"]
                    break
    return gofs


REF_DIR = (arguments.reference_dir, "./gofs/reference")
NEW_DIR = (arguments.new_dir, "./gofs/new")
HAS_NEW = NEW_DIR[0] is not None
if arguments.title is not None:
    TITLE = arguments.title
else:
    TITLE = "Reference vs. New - 2D GoF Comparison" if HAS_NEW else "2D- GoF"

gofs_reference = get_gofs(REF_DIR[0])
gofs_new = get_gofs(NEW_DIR[0]) if HAS_NEW else ParityTupleCompatibleDict()


def copy_plot_files(src_base, target_base, folder_name):
    src_dir = os.path.join(src_base, folder_name)
    tgt_dir = os.path.join(target_base, folder_name)
    if not os.path.exists(src_dir):
        return
    os.makedirs(os.path.join(tgt_dir, "plots"), exist_ok=True)
    files_to_copy = [
        "gof.png",
        "gof.pdf",
        f"plots/{folder_name}_prefit.png",
        f"plots/{folder_name}_prefit.pdf",
        f"plots/{folder_name}_postfit.png",
        f"plots/{folder_name}_postfit.pdf",
    ]
    for f in files_to_copy:
        src_file, tgt_file = os.path.join(src_dir, f), os.path.join(tgt_dir, f)
        if os.path.exists(src_file) and not os.path.exists(tgt_file):
            shutil.copy2(src_file, tgt_file)


plot_data, prefix = [], "2018_mt_"
print("Resolving paths and copying images to web space...")
for key, val_reference in tqdm(gofs_reference.items()):
    components = list(key) if isinstance(key, tuple) else [str(key)]
    val_new = gofs_new.get(key, None)
    ref_folder, new_folder, display_name = None, None, "_".join(components)

    if len(components) == 2:
        str1 = f"{prefix}{components[0]}_{components[1]}"
        str2 = f"{prefix}{components[1]}_{components[0]}"
        ref_folder = str1 if os.path.exists(os.path.join(REF_DIR[0], str1)) else str2
        if HAS_NEW and val_new is not None:
            new_folder = str1 if os.path.exists(os.path.join(NEW_DIR[0], str1)) else str2
    else:
        ref_folder = f"{prefix}{components[0]}"
        if HAS_NEW and val_new is not None:
            new_folder = f"{prefix}{components[0]}"

    copy_plot_files(REF_DIR[0], REF_DIR[1], ref_folder)
    if HAS_NEW and val_new is not None and new_folder is not None:
        copy_plot_files(NEW_DIR[0], NEW_DIR[1], new_folder)

    plot_data.append({"var_name": display_name, "components": components, "reference": val_reference, "new": val_new, "ref_folder": ref_folder, "new_folder": new_folder})

json_data = json.dumps(plot_data)
variables_js = json.dumps(variables_1d)

html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{TITLE}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 10px; background-color: #f9f9f9; height: 100vh; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden; }}
        h2 {{ margin: 0 0 10px 0; text-align: center; color: #333; font-size: 20px; flex: 0 0 auto; }}

        /* Unified Panels */
        .panel {{ background: white; padding: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; min-width: 0; min-height: 0; }}

        #box-matrix {{ justify-content: center; align-items: center; }}
        #matrix-container {{ width: 100%; height: 100%; }}
        #plot-container {{ flex: 1; width: 100%; height: 100%; }}

        /* Controls */
        #box-controls {{ width: 260px; flex: 0 0 auto; }}
        select, input[type="text"] {{ width: 100%; padding: 5px; margin-bottom: 10px; font-size: 13px; box-sizing: border-box; }}
        .filter-list {{ flex: 1; overflow-y: auto; border: 1px solid #ccc; border-radius: 4px; padding: 2px; margin-bottom: 10px; }}
        .filter-item {{ padding: 6px 10px; margin: 2px; border-radius: 4px; cursor: pointer; user-select: none; font-size: 13px; transition: background 0.1s; }}
        .state-0 {{ background: #fff; color: #333; }}
        .state-0:hover {{ background: #eee; }}
        .state-1 {{ background: #d4edda; color: #155724; font-weight: bold; border-left: 4px solid #28a745; }}
        .state--1 {{ background: #f8d7da; color: #721c24; text-decoration: line-through; border-left: 4px solid #dc3545; }}

        .btn-link {{ background-color: #007bff; color: white; padding: 8px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px; text-align: center; transition: background 0.2s; }}
        .btn-link:hover {{ background-color: #0056b3; }}
        .toast {{ text-align: center; font-size: 11px; color: #28a745; margin-top: 5px; opacity: 0; transition: opacity 0.3s; font-weight: bold; }}

        /* Dynamic Layout Wrappers */
        #app-container {{ display: flex; flex: 1; min-height: 0; gap: 10px; }}
        .layout-row {{ display: flex; flex-direction: row; gap: 10px; width: 100%; min-height: 0; min-width: 0; }}
        .layout-col {{ display: flex; flex-direction: column; gap: 10px; height: 100%; min-height: 0; min-width: 0; }}

        /* Drag Handles */
        .resizer-hz {{ height: 12px; cursor: row-resize; display: flex; justify-content: center; align-items: center; background: transparent; flex: 0 0 auto; }}
        .resizer-hz:hover {{ background-color: #e0e0e0; }}
        .resizer-hz-line {{ width: 60px; height: 4px; background-color: #bbb; border-radius: 2px; }}

        .resizer-vt {{ width: 12px; cursor: col-resize; display: flex; justify-content: center; align-items: center; background: transparent; flex: 0 0 auto; }}
        .resizer-vt:hover {{ background-color: #e0e0e0; }}
        .resizer-vt-line {{ width: 4px; height: 60px; background-color: #bbb; border-radius: 2px; }}

        /* Smart Images Panel */
        #var-title {{ text-align: center; color: #d32f2f; margin: 0 0 5px 0; font-size: 16px; flex: 0 0 auto; }}
        .img-grid {{ display: flex; flex: 1 1 auto; min-height: 0; gap: 10px; width: 100%; }}
        .img-row {{ display: flex; flex: 1 1 auto; align-items: center; min-height: 0; min-width: 0; background: #fdfdfd; border-radius: 6px; }}
        .row-label {{ font-weight: bold; font-size: 14px; text-align: center; color: #333; flex: 0 0 auto; display: flex; justify-content: center; align-items: center; }}
        .img-col {{ flex: 1 1 auto; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 0; min-width: 0; height: 100%; padding: 5px; }}
        .img-title {{ font-size: 12px; font-weight: bold; color: #666; margin-bottom: 2px; flex: 0 0 auto; }}
        .img-col img {{ flex: 1 1 auto; min-height: 0; min-width: 0; max-width: 100%; max-height: 100%; object-fit: contain; display: none; }}

        /* Auto-Layout States for Images */
        .img-grid.layout-hz {{ flex-direction: column; }}
        .img-grid.layout-hz .img-row {{ flex-direction: row; height: 50%; border-bottom: 1px solid #eee; }}
        .img-grid.layout-hz .img-row:last-child {{ border-bottom: none; }}
        .img-grid.layout-hz .row-label {{ width: 100px; height: 100%; }}

        .img-grid.layout-vt {{ flex-direction: row; }}
        .img-grid.layout-vt .img-row {{ flex-direction: column; width: 50%; height: 100%; border-right: 1px solid #eee; }}
        .img-grid.layout-vt .img-row:last-child {{ border-right: none; }}
        .img-grid.layout-vt .row-label {{ height: auto; width: 100%; padding: 5px 0; border-bottom: 1px solid #ddd; }}

        .img-col img, .img-title, .row-label {{ cursor: zoom-in; }}

        .img-modal-overlay {{
            position: fixed;
            inset: 0;
            background: rgba(25, 25, 25, 0.75);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            padding: 16px;
            box-sizing: border-box;
        }}
        .img-modal-overlay.open {{ display: flex; }}
        .img-modal-content {{
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-width: 95vw;
            max-height: 95vh;
            min-width: 280px;
        }}
        .img-modal-title {{
            margin: 0;
            font-size: 16px;
            color: #222;
            text-align: center;
        }}
        .img-modal-single {{
            max-width: 92vw;
            max-height: 84vh;
            object-fit: contain;
        }}
        .img-modal-pair {{
            display: flex;
            gap: 12px;
            align-items: stretch;
            justify-content: center;
        }}
        .img-modal-panel {{
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 0;
        }}
        .img-modal-panel-title {{
            font-size: 13px;
            font-weight: bold;
            color: #444;
            margin-bottom: 6px;
        }}
        .img-modal-panel img {{
            max-width: 44vw;
            max-height: 78vh;
            object-fit: contain;
        }}
        .img-modal-note {{
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }}
        .img-modal-link {{
            margin-top: 6px;
            font-size: 12px;
            color: #0b2f73;
            text-decoration: none;
            border: 1px solid #0b2f73;
            border-radius: 4px;
            padding: 3px 8px;
            display: inline-block;
        }}
        .img-modal-link:hover {{ background: #0b2f73; color: #fff; }}
        .img-modal-triplet {{
            display: flex;
            gap: 12px;
            align-items: stretch;
            justify-content: center;
        }}

        @media (max-width: 900px) {{
            .img-modal-pair {{ flex-direction: column; }}
            .img-modal-triplet {{ flex-direction: column; }}
            .img-modal-panel img {{ max-width: 90vw; max-height: 38vh; }}
        }}

        .help-trigger {{
            position: fixed;
            top: 8px;
            right: 14px;
            color: #2b4a7c;
            background: transparent;
            border: none;
            font-weight: bold;
            font-size: 28px;
            line-height: 1;
            text-align: center;
            cursor: help;
            user-select: none;
            z-index: 10000;
        }}
        .help-trigger:hover, .help-trigger:focus {{
            color: #173156;
            outline: none;
            text-decoration: underline;
        }}

        .help-overlay {{
            position: fixed;
            inset: 0;
            background: rgba(15, 25, 40, 0.42);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9998;
            padding: 20px;
            box-sizing: border-box;
        }}
        .help-overlay.open {{ display: flex; }}
        .help-card {{
            width: min(880px, 92vw);
            max-height: 88vh;
            overflow-y: auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 14px 44px rgba(0, 0, 0, 0.28);
            border: 1px solid #d9e1ee;
            padding: 18px 20px;
        }}
        .help-card h3 {{
            margin: 0 0 10px 0;
            color: #173156;
            font-size: 18px;
            text-align: center;
        }}
        .help-card h4 {{
            margin: 12px 0 5px 0;
            color: #27487a;
            font-size: 14px;
        }}
        .help-card ul {{
            margin: 0;
            padding-left: 18px;
            color: #253244;
            font-size: 13px;
            line-height: 1.4;
        }}
        .help-card li {{ margin: 2px 0; }}
        .help-note {{
            margin-top: 10px;
            color: #4a607f;
            font-size: 12px;
            text-align: center;
        }}

        .no-select {{ user-select: none; }}
    </style>
</head>
<body>

    <h2>{TITLE}</h2>

    <div id="help-trigger" class="help-trigger" tabindex="0" aria-label="Show dashboard help">?</div>

    <div id="help-overlay" class="help-overlay">
        <div id="help-card" class="help-card">
            <h3>Dashboard User Guide</h3>

            <h4>1. Variable Exploration</h4>
            <ul>
                <li>Hover over a scatter point or matrix cell to view the corresponding pre-fit, post-fit, and Goodness of Fit (GoF) images.</li>
                <li>Click on a point or cell to lock the current selection. Click it again to unlock.</li>
                <li>The text below the image panel indicates the current lock status.</li>
            </ul>

            <h4>2. Filtering and Sorting</h4>
            <ul>
                <li><strong>Sort / Color By:</strong> Determines whether the scatter plot ranking and matrix coloring are based on the Reference or New GoF values.</li>
                <li><strong>Performance Filter:</strong> Restricts the view to show all results, only improvements, or only regressions.</li>
                <li><strong>Variable Search:</strong> Supports direct names and parity-equivalent pairs (e.g., searching for <code>A_B</code> will also match <code>B_A</code>).</li>
                <li><strong>Variable Filter:</strong> Click variables to cycle their state between neutral, include (green), and exclude (red).</li>
            </ul>

            <h4>3. Alpha Filter</h4>
            <ul>
                <li>Enter the desired range as two comma-separated numeric bounds (e.g., <code>0.0,1.0</code>).</li>
                <li>Bounds are inclusive. A point is displayed only if its value falls within the range <code>[min, max]</code>.</li>
                <li>If the bounds are entered in reverse order (e.g., <code>0.8,0.2</code>), they are automatically reordered.</li>
                <li>Invalid or non-numeric formats will default to the standard <code>0.0,1.0</code> interval.</li>
                <li>In comparison mode, both Reference and New filters are applied simultaneously. In Reference-only mode, the New filter is hidden.</li>
            </ul>

            <h4>4. Image Inspection</h4>
            <ul>
                <li>Click any image to open an enlarged modal view containing a PDF download link.</li>
                <li>Click a column title (Pre-fit, Post-fit, GoF) to view a side-by-side comparison of the Reference and New plots.</li>
                <li>Click a row label (Reference or New) to view all three plots for that dataset simultaneously.</li>
                <li>Press the <code>Escape</code> key or click outside the image to close the modal.</li>
            </ul>

            <h4>5. Layout and View Controls</h4>
            <ul>
                <li>Drag the separators between panels to adjust their sizes.</li>
                <li>Double-click the matrix, scatter plot, or image panel to maximize it. Double-click again to restore the original layout.</li>
                <li>Plots will automatically resize to fit the available space.</li>
            </ul>

            <h4>6. State Sharing</h4>
            <ul>
                <li><strong>Copy Permalink:</strong> Generates a URL containing your current sorting, filtering, searching, and selection states, allowing you to easily share or revisit your view.</li>
            </ul>

            <div class="help-note">Note: This help panel closes automatically when your cursor leaves the area.</div>
        </div>
    </div>

    <!-- DOM Storage: These boxes get moved around by JS into the App Container -->
    <div id="dom-storage" style="display:none;">
        <div id="box-matrix" class="panel"><div id="matrix-container"></div></div>
        <div id="box-scatter" class="panel"><div id="plot-container"></div></div>

        <div id="box-controls" class="panel">
            <label style="font-weight:bold; font-size: 14px;">Sort / Color By:</label>
            <select id="sort-select" onchange="updatePlot()"><option value="reference">Reference GoF</option><option value="new">New GoF</option></select>

            <label style="font-weight:bold; font-size: 14px; margin-top:5px;">Performance Filter:</label>
            <select id="comparison-select" onchange="updatePlot()">
                <option value="all">All</option>
                <option value="improvement">Improvement</option>
                <option value="regression">Regression</option>
            </select>

            <label style="font-weight:bold; font-size: 14px; margin-top:5px;">Variable Search:</label>
            <input id="var-search" type="text" placeholder="Type variable, e.g. eta_1_eta_2" oninput="updatePlot()">

            <label id="alpha-classic-label" style="font-weight:bold; font-size: 14px; margin-top:5px;">Alpha Filter (Reference):</label>
            <div style="display:flex; gap:6px; align-items:center; margin-bottom:10px;">
                <input id="alpha-classic" type="text" value="0.0,1.0" placeholder="min,max" oninput="updatePlot()" style="margin-bottom:0; flex:1;">
                <button class="btn-link" style="padding:6px 10px; margin:0;" onclick="resetAlphaFilters('reference')">Reset</button>
            </div>

            <label id="alpha-ml-label" style="font-weight:bold; font-size: 14px; margin-top:5px;">Alpha Filter (New):</label>
            <div id="alpha-ml-row" style="display:flex; gap:6px; align-items:center; margin-bottom:10px;">
                <input id="alpha-ml" type="text" value="0.0,1.0" placeholder="min,max" oninput="updatePlot()" style="margin-bottom:0; flex:1;">
                <button class="btn-link" style="padding:6px 10px; margin:0;" onclick="resetAlphaFilters('new')">Reset</button>
            </div>

            <label style="font-weight:bold; font-size: 14px; margin-top:5px;">Variable Filter:</label>
            <div style="font-size: 11px; color: #677; margin-bottom: 5px; text-align: center;">Click: <span style="color:#28a745;">Include</span> / <span style="color:#dc3545; text-decoration:line-through;">Exclude</span></div>
            <div class="filter-list" id="filter-list"></div>
            <button class="btn-link" style="padding:6px; margin-bottom:10px;" onclick="resetVariableStateFilters()">Reset Variable Filter</button>

            <button class="btn-link" onclick="copyPermalink()">&#128279; Copy Permalink</button>
            <div class="toast" id="copy-toast">Link Copied!</div>
        </div>

        <div id="box-images" class="panel">
            <h3 id="var-title">Hover over a point to view plots</h3>
            <div class="img-grid layout-hz" id="img-grid">
                <div class="img-row" id="row-classic">
                    <div class="row-label" id="lbl-classic" style="border-left: 4px solid #3366cc; border-top: none;">Reference</div>
                    <div class="img-col"><div class="img-title">Pre-fit</div><img id="classic_prefit" src="" onerror="this.style.display='none'"></div>
                    <div class="img-col"><div class="img-title">Post-fit</div><img id="classic_postfit" src="" onerror="this.style.display='none'"></div>
                    <div class="img-col"><div class="img-title">GoF</div><img id="classic_gof" src="" onerror="this.style.display='none'"></div>
                </div>
                <div class="img-row" id="row-ml">
                    <div class="row-label" id="lbl-ml" style="border-left: 4px solid #ff9900; border-top: none;">New</div>
                    <div class="img-col"><div class="img-title">Pre-fit</div><img id="ml_prefit" src="" onerror="this.style.display='none'"></div>
                    <div class="img-col"><div class="img-title">Post-fit</div><img id="ml_postfit" src="" onerror="this.style.display='none'"></div>
                    <div class="img-col"><div class="img-title">GoF</div><img id="ml_gof" src="" onerror="this.style.display='none'"></div>
                </div>
            </div>
            <div id="lock-hint" style="font-size:11px; color:#335; text-align:center; margin-top:6px; min-height:14px;"></div>
        </div>
    </div>

    <!-- The Active Canvas -->
    <div id="app-container"></div>

    <div id="img-modal" class="img-modal-overlay" onclick="onModalOverlayClick(event)">
        <div id="img-modal-content" class="img-modal-content"></div>
    </div>

    <script>
        const rawData = {json_data};
        const variablesList = {variables_js};
        const REFERENCE_BASE = "{REF_DIR[1]}";
        const NEW_BASE = "{NEW_DIR[1]}";
        const HAS_NEW = {str(HAS_NEW).lower()};
        let currentHoverVar = null;
        let lockedVar = null;
        let activeComparisonKind = 'prefit';
        const comparisonKinds = ['prefit', 'postfit', 'gof'];
        const comparisonLabels = {{ prefit: 'Pre-fit', postfit: 'Post-fit', gof: 'GoF' }};

        // --- DOM Elements ---
        const bMatrix = document.getElementById('box-matrix');
        const bScatter = document.getElementById('box-scatter');
        const bControls = document.getElementById('box-controls');
        const bImages = document.getElementById('box-images');
        const appContainer = document.getElementById('app-container');
        const helpTrigger = document.getElementById('help-trigger');
        const helpOverlay = document.getElementById('help-overlay');
        const helpCard = document.getElementById('help-card');
        let expandedPanelId = null;

        function showHelpOverlay() {{
            if (!helpOverlay) return;
            helpOverlay.classList.add('open');
        }}

        function hideHelpOverlay() {{
            if (!helpOverlay) return;
            helpOverlay.classList.remove('open');
        }}

        function bindImmediatePanelHide() {{
            if (!helpCard) return;
            helpCard.addEventListener('mouseleave', hideHelpOverlay);
        }}

        function bindHelpOverlayHandlers() {{
            if (!helpTrigger || !helpOverlay || !helpCard) return;

            helpTrigger.addEventListener('mouseenter', showHelpOverlay);
            helpTrigger.addEventListener('focus', showHelpOverlay);
            helpTrigger.addEventListener('blur', hideHelpOverlay);
            helpTrigger.addEventListener('click', showHelpOverlay);

            helpOverlay.addEventListener('mouseenter', showHelpOverlay);
            helpOverlay.addEventListener('click', event => {{
                if (event.target === helpOverlay) hideHelpOverlay();
            }});

            document.addEventListener('keydown', event => {{
                if (event.key === 'Escape') hideHelpOverlay();
            }});
        }}

        // --- GLOBAL DRAG STATE ---
        let dragState = null;
        document.addEventListener('mousemove', e => {{
            if (!dragState) return;
            if (dragState.type === 'hz') {{
                let newHeight = e.clientY - dragState.target.getBoundingClientRect().top;
                if (newHeight < 200) newHeight = 200;
                dragState.target.style.flex = 'none';
                dragState.target.style.height = newHeight + 'px';
            }} else if (dragState.type === 'vt') {{
                let newWidth = e.clientX - dragState.target.getBoundingClientRect().left;
                if (newWidth < 200) newWidth = 200;
                dragState.target.style.flex = 'none';
                dragState.target.style.width = newWidth + 'px';
            }}
            Plotly.Plots.resize(document.getElementById('plot-container'));
            Plotly.Plots.resize(document.getElementById('matrix-container'));
        }});
        document.addEventListener('mouseup', () => {{
            if (dragState) {{ dragState = null; document.body.classList.remove('no-select'); }}
        }});

        function createResizer(type, targetEl, id = null) {{
            const r = document.createElement('div');
            if (id) r.id = id;
            r.className = type === 'hz' ? 'resizer-hz' : 'resizer-vt';
            r.innerHTML = `<div class="${{r.className}}-line"></div>`;
            r.onmousedown = (e) => {{
                dragState = {{ type, target: targetEl }};
                document.body.classList.add('no-select'); e.stopPropagation();
            }};
            return r;
        }}

        // --- DYNAMIC LAYOUT BUILDER ---
        function changeLayout() {{
            appContainer.innerHTML = '';
            // Reset flex properties assigned by dragging
            [bMatrix, bScatter, bImages, bControls].forEach(b => b.style = '');

            // C: [Images] left, [Scatter / Matrix] mid, [Controls] right
            appContainer.style.flexDirection = 'row';
            bImages.style.flex = '0 0 40vw';

            const colMid = document.createElement('div'); colMid.className = 'layout-col'; colMid.id = 'col-mid'; colMid.style.flex = '1';
            bScatter.style.flex = '0 0 45vh'; bMatrix.style.flex = '1';
            colMid.appendChild(bScatter); colMid.appendChild(createResizer('hz', bScatter, 'resizer-mid-hz')); colMid.appendChild(bMatrix);

            appContainer.appendChild(bImages); appContainer.appendChild(createResizer('vt', bImages, 'resizer-main-vt')); appContainer.appendChild(colMid); appContainer.appendChild(bControls);

            if (expandedPanelId !== null) applyPanelExpansion();

            // Timeout ensures DOM is attached before Plotly computes boundaries
            setTimeout(() => {{
                updatePlot();
                Plotly.Plots.resize(document.getElementById('plot-container'));
                Plotly.Plots.resize(document.getElementById('matrix-container'));
            }}, 50);
        }}

        function togglePanelExpansion(panelId) {{
            if (expandedPanelId === panelId) {{
                expandedPanelId = null;
                changeLayout();
                return;
            }}
            expandedPanelId = panelId;
            applyPanelExpansion();
            setTimeout(() => {{
                Plotly.Plots.resize(document.getElementById('plot-container'));
                Plotly.Plots.resize(document.getElementById('matrix-container'));
            }}, 20);
        }}

        function applyPanelExpansion() {{
            const colMid = document.getElementById('col-mid');
            const resizerMain = document.getElementById('resizer-main-vt');
            const resizerMid = document.getElementById('resizer-mid-hz');
            if (!colMid) return;

            [bImages, bScatter, bMatrix, colMid, resizerMain, resizerMid].forEach(el => {{
                if (el) el.style.display = '';
            }});

            if (expandedPanelId === 'box-images') {{
                bImages.style.flex = '1';
                colMid.style.display = 'none';
                if (resizerMain) resizerMain.style.display = 'none';
            }} else if (expandedPanelId === 'box-scatter') {{
                bImages.style.display = 'none';
                if (resizerMain) resizerMain.style.display = 'none';
                bMatrix.style.display = 'none';
                if (resizerMid) resizerMid.style.display = 'none';
                bScatter.style.flex = '1';
            }} else if (expandedPanelId === 'box-matrix') {{
                bImages.style.display = 'none';
                if (resizerMain) resizerMain.style.display = 'none';
                bScatter.style.display = 'none';
                if (resizerMid) resizerMid.style.display = 'none';
                bMatrix.style.flex = '1';
            }}
        }}

        // --- SMART IMAGE LAYOUT OBSERVER ---
        const imgGrid = document.getElementById('img-grid');
        const lblClassic = document.getElementById('lbl-classic');
        const lblMl = document.getElementById('lbl-ml');

        const resizeObserver = new ResizeObserver(entries => {{
            for (let entry of entries) {{
                const w = entry.contentRect.width; const h = entry.contentRect.height;
                if (w > h * 1.3) {{ // Wide -> Rows
                    imgGrid.classList.remove('layout-vt'); imgGrid.classList.add('layout-hz');
                    lblClassic.style.borderLeft = "4px solid #3366cc"; lblClassic.style.borderTop = "none";
                    lblMl.style.borderLeft = "4px solid #ff9900"; lblMl.style.borderTop = "none";
                }} else {{ // Tall -> Cols
                    imgGrid.classList.remove('layout-hz'); imgGrid.classList.add('layout-vt');
                    lblClassic.style.borderLeft = "none"; lblClassic.style.borderTop = "4px solid #3366cc";
                    lblMl.style.borderLeft = "none"; lblMl.style.borderTop = "4px solid #ff9900";
                }}
            }}
        }});
        resizeObserver.observe(bImages);

        // --- UI FILTER LOGIC ---
        const filterStates = {{}};
        const listContainer = document.getElementById('filter-list');
        variablesList.forEach(v => {{
            filterStates[v] = 0;
            const el = document.createElement('div');
            el.className = 'filter-item state-0'; el.id = 'flt-' + v; el.innerText = v;
            el.onclick = () => {{
                filterStates[v] = (filterStates[v] === 0) ? 1 : (filterStates[v] === 1) ? -1 : 0;
                document.getElementById('flt-' + v).className = 'filter-item state-' + filterStates[v];
                updatePlot();
            }};
            listContainer.appendChild(el);
        }});

        function configureDataModeUI() {{
            const sortSelect = document.getElementById('sort-select');
            const comparisonSelect = document.getElementById('comparison-select');
            const alphaMlLabel = document.getElementById('alpha-ml-label');
            const alphaMlInput = document.getElementById('alpha-ml');
            const alphaMlRow = document.getElementById('alpha-ml-row');
            const rowMl = document.getElementById('row-ml');
            const rowClassic = document.getElementById('row-classic');

            if (!HAS_NEW) {{
                sortSelect.value = 'reference';
                sortSelect.disabled = true;

                comparisonSelect.value = 'all';
                comparisonSelect.disabled = true;

                alphaMlLabel.style.display = 'none';
                alphaMlInput.style.display = 'none';
                alphaMlRow.style.display = 'none';

                rowMl.style.display = 'none';
                rowClassic.style.height = '100%';
                rowClassic.style.width = '100%';
            }}
        }}

        function resetAlphaFilters(target = 'all') {{
            if (target === 'all' || target === 'reference') {{
                document.getElementById('alpha-classic').value = '0.0,1.0';
            }}
            if ((target === 'all' || target === 'new') && HAS_NEW) {{
                document.getElementById('alpha-ml').value = '0.0,1.0';
            }}
            updatePlot();
        }}

        function resetVariableStateFilters() {{
            Object.keys(filterStates).forEach(v => {{
                filterStates[v] = 0;
                const el = document.getElementById('flt-' + v);
                if (el) el.className = 'filter-item state-0';
            }});
            updatePlot();
        }}

        function updateLockHint() {{
            const hint = document.getElementById('lock-hint');
            if (!hint) return;
            if (lockedVar) {{
                hint.innerText = `Locked on "${{lockedVar}}". Click the same point/cell again to unlock.`;
            }} else {{
                hint.innerText = '';
            }}
        }}

        function parseAlphaRange(text) {{
            const fallback = [0.0, 1.0];
            if (!text) return fallback;
            const parts = text.split(',').map(p => p.trim());
            if (parts.length !== 2) return fallback;

            const minVal = parseFloat(parts[0]);
            const maxVal = parseFloat(parts[1]);
            if (!Number.isFinite(minVal) || !Number.isFinite(maxVal)) return fallback;

            const lo = Math.min(minVal, maxVal);
            const hi = Math.max(minVal, maxVal);
            return [lo, hi];
        }}

        function inRange(val, range) {{
            if (val === null || val === undefined) return false;
            return val >= range[0] && val <= range[1];
        }}

        function copyPermalink() {{
            const params = new URLSearchParams();
            params.set('sort', document.getElementById('sort-select').value);
            params.set('cmp', document.getElementById('comparison-select').value);

            const searchQuery = document.getElementById('var-search').value.trim();
            if (searchQuery.length > 0) params.set('search', searchQuery);

            const alphaClassic = document.getElementById('alpha-classic').value.trim();
            if (alphaClassic.length > 0) params.set('alpha_c', alphaClassic);
            if (HAS_NEW) {{
                const alphaMl = document.getElementById('alpha-ml').value.trim();
                if (alphaMl.length > 0) params.set('alpha_m', alphaMl);
            }}

            let inc = [], exc = [];
            for (const [v, state] of Object.entries(filterStates)) {{
                if (state === 1) inc.push(v);
                if (state === -1) exc.push(v);
            }}
            if (inc.length > 0) params.set('inc', inc.join(','));
            if (exc.length > 0) params.set('exc', exc.join(','));
            if (lockedVar) params.set('lock', lockedVar);
            if (currentHoverVar) params.set('view', currentHoverVar);

            const newUrl = window.location.origin + window.location.pathname + '?' + params.toString();
            window.history.replaceState(null, '', newUrl);

            try {{
                navigator.clipboard.writeText(newUrl).then(() => {{
                    const toast = document.getElementById('copy-toast');
                    toast.style.opacity = 1; setTimeout(() => toast.style.opacity = 0, 2000);
                }});
            }} catch(e) {{ alert("URL updated in your address bar."); }}
        }}

        function loadStateFromUrl() {{
            const params = new URLSearchParams(window.location.search);
            if (params.has('sort')) document.getElementById('sort-select').value = params.get('sort');
            if (params.has('cmp')) document.getElementById('comparison-select').value = params.get('cmp');
            if (params.has('search')) document.getElementById('var-search').value = params.get('search');
            if (params.has('alpha_c')) document.getElementById('alpha-classic').value = params.get('alpha_c');
            if (HAS_NEW && params.has('alpha_m')) document.getElementById('alpha-ml').value = params.get('alpha_m');

            if (!HAS_NEW) {{
                document.getElementById('sort-select').value = 'reference';
                document.getElementById('comparison-select').value = 'all';
            }}

            if (params.has('inc')) params.get('inc').split(',').forEach(v => {{
                if (filterStates[v] !== undefined) {{ filterStates[v] = 1; document.getElementById('flt-' + v).className = 'filter-item state-1'; }}
            }});
            if (params.has('exc')) params.get('exc').split(',').forEach(v => {{
                if (filterStates[v] !== undefined) {{ filterStates[v] = -1; document.getElementById('flt-' + v).className = 'filter-item state--1'; }}
            }});

            if (params.has('lock')) {{
                const lockVar = params.get('lock');
                if (rawData.some(item => item.var_name === lockVar)) lockedVar = lockVar;
            }}

            updateLockHint();

            changeLayout(); // Automatically triggers updatePlot

            if (lockedVar) {{
                const selected = rawData.find(item => item.var_name === lockedVar);
                if (selected) setTimeout(() => loadImages(selected.var_name, selected.ref_folder, selected.new_folder), 200);
                return;
            }}

            if (params.has('view')) {{
                const viewVar = params.get('view');
                const d = rawData.find(item => item.var_name === viewVar);
                if (d) setTimeout(() => loadImages(d.var_name, d.ref_folder, d.new_folder), 200);
            }}
        }}

        function getActiveFilters() {{
            let includes = [], excludes = [];
            for (const [v, state] of Object.entries(filterStates)) {{
                if (state === 1) includes.push(v);
                if (state === -1) excludes.push(v);
            }}
            return {{ includes, excludes }};
        }}

        function matchesSearch(item, query) {{
            const q = (query || '').trim().toLowerCase();
            if (!q) return true;

            const direct = (item.var_name || '').toLowerCase();
            if (direct.includes(q)) return true;

            if (item.components.length === 2) {{
                const rev = `${{item.components[1]}}_${{item.components[0]}}`.toLowerCase();
                if (rev.includes(q)) return true;
            }}

            return item.components.some(c => c.toLowerCase().includes(q));
        }}

        function passesComparisonFilter(item, mode) {{
            if (!HAS_NEW) return true;
            if (mode === 'all') return true;
            if (item.new === null) return false;
            if (mode === 'improvement') return item.new > item.reference;
            if (mode === 'regression') return item.new < item.reference;
            return true;
        }}

        function passesAlphaFilter(item, referenceRange, newRange) {{
            if (!inRange(item.reference, referenceRange)) return false;
            if (!HAS_NEW) return true;
            return inRange(item.new, newRange);
        }}

        function getDataPointFromEvent(data) {{
            if (!data || !data.points) return null;
            const point = data.points.find(p => Array.isArray(p.customdata) && p.customdata.length >= 5 && p.customdata[0] !== null);
            return point ? point.customdata : null;
        }}

        function handleHoverEvent(data) {{
            if (lockedVar !== null) return;
            const custom = getDataPointFromEvent(data);
            if (!custom) return;
            const [varName, , , refFolder, newFolder] = custom;
            loadImages(varName, refFolder, newFolder);
        }}

        function handleClickEvent(data) {{
            const custom = getDataPointFromEvent(data);
            if (!custom) return;
            const [varName, , , refFolder, newFolder] = custom;

            if (lockedVar === varName) {{
                lockedVar = null;
                updateLockHint();
                updatePlot();
                return;
            }}

            if (lockedVar !== null) return;

            lockedVar = varName;
            loadImages(varName, refFolder, newFolder);
            updateLockHint();
            updatePlot();
        }}

        function onModalOverlayClick(event) {{
            if (event.target && event.target.id === 'img-modal') closeImageModal();
        }}

        function closeImageModal() {{
            document.getElementById('img-modal').classList.remove('open');
            document.getElementById('img-modal-content').innerHTML = '';
        }}

        function openImageModal(contentHtml) {{
            const modal = document.getElementById('img-modal');
            const content = document.getElementById('img-modal-content');
            content.innerHTML = contentHtml;
            modal.classList.add('open');
        }}

        function inferPdfFromPngSrc(src) {{
            if (!src || !src.includes('.png')) return null;
            return src.replace(/\\.png(\\?.*)?$/i, '.pdf$1');
        }}

        function renderPdfLink(pdfUrl) {{
            if (!pdfUrl) return '<div class="img-modal-note">PDF unavailable.</div>';
            return `<a class="img-modal-link" href="${{pdfUrl}}" target="_blank" download>Download PDF</a>`;
        }}

        function openSingleImageModal(imageEl, title) {{
            if (!imageEl || !imageEl.src || imageEl.style.display === 'none') return;
            const pdfUrl = inferPdfFromPngSrc(imageEl.src);
            openImageModal(`
                <h3 class="img-modal-title">${{title}}</h3>
                <img class="img-modal-single" src="${{imageEl.src}}" alt="${{title}}">
                <div style="text-align:center;">${{renderPdfLink(pdfUrl)}}</div>
            `);
        }}

        function openRowTripletModal(prefix, rowTitle) {{
            const cards = [];
            comparisonKinds.forEach(kind => {{
                const img = document.getElementById(prefix + '_' + kind);
                if (!img || !img.src || img.style.display === 'none') return;
                const pdfUrl = inferPdfFromPngSrc(img.src);
                cards.push(`
                    <div class="img-modal-panel">
                        <div class="img-modal-panel-title">${{comparisonLabels[kind]}}</div>
                        <img src="${{img.src}}" alt="${{rowTitle}} ${{comparisonLabels[kind]}}">
                        ${{renderPdfLink(pdfUrl)}}
                    </div>
                `);
            }});
            if (cards.length === 0) return;

            openImageModal(`
                <h3 class="img-modal-title">${{rowTitle}}</h3>
                <div class="img-modal-triplet">${{cards.join('')}}</div>
            `);
        }}

        function openPairImageModal(kind) {{
            const classicImg = document.getElementById('classic_' + kind);
            const mlImg = document.getElementById('ml_' + kind);
            const classicVisible = classicImg && classicImg.src && classicImg.style.display !== 'none';
            const mlVisible = mlImg && mlImg.src && mlImg.style.display !== 'none';
            if (!classicVisible && !mlVisible) return;

            const titleText = comparisonLabels[kind] || kind;
            if (!HAS_NEW) {{
                if (classicVisible) openSingleImageModal(classicImg, `Reference - ${{titleText}}`);
                return;
            }}
            const classicHtml = classicVisible
                ? `<div class="img-modal-panel"><div class="img-modal-panel-title">Reference</div><img src="${{classicImg.src}}" alt="Reference ${{titleText}}">${{renderPdfLink(inferPdfFromPngSrc(classicImg.src))}}</div>`
                : `<div class="img-modal-panel"><div class="img-modal-panel-title">Reference</div><div class="img-modal-note">Image unavailable.</div></div>`;
            const mlHtml = mlVisible
                ? `<div class="img-modal-panel"><div class="img-modal-panel-title">New</div><img src="${{mlImg.src}}" alt="New ${{titleText}}">${{renderPdfLink(inferPdfFromPngSrc(mlImg.src))}}</div>`
                : `<div class="img-modal-panel"><div class="img-modal-panel-title">New</div><div class="img-modal-note">Image unavailable.</div></div>`;

            openImageModal(`
                <h3 class="img-modal-title">${{titleText}}</h3>
                <div class="img-modal-pair">${{classicHtml}}${{mlHtml}}</div>
            `);
        }}

        function bindImageInteractionHandlers() {{
            ['classic', 'ml'].forEach(prefix => {{
                comparisonKinds.forEach(kind => {{
                    const img = document.getElementById(prefix + '_' + kind);
                    if (!img || img.dataset.zoomBound === '1') return;
                    img.dataset.zoomBound = '1';
                    img.addEventListener('click', event => {{
                        event.stopPropagation();
                        activeComparisonKind = kind;
                        const rowName = prefix === 'classic' ? 'Reference' : 'New';
                        openSingleImageModal(img, `${{rowName}} - ${{comparisonLabels[kind]}}`);
                    }});
                }});
            }});

            document.querySelectorAll('#box-images .img-title').forEach((titleEl, idx) => {{
                if (titleEl.dataset.zoomBound === '1') return;
                titleEl.dataset.zoomBound = '1';
                const kind = comparisonKinds[idx % comparisonKinds.length];
                titleEl.addEventListener('click', event => {{
                    event.stopPropagation();
                    activeComparisonKind = kind;
                    openPairImageModal(kind);
                }});
            }});

            if (lblClassic && lblClassic.dataset.zoomBound !== '1') {{
                lblClassic.dataset.zoomBound = '1';
                lblClassic.addEventListener('click', event => {{
                    event.stopPropagation();
                    openRowTripletModal('classic', 'Reference');
                }});
            }}
            if (lblMl && lblMl.dataset.zoomBound !== '1') {{
                lblMl.dataset.zoomBound = '1';
                lblMl.addEventListener('click', event => {{
                    event.stopPropagation();
                    openRowTripletModal('ml', 'New');
                }});
            }}

            if (document.body.dataset.modalEscBound !== '1') {{
                document.body.dataset.modalEscBound = '1';
                document.addEventListener('keydown', event => {{
                    if (event.key === 'Escape') closeImageModal();
                }});
            }}
        }}

        function bindPanelFullscreenHandlers() {{
            [bMatrix, bScatter, bImages].forEach(panel => {{
                if (!panel || panel.dataset.fullscreenBound === '1') return;
                panel.dataset.fullscreenBound = '1';
                panel.addEventListener('dblclick', event => {{
                    if (event.target.closest('.img-col') || event.target.closest('.img-title') || event.target.closest('.row-label')) return;
                    event.preventDefault();
                    togglePanelExpansion(panel.id);
                }});
            }});
        }}

        function configurePanelResizeObserver() {{
            const ro = new ResizeObserver(() => {{
                Plotly.Plots.resize(document.getElementById('plot-container'));
                Plotly.Plots.resize(document.getElementById('matrix-container'));
            }});
            ro.observe(bScatter);
            ro.observe(bMatrix);
        }}

        async function downloadPlotAsPdf(graphDiv, filenameBase) {{
            if (!window.jspdf || !window.jspdf.jsPDF) {{
                alert('PDF export library is not available.');
                return;
            }}
            const width = Math.max(600, graphDiv.clientWidth || 900);
            const height = Math.max(400, graphDiv.clientHeight || 600);
            const pngData = await Plotly.toImage(graphDiv, {{ format: 'png', width: width * 2, height: height * 2 }});

            const {{ jsPDF }} = window.jspdf;
            const pdf = new jsPDF({{ orientation: width >= height ? 'landscape' : 'portrait', unit: 'pt', format: 'a4' }});
            const pageW = pdf.internal.pageSize.getWidth();
            const pageH = pdf.internal.pageSize.getHeight();
            const scale = Math.min(pageW / width, pageH / height);
            const imgW = width * scale;
            const imgH = height * scale;
            const offsetX = (pageW - imgW) / 2;
            const offsetY = (pageH - imgH) / 2;
            pdf.addImage(pngData, 'PNG', offsetX, offsetY, imgW, imgH);
            pdf.save(`${{filenameBase}}.pdf`);
        }}

        function getPlotlyConfig(filenameBase) {{
            return {{
                responsive: true,
                displaylogo: false,
                toImageButtonOptions: {{ format: 'png', filename: filenameBase, scale: 2 }},
                modeBarButtonsToAdd: [{{
                    name: 'Download as PDF',
                    icon: Plotly.Icons.camera,
                    click: (graphDiv) => downloadPlotAsPdf(graphDiv, filenameBase)
                }}]
            }};
        }}

        // --- PLOTTING LOGIC ---
        function updatePlot() {{
            const sortBy = document.getElementById('sort-select').value;
            const comparisonMode = document.getElementById('comparison-select').value;
            const searchQuery = document.getElementById('var-search').value;
            const alphaClassicRange = parseAlphaRange(document.getElementById('alpha-classic').value);
            const alphaMlRange = HAS_NEW ? parseAlphaRange(document.getElementById('alpha-ml').value) : [0.0, 1.0];
            const {{ includes, excludes }} = getActiveFilters();

            const activeData = rawData.filter(d => {{
                if (d.components.some(c => excludes.includes(c))) return false;
                if (includes.length > 0 && !d.components.some(c => includes.includes(c))) return false;
                if (!matchesSearch(d, searchQuery)) return false;
                if (!passesAlphaFilter(d, alphaClassicRange, alphaMlRange)) return false;
                return passesComparisonFilter(d, comparisonMode);
            }});

            if (lockedVar !== null && !activeData.some(d => d.var_name === lockedVar)) {{
                lockedVar = null;
            }}
            updateLockHint();

            // 1. SCATTER PLOT
            const scatterData = [...activeData].sort((a, b) => {{
                let valA = a[sortBy] !== null ? a[sortBy] : 2;
                let valB = b[sortBy] !== null ? b[sortBy] : 2;
                return valA - valB;
            }});

            let x_vals = [], y_c = [], y_m = [], custom = [], r_x = [], r_y = [], g_x = [], g_y = [];
            scatterData.forEach((d, i) => {{
                x_vals.push(i);
                y_c.push(d.reference);
                y_m.push(d.new);
                custom.push([d.var_name, d.reference, d.new, d.ref_folder, d.new_folder]);
                if (d.new !== null) {{
                    if (d.new < d.reference) {{
                        r_x.push(i, i, null);
                        r_y.push(d.reference, d.new, null);
                    }} else if (d.new > d.reference) {{
                        g_x.push(i, i, null);
                        g_y.push(d.reference, d.new, null);
                    }}
                }}
            }});

            const tClassic = {{
                x: x_vals,
                y: y_c,
                mode: 'markers',
                type: 'scatter',
                marker: {{ size: 5, color: '#3366cc' }},
                name: 'Reference',
                customdata: custom,
                hovertemplate: HAS_NEW
                    ? "<b>%{{customdata[0]}}</b><br>Reference: %{{customdata[1]:.4f}}<br>New: %{{customdata[2]:.4f}}<extra></extra>"
                    : "<b>%{{customdata[0]}}</b><br>Reference: %{{customdata[1]:.4f}}<extra></extra>"
            }};
            const tML = {{
                x: x_vals,
                y: y_m,
                mode: 'markers',
                type: 'scatter',
                marker: {{ size: 5, color: '#ff9900', symbol: 'diamond' }},
                name: 'New',
                customdata: custom,
                hoverinfo: 'skip'
            }};
            const tRed = {{ x: r_x, y: r_y, mode: 'lines', type: 'scatter', line: {{ color: 'red', width: 1.5 }}, opacity: 0.5, name: 'Regression', hoverinfo: 'skip' }};
            const tGreen = {{ x: g_x, y: g_y, mode: 'lines', type: 'scatter', line: {{ color: 'green', width: 1.5 }}, opacity: 0.5, name: 'Improvement', hoverinfo: 'skip' }};

            const scatterTraces = HAS_NEW ? [tGreen, tRed, tClassic, tML] : [tClassic];
            const scatterSelectionShapes = [];
            if (lockedVar !== null) {{
                const selectedItem = scatterData.find(d => d.var_name === lockedVar);
                if (selectedItem) {{
                    const selX = scatterData.findIndex(d => d.var_name === lockedVar);
                    scatterSelectionShapes.push({{
                        type: 'circle',
                        xref: 'x',
                        yref: 'y',
                        x0: selX - 0.45,
                        x1: selX + 0.45,
                        y0: selectedItem.reference - 0.035,
                        y1: selectedItem.reference + 0.035,
                        line: {{ color: '#0b2f73', width: 2 }},
                        fillcolor: 'rgba(0,0,0,0)'
                    }});
                    scatterTraces.push({{
                        x: [selX],
                        y: [selectedItem.reference],
                        mode: 'markers',
                        type: 'scatter',
                        marker: {{ symbol: 'circle-open', size: 22, color: 'rgba(0,0,0,0)', line: {{ color: '#0b2f73', width: 2 }} }},
                        hoverinfo: 'skip',
                        showlegend: false
                    }});
                    if (HAS_NEW && selectedItem.new !== null) {{
                        scatterSelectionShapes.push({{
                            type: 'circle',
                            xref: 'x',
                            yref: 'y',
                            x0: selX - 0.45,
                            x1: selX + 0.45,
                            y0: selectedItem.new - 0.035,
                            y1: selectedItem.new + 0.035,
                            line: {{ color: '#0b2f73', width: 2 }},
                            fillcolor: 'rgba(0,0,0,0)'
                        }});
                        scatterTraces.push({{
                            x: [selX],
                            y: [selectedItem.new],
                            mode: 'markers',
                            type: 'scatter',
                            marker: {{ symbol: 'circle-open', size: 22, color: 'rgba(0,0,0,0)', line: {{ color: '#0b2f73', width: 2 }} }},
                            hoverinfo: 'skip',
                            showlegend: false
                        }});
                    }}
                }}
            }}

            const shownYValues = [
                ...y_c.filter(v => Number.isFinite(v)),
                ...(HAS_NEW ? y_m.filter(v => Number.isFinite(v)) : [])
            ];
            const yMinData = shownYValues.length ? Math.min(...shownYValues) : 0.0;
            const yMaxData = shownYValues.length ? Math.max(...shownYValues) : 1.0;
            const yPad = Math.max(0.01, (yMaxData - yMinData) * 0.08);
            let yMin = Math.max(0.0, yMinData - yPad);
            let yMax = Math.min(1.0, yMaxData + yPad);
            if (yMax - yMin < 0.05) {{
                const center = (yMax + yMin) / 2;
                yMin = Math.max(0.0, center - 0.025);
                yMax = Math.min(1.0, center + 0.025);
            }}

            const scatterLayout = {{
                title: {{ text: "Sorted p-Values", font: {{size: 13}} }}, xaxis: {{ showticklabels: false }}, yaxis: {{ title: "p-Value", range: [yMin, yMax] }},
                hovermode: "closest", margin: {{ t: 30, l: 40, r: 10, b: 20 }},
                shapes: [
                    {{ type: 'line', x0: 0, x1: 1, y0: 0.01, y1: 0.01, xref: 'paper', line: {{color: 'black', width: 1}} }},
                    {{ type: 'line', x0: 0, x1: 1, y0: 0.05, y1: 0.05, xref: 'paper', line: {{color: 'black', width: 1}} }},
                    ...scatterSelectionShapes
                ]
            }};

            Plotly.react('plot-container', scatterTraces, scatterLayout, getPlotlyConfig('pvalues_scatter'));
            const scatterDiv = document.getElementById('plot-container');
            if (scatterDiv.removeAllListeners) {{
                scatterDiv.removeAllListeners('plotly_hover');
                scatterDiv.removeAllListeners('plotly_click');
            }}
            scatterDiv.on('plotly_hover', handleHoverEvent);
            scatterDiv.on('plotly_click', handleClickEvent);

            // 2. MATRIX PLOT
            const matrixVarSet = new Set();
            activeData.forEach(item => item.components.forEach(c => matrixVarSet.add(c)));
            const matrixVariables = variablesList.filter(v => matrixVarSet.has(v));
            const singleMap = new Map();
            const pairMap = new Map();
            activeData.forEach(item => {{
                if (item.components.length === 1) {{
                    singleMap.set(item.components[0], item);
                }} else if (item.components.length === 2) {{
                    const key = [...item.components].sort().join('|');
                    pairMap.set(key, item);
                }}
            }});

            const nVars = matrixVariables.length;
            let z_main = [], custom_matrix = [];
            for (let i = 0; i < nVars; i++) {{
                let row_main = [], row_custom = [];
                const varY = matrixVariables[i];
                for (let j = 0; j < nVars; j++) {{
                    const varX = matrixVariables[j];
                    if (j > i) {{
                        row_main.push(null);
                        row_custom.push(null);
                        continue;
                    }}

                    let d = null;
                    if (i === j) {{
                        d = singleMap.get(varX) || null;
                    }} else {{
                        d = pairMap.get([varX, varY].sort().join('|')) || null;
                    }}

                    if (d) {{
                        row_main.push(d[sortBy] !== null ? d[sortBy] : null);
                        row_custom.push([d.var_name, d.reference, d.new, d.ref_folder, d.new_folder]);
                    }} else {{
                        row_main.push(null);
                        row_custom.push(null);
                    }}
                }}
                z_main.push(row_main);
                custom_matrix.push(row_custom);
            }}

            const cScale = [ [0.0, '#d73027'], [0.05, '#fee08b'], [1.0, '#1a9850'] ];
            const matrixTicks = Array.from({{length: nVars}}, (_, i) => i);
            const varToIdx = new Map(matrixVariables.map((v, i) => [v, i]));
            const matrixAxisMin = -0.5;
            const matrixAxisMax = nVars > 0 ? nVars - 0.5 : 0.5;
            const tHeat = {{
                type: 'heatmap',
                x: matrixTicks,
                y: matrixTicks,
                z: z_main,
                customdata: custom_matrix,
                zmin: 0,
                zmax: 1,
                colorscale: cScale,
                hoverongaps: false,
                colorbar: {{ title: 'p-Val', thickness: 10, len: 1.0, outlinewidth: 0, tickfont: {{size: 10}} }},
                hovertemplate: HAS_NEW
                    ? "<b>%{{customdata[0]}}</b><br>Reference: %{{customdata[1]:.4f}}<br>New: %{{customdata[2]:.4f}}<extra></extra>"
                    : "<b>%{{customdata[0]}}</b><br>Reference: %{{customdata[1]:.4f}}<extra></extra>"
            }};

            const matrixTraces = [tHeat];
            const matrixSelectionShapes = [];
            if (lockedVar !== null) {{
                const selectedItem = activeData.find(d => d.var_name === lockedVar);
                if (selectedItem) {{
                    let selX = null;
                    let selY = null;
                    if (selectedItem.components.length === 1) {{
                        const v = selectedItem.components[0];
                        if (varToIdx.has(v)) {{
                            selX = varToIdx.get(v);
                            selY = varToIdx.get(v);
                        }}
                    }} else if (selectedItem.components.length === 2) {{
                        const a = selectedItem.components[0];
                        const b = selectedItem.components[1];
                        if (varToIdx.has(a) && varToIdx.has(b)) {{
                            const idxA = varToIdx.get(a);
                            const idxB = varToIdx.get(b);
                            selX = Math.min(idxA, idxB);
                            selY = Math.max(idxA, idxB);
                        }}
                    }}
                    if (selX !== null && selY !== null) {{
                        matrixSelectionShapes.push({{
                            type: 'rect',
                            xref: 'x',
                            yref: 'y',
                            x0: selX - 0.5,
                            x1: selX + 0.5,
                            y0: selY - 0.5,
                            y1: selY + 0.5,
                            line: {{ color: '#0b2f73', width: 4 }},
                            fillcolor: 'rgba(0,0,0,0)',
                            layer: 'above'
                        }});
                        matrixTraces.push({{
                            type: 'scatter',
                            mode: 'markers',
                            x: [selX],
                            y: [selY],
                            marker: {{ symbol: 'square-open', color: 'rgba(0,0,0,0)', size: 30, line: {{ color: '#0b2f73', width: 4 }} }},
                            hoverinfo: 'skip',
                            showlegend: false
                        }});
                    }}
                }}
            }}

            const matrixLayout = {{
                title: {{ text: "Variable Matrix", font: {{size: 13}} }},
                xaxis: {{
                    tickangle: -45,
                    tickmode: 'array',
                    tickvals: matrixTicks,
                    ticktext: matrixVariables,
                    automargin: true,
                    showgrid: false,
                    showline: false,
                    zeroline: false,
                    tickfont: {{size: 8}},
                    ticklabelstandoff: 0,
                    range: [matrixAxisMin, matrixAxisMax]
                }},
                yaxis: {{
                    tickmode: 'array',
                    tickvals: matrixTicks,
                    ticktext: matrixVariables,
                    automargin: true,
                    showgrid: false,
                    showline: false,
                    zeroline: false,
                    tickfont: {{size: 8}},
                    ticklabelstandoff: 0,
                    scaleanchor: 'x',
                    scaleratio: 1,
                    constrain: 'domain',
                    range: [matrixAxisMax, matrixAxisMin]
                }},
                margin: {{ t: 30, l: 8, r: 10, b: 20 }},
                plot_bgcolor: '#fff',
                paper_bgcolor: '#fff',
                shapes: matrixSelectionShapes
            }};

            Plotly.react('matrix-container', matrixTraces, matrixLayout, getPlotlyConfig('gof_matrix'));
            const matrixDiv = document.getElementById('matrix-container');
            if (matrixDiv.removeAllListeners) {{
                matrixDiv.removeAllListeners('plotly_hover');
                matrixDiv.removeAllListeners('plotly_click');
            }}
            matrixDiv.on('plotly_hover', handleHoverEvent);
            matrixDiv.on('plotly_click', handleClickEvent);
        }}

        function loadImages(varName, refFolder, newFolder) {{
            currentHoverVar = varName;
            document.getElementById('var-title').innerText = "Distributions for: " + varName;
            const buildPath = (base, folder, suffix) => base + "/" + folder + "/" + suffix;

            const classicElements = [document.getElementById('classic_prefit'), document.getElementById('classic_postfit'), document.getElementById('classic_gof')];
            classicElements[0].src = buildPath(REFERENCE_BASE, refFolder, "plots/" + refFolder + "_prefit.png");
            classicElements[1].src = buildPath(REFERENCE_BASE, refFolder, "plots/" + refFolder + "_postfit.png");
            classicElements[2].src = buildPath(REFERENCE_BASE, refFolder, "gof.png");
            classicElements.forEach(el => el.style.display = 'block');

            const mlElements = [document.getElementById('ml_prefit'), document.getElementById('ml_postfit'), document.getElementById('ml_gof')];
            if(newFolder) {{
                mlElements[0].src = buildPath(NEW_BASE, newFolder, "plots/" + newFolder + "_prefit.png");
                mlElements[1].src = buildPath(NEW_BASE, newFolder, "plots/" + newFolder + "_postfit.png");
                mlElements[2].src = buildPath(NEW_BASE, newFolder, "gof.png");
                mlElements.forEach(el => el.style.display = 'block');
            }} else {{
                mlElements.forEach(el => el.style.display = 'none');
            }}
        }}

        // --- STARTUP ---
        configureDataModeUI();
        bindImageInteractionHandlers();
        bindPanelFullscreenHandlers();
        bindHelpOverlayHandlers();
        bindImmediatePanelHide();
        configurePanelResizeObserver();
        updateLockHint();
        loadStateFromUrl();
    </script>
</body>
</html>
"""

with open("index.html", "w") as f:
    f.write(html_template)

print("Finished! Wrote index.html and copied necessary images.")
