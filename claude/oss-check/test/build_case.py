"""Rebuild the oss-check test cases, offline and reproducibly.

    python build_case.py [/tmp/oss-check-cases]

Writes 9 small repositories and 4 simulated Python environments:

- darius-1-markitdown: the author's measurement of 2026-08-29 rebuilt on its form:
  an empty baseline (pip, setuptools), the "a la carte" stack, markitdown and
  markitdown[all], as site-packages folders with *.dist-info/RECORD files whose
  sizes reproduce the published figures, plus a small MIT source repo.
- darius-2-open-webui: a repo shaped like Open WebUI 0.11.1 (2026-08-31): the
  README promises no external connections, the code downloads an embedding
  model from huggingface.co at start, OFFLINE_MODE cuts it, telemetry is opt-in.
- darius-3-stirling-pdf: a repo shaped like Stirling PDF 2.14.3 (2026-09-01): the
  LICENSE says MIT then carves out 6 directories, 2 of them proprietary with a
  production clause; a dormant licence checker calls a key service.
- piege-double-licence, piege-extra-lourd: dual AGPL or commercial; heavy
  packages hidden behind an optional extra.
- propre-mit, propre-apache, propre-bsd: clean repos with false-positive traps
  ("proprietary" in a comment, huggingface.co in docs and tests, GPL in a CHANGELOG).
- controle-busl: a whole repo under BUSL-1.1, to exercise the STOP verdict.

Project names, holders and code are invented. Big files are sparse (os.truncate):
the script measures apparent sizes, so 507 Mo of simulated packages take almost
no disk. Standard library only.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "oss-check-cases").resolve()
MB = 1_000_000

MIT = """MIT License

Copyright (c) 2026 {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
BSD3 = """BSD 3-Clause License

Copyright (c) 2026, {holder}

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED.
"""
APACHE = """
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   (Sections 3 to 9 shortened for the test case.)

   END OF TERMS AND CONDITIONS
"""
AGPL = """                    GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

  (Remaining sections shortened for the test case.)
"""
OFL = """Copyright 2026 The Example Sans Project Authors

This Font Software is licensed under the SIL Open Font License, Version 1.1.

SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007

PERMISSION AND CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining a copy of
the Font Software, to use, study, copy, merge, embed, modify, redistribute, and
sell modified and unmodified copies of the Font Software.
"""
PROPRIETARY = """Papyrus PDF Proprietary License

Copyright (c) 2026 Papyrus Labs.

Production use of the Papyrus Software is only permitted with a valid User License.

You may use the Papyrus Software for development and testing without a User
License. You may not remove or circumvent the license checks.
"""
BUSL = """Business Source License 1.1

Parameters

Licensor:             Queueforge Labs
Licensed Work:        Queueforge 3.2. The Licensed Work is (c) 2026 Queueforge Labs.
Additional Use Grant: None
Change Date:          2030-06-01
Change License:       Apache License, Version 2.0

Terms

The Licensor hereby grants you the right to copy, modify, create derivative
works, redistribute, and make non-production use of the Licensed Work. The
Licensor may make an Additional Use Grant, above, permitting limited
production use.
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sparse(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)


# ------------------------------------------------------------- simulated envs

def dist(sp, name, version, total, script=None):
    """One installed distribution whose RECORD files add up to exactly `total` bytes."""
    di = f"{name.replace('-', '_')}-{version}.dist-info"
    pkg = name.replace("-", "_").replace(".", "_").lower()
    files = {f"{di}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
             f"{di}/WHEEL": "Wheel-Version: 1.0\nGenerator: oss-check-test\nRoot-Is-Purelib: true\n",
             f"{di}/INSTALLER": "pip\n",
             f"{pkg}/__init__.py": f"# simulated package {name} {version}\n"}
    if script:
        files[f"../../../bin/{script}"] = f"#!/bin/sh\n# simulated entry point {script}\n"
    for rel, text in files.items():
        write(sp / rel, text)
    small = sum(len(t.encode()) for t in files.values())
    big_rel, rec_rel = f"{pkg}/_payload.bin", f"{di}/RECORD"
    big = total - small
    for _ in range(6):
        record = "".join(f"{k},sha256=simulated,{len(v.encode())}\n" for k, v in files.items())
        record += f"{big_rel},sha256=simulated,{big}\n{rec_rel},,\n"
        new = total - small - len(record.encode())
        if new == big:
            break
        big = new
    write(sp / rec_rel, record)
    sparse(sp / big_rel, big)


BASELINE = [("pip", "24.0", 10.2, "pip"), ("setuptools", "69.5.1", 3.6, None)]
A_LA_CARTE = [("lxml", "5.2.2", 16.5), ("pillow", "10.4.0", 10.1), ("pypdf", "4.3.1", 1.9),
              ("python-docx", "1.1.2", 1.1), ("openpyxl", "3.1.5", 2.6), ("python-pptx", "1.0.2", 3.4),
              ("XlsxWriter", "3.2.0", 1.4), ("et-xmlfile", "1.1.0", 0.1), ("beautifulsoup4", "4.12.3", 1.6),
              ("soupsieve", "2.5", 0.2), ("markdownify", "0.13.1", 0.1), ("six", "1.16.0", 0.1),
              ("typing-extensions", "4.12.2", 0.4)]
MARKITDOWN = [("markitdown", "0.1.2", 0.4), ("magika", "0.6.1", 4.0), ("numpy", "2.1.0", 48.6),
              ("sympy", "1.13.2", 48.6), ("onnxruntime", "1.19.0", 33.7), ("beautifulsoup4", "4.12.3", 1.6),
              ("soupsieve", "2.5", 0.2), ("markdownify", "0.13.1", 0.1), ("six", "1.16.0", 0.1),
              ("requests", "2.32.3", 0.3), ("charset-normalizer", "3.3.2", 0.5), ("idna", "3.8", 0.5),
              ("urllib3", "2.2.2", 0.6), ("certifi", "2024.8.30", 0.4), ("mpmath", "1.3.0", 3.1),
              ("coloredlogs", "15.0.1", 0.2), ("humanfriendly", "10.0", 0.5), ("flatbuffers", "24.3.25", 0.1),
              ("packaging", "24.1", 0.3), ("protobuf", "5.28.0", 2.5), ("click", "8.1.7", 0.6),
              ("python-dotenv", "1.0.1", 0.1), ("defusedxml", "0.7.1", 0.2), ("colorama", "0.4.6", 0.1),
              ("pyreadline3", "3.4.1", 0.4)]
MARKITDOWN_ALL_EXTRA = [
    ("pandas", "2.2.2", 52.6), ("SpeechRecognition", "3.10.4", 42.7), ("lxml", "5.2.2", 16.5),
    ("pillow", "10.4.0", 10.1), ("python-docx", "1.1.2", 1.1), ("openpyxl", "3.1.5", 2.6),
    ("python-pptx", "1.0.2", 3.4), ("XlsxWriter", "3.2.0", 1.4), ("et-xmlfile", "1.1.0", 0.1),
    ("pdfminer.six", "20240706", 5.6), ("pdfplumber", "0.11.4", 0.3), ("pypdfium2", "4.30.0", 8.9),
    ("mammoth", "1.8.0", 0.3), ("cobble", "0.1.4", 0.1), ("olefile", "0.47", 0.2), ("pydub", "0.25.1", 0.3),
    ("youtube-transcript-api", "0.6.2", 0.2), ("xlrd", "2.0.1", 0.5), ("python-dateutil", "2.9.0", 0.5),
    ("pytz", "2024.1", 2.9), ("tzdata", "2024.1", 1.9), ("azure-ai-documentintelligence", "1.0.0", 2.1),
    ("azure-core", "1.30.2", 0.9), ("azure-identity", "1.17.1", 0.8), ("msal", "1.30.0", 0.6),
    ("msal-extensions", "1.2.0", 0.1), ("cryptography", "43.0.0", 13.3), ("cffi", "1.17.0", 1.0),
    ("pycparser", "2.22", 0.6), ("isodate", "0.6.1", 0.2), ("PyJWT", "2.9.0", 0.2)]
# sympy and numpy are both published at 48,6 Mo: 40 000 bytes apart keeps the published order
NUDGE = {"sympy": 40_000, "numpy": -40_000}


def env(path, dists):
    sp = path / "lib" / "python3.10" / "site-packages"
    for name, version, mb, script in BASELINE + [d + ("markitdown" if d[0] == "markitdown" else None,)
                                                 for d in dists]:
        dist(sp, name, version, round(mb * MB) + NUDGE.get(name, 0), script)


def build_envs(case):
    envs = case / "envs"
    sp = envs / "temoin" / "lib" / "python3.10" / "site-packages"
    for name, version, mb, script in BASELINE:
        dist(sp, name, version, round(mb * MB), script)
    env(envs / "a-la-carte", A_LA_CARTE)
    env(envs / "markitdown", MARKITDOWN)
    env(envs / "markitdown-all", MARKITDOWN + MARKITDOWN_ALL_EXTRA)


def node_pkg(nm, name, version, total, license_id="MIT"):
    d = nm / name
    pj = json.dumps({"name": name, "version": version, "license": license_id}, indent=2) + "\n"
    write(d / "package.json", pj)
    idx = f"module.exports = {{}}; // simulated {name}\n"
    write(d / "index.js", idx)
    sparse(d / "payload.bin", total - len(pj.encode()) - len(idx.encode()))


# ------------------------------------------------------------- repositories

def darius_1(base):
    case = base / "darius-1-markitdown"
    build_envs(case)
    r = case / "repo"
    write(r / "LICENSE", MIT.format(holder="Convertisseur authors"))
    write(r / "README.md", "# convertisseur\n\nConvert PDF, Word, Excel, PowerPoint and HTML files to Markdown.\n"
          "Install the extras with `pip install convertisseur[all]`.\n")
    write(r / "pyproject.toml", '[project]\nname = "convertisseur"\nversion = "0.1.0"\nlicense = "MIT"\n'
          'dependencies = ["beautifulsoup4", "requests", "markdownify", "magika>=0.6", "charset-normalizer",'
          ' "defusedxml"]\n\n[project.optional-dependencies]\nall = ["pandas", "SpeechRecognition", "python-pptx",'
          ' "mammoth", "openpyxl", "pdfminer.six", "pydub"]\n')
    write(r / "src" / "convertisseur" / "__init__.py",
          '"""Convert documents to Markdown. Format detection runs a local model, no download."""\n'
          "from magika import Magika\n\n\ndef detect(path):\n    return Magika().identify_path(path).output.label\n")
    return case


def darius_2(base):
    r = base / "darius-2-open-webui"
    write(r / "LICENSE", BSD3.format(holder="Chat Local contributors"))
    write(r / "README.md", "# Chat Local\n\nThe chat interface you install at home to talk to local models.\n\n"
          "Chat Local does not make any external connections, your data stays securely on your "
          "locally hosted server.\n")
    write(r / "pyproject.toml", '[project]\nname = "chat-local"\nversion = "0.11.1"\nlicense = "BSD-3-Clause"\n'
          'dependencies = ["fastapi", "uvicorn", "sentence-transformers", "huggingface_hub", "posthog"]\n')
    write(r / "backend" / "config.py",
          'import os\n\n'
          'RAG_EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")\n'
          'RAG_EMBEDDING_MODEL_AUTO_UPDATE = os.environ.get("RAG_EMBEDDING_MODEL_AUTO_UPDATE", "true") == "true"\n'
          'OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "false").lower() == "true"\n\n'
          'if OFFLINE_MODE:\n    os.environ["HF_HUB_OFFLINE"] = "1"\n')
    write(r / "backend" / "retrieval" / "utils.py",
          "import os\n\nfrom huggingface_hub import snapshot_download\n"
          "from sentence_transformers import SentenceTransformer\n\n"
          "from backend.config import OFFLINE_MODE\n\n\n"
          "def get_model_path(model, update_model=False):\n"
          "    # Models are fetched from https://huggingface.co on first use\n"
          '    cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME")\n'
          "    local_files_only = not update_model\n"
          "    if OFFLINE_MODE:\n        local_files_only = True\n"
          "    return snapshot_download(repo_id=model, cache_dir=cache_dir, local_files_only=local_files_only)\n\n\n"
          "def get_ef(engine, embedding_model, auto_update=True):\n"
          '    if engine == "":\n'
          '        return SentenceTransformer(get_model_path(embedding_model, auto_update), device="cpu")\n'
          "    return None\n")
    write(r / "backend" / "telemetry.py",
          "import os\n\nfrom posthog import Posthog\n\n"
          'ENABLE_POSTHOG = os.environ.get("ENABLE_POSTHOG", "false").lower() == "true"\n'
          'POSTHOG_PROJECT = os.environ.get("POSTHOG_PROJECT", "")\n'
          'POSTHOG_HOST = "https://us.i.posthog.com"\n\n\n'
          "def track(event, props=None):\n"
          "    if ENABLE_POSTHOG:\n"
          '        client = Posthog(POSTHOG_PROJECT, host=POSTHOG_HOST)\n'
          '        client.capture("chat-local", event, properties=props or {})\n')
    write(r / "backend" / "main.py",
          "from fastapi import FastAPI\n\n"
          "from backend.config import RAG_EMBEDDING_MODEL, RAG_EMBEDDING_MODEL_AUTO_UPDATE\n"
          "from backend.retrieval.utils import get_ef\n\n"
          "app = FastAPI()\n"
          'app.state.EMBEDDING_FUNCTION = get_ef("", RAG_EMBEDDING_MODEL, RAG_EMBEDDING_MODEL_AUTO_UPDATE)\n')
    write(r / "docs" / "models.md", "# Models\n\nThe default embedding model comes from "
          "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2.\n")
    write(r / "tests" / "test_embedding.py",
          "from transformers import AutoModel\n\n\ndef test_model_loads():\n"
          '    assert AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")\n')
    return r


def darius_3(base):
    r = base / "darius-3-stirling-pdf"
    listed = ["app/proprietary/", "frontend/src/proprietary/", "app/core/src/main/resources/static/pdfjs/",
              "app/core/src/main/resources/static/js/thirdParty/", "frontend/public/vendor/fonts/",
              "docker/embedded/"]
    head = ("MIT License\n\nCopyright (c) 2026 Papyrus PDF contributors\n\n"
            "Portions of this software are licensed as follows:\n\n"
            "* All content that resides under the following directories is licensed under the\n"
            '  license defined in "app/proprietary/LICENSE":\n'
            f"    - {listed[0]}\n    - {listed[1]}\n"
            "* All content that resides under the following directories retains its own\n"
            "  license, defined in the LICENSE file of each directory:\n"
            + "".join(f"    - {d}\n" for d in listed[2:]) +
            '* Content outside of the above mentioned directories is available under the "MIT"\n'
            "  license as defined below.\n\n")
    write(r / "LICENSE", head + MIT.format(holder="Papyrus PDF contributors").split("\n\n", 2)[2])
    write(r / "README.md", "# Papyrus PDF\n\nThe PDF toolbox you host yourself: merge, sign, OCR, compress. "
          "55 tools, runs entirely on your server. Nothing ever uploads to a random website.\n")
    write(r / listed[0] / "LICENSE", PROPRIETARY)
    write(r / listed[1] / "LICENSE", PROPRIETARY)
    write(r / listed[2] / "LICENSE", APACHE)
    write(r / listed[3] / "LICENSE", MIT.format(holder="Example Charts authors"))
    write(r / listed[4] / "LICENSE", OFL)
    write(r / listed[5] / "LICENSE", BSD3.format(holder="Example Runtime authors"))
    write(r / listed[0] / "src/main/java/com/papyrus/license/KeygenLicenseVerifier.java", """package com.papyrus.license;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

/**
 * Checks a Papyrus User License against the key service.
 * Only runs when an administrator enters a license key.
 */
public class KeygenLicenseVerifier {

    private static final String KEYGEN_API = "https://api.keygen.sh/v1/accounts/";
    private static final String ACCOUNT = "papyrus-demo";

    private final String licenseKey;
    private final HttpClient client = HttpClient.newHttpClient();

    public KeygenLicenseVerifier(String licenseKey) {
        this.licenseKey = licenseKey;
    }

    public boolean verify() throws Exception {
        if (licenseKey == null || licenseKey.isBlank()) {
            return false;
        }
        HttpRequest request = HttpRequest.newBuilder(URI.create(KEYGEN_API + ACCOUNT + "/licenses/actions/validate-key"))
                .POST(HttpRequest.BodyPublishers.ofString("{}"))
                .build();
        return client.send(request, HttpResponse.BodyHandlers.ofString()).statusCode() == 200;
    }

    public void registerMachine(String fingerprint) throws Exception {
        if (licenseKey == null || licenseKey.isBlank()) {
            return;
        }
        HttpRequest request = HttpRequest.newBuilder(URI.create(KEYGEN_API + ACCOUNT + "/machines"))
                .POST(HttpRequest.BodyPublishers.ofString(fingerprint))
                .build();
        client.send(request, HttpResponse.BodyHandlers.ofString());
    }
}
""")
    write(r / "app/core/src/main/java/com/papyrus/core/MergeController.java",
          "package com.papyrus.core;\n\n// Merges PDF files locally; nothing leaves the server.\n"
          "public class MergeController {\n    public int tools() {\n        return 55;\n    }\n}\n")
    write(r / listed[2] / "pdf.worker.js", "// simulated pdf.js worker\nexport const version = '4.0.0';\n")
    write(r / "frontend/src/App.tsx", "export const App = () => null; // 55 tools\n")
    return r


def piege_double(base):
    r = base / "piege-double-licence"
    write(r / "LICENSE", AGPL)
    write(r / "LICENSE-COMMERCIAL.md", "# TableKit Commercial License\n\nThis Commercial License applies to customers "
          "who bought a TableKit subscription.\nIt replaces the AGPL-3.0 obligations for the subscriber's own "
          "products.\nUse under this license requires a paid subscription agreement with the licensor.\n")
    write(r / "package.json", json.dumps({
        "name": "tablekit", "version": "4.2.0", "license": "AGPL-3.0-only OR LicenseRef-Commercial",
        "dependencies": {"lodash": "^4.17.21", "@tablekit/core": "4.2.0", "chart-lite": "^2.1.0"}}, indent=2) + "\n")
    write(r / "README.md", "# TableKit\n\nData grids for the browser. TableKit is dual-licensed: AGPL-3.0 for open "
          "source projects, or a commercial license for closed-source products.\n")
    write(r / "src" / "index.js", "const core = require('@tablekit/core');\n\nmodule.exports = function grid(rows) {\n"
          "  return core.render(rows);\n};\n")
    nm = r / "node_modules"
    node_pkg(nm, "lodash", "4.17.21", round(1.4 * MB))
    node_pkg(nm, "@tablekit/core", "4.2.0", round(0.6 * MB), "AGPL-3.0-only OR LicenseRef-Commercial")
    node_pkg(nm, "chart-lite", "2.1.0", round(2.2 * MB))
    node_pkg(nm / "chart-lite" / "node_modules", "color-math", "1.0.3", round(0.3 * MB))
    return r


def piege_extra(base):
    r = base / "piege-extra-lourd"
    write(r / "LICENSE", MIT.format(holder="docsift authors"))
    write(r / "pyproject.toml", '[project]\nname = "docsift"\nversion = "0.4.0"\nlicense = "MIT"\n'
          'dependencies = ["requests>=2.31", "pypdf>=4.0"]\n\n[project.optional-dependencies]\n'
          'ocr = ["torch>=2.3", "transformers>=4.40", "pillow>=10"]\n'
          'all = ["docsift[ocr]", "pandas>=2.2", "openpyxl>=3.1"]\n')
    write(r / "README.md", "# docsift\n\nA light PDF text extractor: 2 dependencies.\n\n"
          "`pip install docsift`, or `pip install docsift[all]` for OCR and tables.\n")
    write(r / "docsift" / "extract.py",
          "from pypdf import PdfReader\n\n\nclass Extractor:\n"
          "    def __init__(self, use_ocr: bool = False):\n        self.use_ocr = use_ocr\n\n"
          "    def run(self, path):\n"
          '        text = "".join(p.extract_text() or "" for p in PdfReader(path).pages)\n'
          "        if self.use_ocr:\n            from transformers import AutoModel\n"
          '            model = AutoModel.from_pretrained("docsift/ocr-small")\n'
          "            text += model.config.name_or_path\n"
          "        return text\n")
    return r


def propre_mit(base):
    r = base / "propre-mit"
    write(r / "LICENSE", MIT.format(holder="mini-slug authors"))
    write(r / "package.json", json.dumps({"name": "mini-slug", "version": "1.3.0", "license": "MIT"}, indent=2) + "\n")
    write(r / "README.md", "# mini-slug\n\nTurn titles into URL slugs. Works with text pasted from proprietary "
          "editors.\n")
    write(r / "src" / "index.js",
          "// Handles proprietary formats too: smart quotes pasted from word processors.\n"
          "const NOTE = 'Works with proprietary editors';\n\n"
          "module.exports = function slug(title) {\n"
          "  return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');\n};\n"
          "module.exports.NOTE = NOTE;\n")
    return r


def propre_apache(base):
    r = base / "propre-apache"
    write(r / "LICENSE", APACHE)
    write(r / "NOTICE", "geo-tiles\nCopyright 2026 The geo-tiles authors\n\nThis product includes software "
          "developed by the geo-tiles authors.\n")
    write(r / "pyproject.toml", '[project]\nname = "geo-tiles"\nversion = "2.0.1"\nlicense = "Apache-2.0"\n'
          'dependencies = ["mercantile>=1.2"]\n')
    write(r / "README.md", "# geo-tiles\n\nSlice maps into tiles. Apache-2.0.\n")
    for mod in ("tiles", "bbox", "cli"):
        write(r / "geo_tiles" / f"{mod}.py", f"# SPDX-License-Identifier: Apache-2.0\n\"\"\"{mod} helpers.\"\"\"\n\n\n"
              f"def {mod}_version():\n    return \"2.0.1\"\n")
    write(r / "docs" / "usage.md", "# Usage\n\nPretrained tile classifiers live on https://huggingface.co/geo-tiles "
          "(optional, not installed).\n")
    write(r / "tests" / "test_models.py",
          "from transformers import AutoModel\n\n\ndef test_optional_classifier():\n"
          '    # https://huggingface.co/geo-tiles/demo, never run in CI\n'
          '    AutoModel.from_pretrained("geo-tiles/demo")\n')
    return r


def propre_bsd(base):
    r = base / "propre-bsd"
    write(r / "LICENSE", BSD3.format(holder="csvtool authors"))
    write(r / "setup.cfg", "[metadata]\nname = csvtool\nversion = 2.1.0\nlicense = BSD-3-Clause\n\n"
          "[options]\ninstall_requires =\n    click>=8\n")
    write(r / "CHANGELOG.md", "# Changelog\n\n## 2.0.0\n\n- Relicensed from GPL-3.0 to BSD-3-Clause.\n"
          "- Removed the proprietary XLS reader.\n- Removed the update check: no more calls to "
          "pypi.org/pypi/csvtool/json.\n")
    write(r / "README.md", "# csvtool\n\nSort, filter and join CSV files from the command line.\n")
    write(r / "csvtool" / "cli.py",
          '"""csvtool command line.\n\nVersion 1.x called check_for_updates() at start; removed in 2.0.\n"""\n'
          "import csv\nimport sys\n\n# No telemetry, no update check: this tool never calls the network.\n\n\n"
          "def main():\n    rows = list(csv.reader(sys.stdin))\n    csv.writer(sys.stdout).writerows(sorted(rows))\n")
    return r


def controle_busl(base):
    r = base / "controle-busl"
    write(r / "LICENSE", BUSL)
    write(r / "pyproject.toml", '[project]\nname = "queueforge"\nversion = "3.2.0"\nlicense = "BUSL-1.1"\n'
          'dependencies = ["redis>=5"]\n')
    write(r / "README.md", "# Queueforge\n\nA job queue for Python services.\n")
    write(r / "queueforge" / "server.py", "import redis\n\n\ndef connect(url):\n    return redis.Redis.from_url(url)\n")
    return r


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    d1 = darius_1(OUT)
    env1 = {"env": "darius-1-markitdown/envs/markitdown-all", "baseline": "darius-1-markitdown/envs/temoin"}
    darius_2(OUT), darius_3(OUT), piege_double(OUT), piege_extra(OUT)
    propre_mit(OUT), propre_apache(OUT), propre_bsd(OUT), controle_busl(OUT)
    ok_all = {u: "OK" for u in ("perso", "interne", "saas", "redistribution")}
    expected = [
        {"case": "darius-1-markitdown/repo", "kind": "réel", **env1, "verdicts": ok_all,
         "first_launch": 0, "dormant": 0, "carve_outs": 0, "label": "MIT", "packages": 56, "size": "319,7 Mo"},
        {"case": "darius-2-open-webui", "kind": "réel", "label": "BSD-3-Clause",
         "verdicts": {u: "ATTENTION" for u in ok_all}, "first_launch": 2, "dormant": 1, "carve_outs": 0,
         "first_categories": ["modele", "modele"], "dormant_categories": ["telemetrie"],
         "switches": ["HF_HUB_OFFLINE", "OFFLINE_MODE"], "promise_broken": True},
        {"case": "darius-3-stirling-pdf", "kind": "réel", "label": "MIT avec découpage (6 répertoires, 2 non libres)",
         "verdicts": {"perso": "OK", "interne": "ATTENTION", "saas": "ATTENTION", "redistribution": "ATTENTION"},
         "first_launch": 0, "dormant": 2, "dormant_categories": ["licence", "licence"], "dormant_host": "api.keygen.sh",
         "carve_outs": 6, "nonfree": 2, "spdx_global": "NOASSERTION", "promise_broken": False},
        {"case": "piege-double-licence", "kind": "piège", "label": "AGPL-3.0 ou commerciale", "dual": True,
         "env": "piege-double-licence/node_modules", "packages": 4, "size": "4,5 Mo",
         "verdicts": {"perso": "OK", "interne": "OK", "saas": "ATTENTION", "redistribution": "ATTENTION"},
         "first_launch": 0, "dormant": 0, "carve_outs": 0},
        {"case": "piege-extra-lourd", "kind": "piège", "label": "MIT", "verdicts": ok_all, "first_launch": 0,
         "dormant": 1, "dormant_categories": ["modele"], "carve_outs": 0, "base": ["pypdf", "requests"],
         "heavy_extras": {"ocr": ["torch", "transformers"], "all": ["pandas", "torch", "transformers"]}},
        {"case": "propre-mit", "kind": "propre", "label": "MIT", "verdicts": ok_all, "first_launch": 0, "dormant": 0,
         "carve_outs": 0},
        {"case": "propre-apache", "kind": "propre", "label": "Apache-2.0", "verdicts": ok_all, "first_launch": 0,
         "dormant": 0, "carve_outs": 0, "notices": ["NOTICE"], "spdx_headers": {"Apache-2.0": 3}},
        {"case": "propre-bsd", "kind": "propre", "label": "BSD-3-Clause", "verdicts": ok_all, "first_launch": 0,
         "dormant": 0, "carve_outs": 0},
        {"case": "controle-busl", "kind": "contrôle", "label": "BUSL-1.1",
         "verdicts": {"perso": "OK", "interne": "STOP", "saas": "STOP", "redistribution": "STOP"},
         "first_launch": 0, "dormant": 0, "carve_outs": 0},
    ]
    write(OUT / "expected.json", json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
    print(f"cases written to {OUT} ({len(expected)} repos, 4 simulated Python environments, "
          f"{d1.name} included)")


if __name__ == "__main__":
    main()
