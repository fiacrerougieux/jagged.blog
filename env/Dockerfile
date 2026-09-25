# Jagged duel runner.
#
# Contains the `pi` agent harness plus every renderer a case might need, so a
# run is reproducible months after the post goes up. The agent gets bash inside
# here and nowhere else.
FROM node:24-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Renderers. Kept to apt packages so the image builds without a toolchain:
#   imagemagick   -> PPM, PNM, generic raster conversion
#   librsvg2-bin  -> rsvg-convert, for every SVG case
#   graphviz      -> dot, for the DOT cases
#   fonts-dejavu  -> so text in SVG/DOT output actually renders
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      imagemagick \
      librsvg2-bin \
      graphviz \
      fonts-dejavu-core \
      python3 \
      python3-pip \
      python3-venv \
      git \
    && rm -rf /var/lib/apt/lists/*

# ImageMagick's Debian policy blocks reading/writing several formats by default.
# We only ever convert model output in a throwaway container, so allow them.
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
      sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml; \
    fi

# Python checkers. rdkit for the SMILES cases, biopython for Newick,
# matplotlib for the GPX/plot cases.
RUN python3 -m venv /opt/checkenv \
    && /opt/checkenv/bin/pip install --no-cache-dir \
       rdkit biopython matplotlib numpy
ENV CHECK_PY=/opt/checkenv/bin/python3

# The agent harness. Pinned: a run months from now must reproduce, and 0.85.1
# in particular sends a mid-conversation reasoning-effort update that several
# providers reject with a 400 (anthropic/claude-opus-5 among them).
ARG PI_VERSION=0.83.0
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@${PI_VERSION}

# Non-root. The run directory is bind-mounted at /work and must be writable by
# this uid, which run.mjs arranges by passing --user.
RUN useradd -m -u 1001 duel || true
WORKDIR /work

ENV PATH=/work/bin:$PATH
ENV PI_OFFLINE=1

# ── Renderers for the rest of the prompt pack ───────────────────────────────
# Appended after the original layers so their cache survives. Every case's
# render command runs one of these; the scripts that drive them live in
# renderers/ and are mounted read-only at /renderers, like the checkers.

#   chromium      -> HTML/CSS, Mermaid, Vega-Lite, ECharts, WaveDrom, Lottie,
#                    GLSL (WebGL on SwiftShader) and 3Dmol, all via puppeteer
#   openscad+xvfb -> CAD cases; OpenSCAD needs a GL context even for PNG export
#   ngspice, plantuml, lilypond, abcm2ps, ffmpeg (libass for ASS subtitles)
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium fonts-liberation fonts-noto-color-emoji \
      xvfb xauth libgl1-mesa-dri \
      openscad ngspice plantuml lilypond abcm2ps ffmpeg \
      poppler-utils curl xz-utils \
      build-essential pkg-config libcairo2-dev libpango1.0-dev \
    && rm -rf /var/lib/apt/lists/*

# LaTeX: standalone class (latex-extra), TikZ and PGFPlots (pictures).
RUN apt-get update && apt-get install -y --no-install-recommends \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra \
      texlive-pictures texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

# Blender, rendered with Cycles on the CPU: there is no GPU in here.
RUN apt-get update && apt-get install -y --no-install-recommends blender \
    && rm -rf /var/lib/apt/lists/*

# Python side: Manim, pvlib (+ solarfactors for bifacial), fontTools and
# HarfBuzz for the type cases, shapely for geometry checks.
# pycairo (for Manim) builds from source and needs the Python headers.
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && /opt/checkenv/bin/pip install --no-cache-dir \
      manim pvlib solarfactors fonttools uharfbuzz pillow scipy shapely pandas

# Browser libraries, pinned in renderers/package.json.
COPY renderers/package.json /opt/render/package.json
RUN cd /opt/render && npm install --omit=dev --ignore-scripts --no-audit --no-fund
ENV RENDER_NODE_PATH=/opt/render/node_modules
ENV CHROME_PATH=/usr/bin/chromium

# Single-binary tools.
ARG TYPST_VERSION=0.15.1
ARG D2_VERSION=0.7.0
RUN ARCH=$(uname -m) \
    && curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-${ARCH}-unknown-linux-musl.tar.xz" \
       | tar -xJ -C /tmp && mv /tmp/typst-*/typst /usr/local/bin/typst \
    && D2ARCH=$([ "$ARCH" = aarch64 ] && echo arm64 || echo amd64) \
    && curl -fsSL "https://github.com/terrastruct/d2/releases/download/v${D2_VERSION}/d2-v${D2_VERSION}-linux-${D2ARCH}.tar.gz" \
       | tar -xz -C /tmp && mv /tmp/d2-v${D2_VERSION}/bin/d2 /usr/local/bin/d2 \
    && rm -rf /tmp/typst-* /tmp/d2-*

# Optional, heavy or fragile. A failure here leaves the tool missing and the
# case's render prints that plainly; it does not break the image.
#   KiCad 7+ for kicad-cli (bookworm itself ships 6, which has no CLI)
RUN (echo "deb http://deb.debian.org/debian bookworm-backports main" > /etc/apt/sources.list.d/backports.list \
     && apt-get update && apt-get install -y --no-install-recommends -t bookworm-backports kicad \
     && rm -rf /var/lib/apt/lists/*) || echo "OPTIONAL: kicad not installed"
#   OpenModelica compiler
RUN (apt-get update && apt-get install -y --no-install-recommends gnupg \
     && curl -fsSL https://build.openmodelica.org/apt/openmodelica.asc | gpg --dearmor -o /usr/share/keyrings/openmodelica.gpg \
     && echo "deb [signed-by=/usr/share/keyrings/openmodelica.gpg] https://build.openmodelica.org/apt bookworm stable" > /etc/apt/sources.list.d/openmodelica.list \
     && apt-get update && apt-get install -y --no-install-recommends omc \
     && rm -rf /var/lib/apt/lists/*) || echo "OPTIONAL: openmodelica not installed"
#   Lean 4 with a prebuilt Mathlib, so a proof checks in seconds, not an hour
RUN (curl -fsSL https://raw.githubusercontent.com/leanprover/elan/v4.2.4/elan-init.sh | sh -s -- -y --no-modify-path --default-toolchain none \
     && export ELAN_HOME=/root/.elan PATH=/root/.elan/bin:$PATH \
     && mkdir -p /opt/lean && cd /opt/lean \
     && lake +leanprover-community/mathlib4:lean-toolchain new proof math \
     && cd proof && lake exe cache get \
     && mv /root/.elan /opt/elan && chmod -R a+rX /opt/elan /opt/lean) || echo "OPTIONAL: lean not installed"
ENV ELAN_HOME=/opt/elan
ENV PATH=/work/bin:/opt/elan/bin:$PATH
# Runs use the host uid, not root. Without this git calls the Mathlib checkout
# "dubious ownership", Lake decides the dependency changed and tries to
# re-clone it into a read-only directory. The search path is also resolved
# once here so a check never needs Lake at all.
RUN git config --system --add safe.directory '*' \
    && (cd /opt/lean/proof 2>/dev/null && lake env printenv LEAN_PATH > /opt/lean/leanpath) || true

# Blog export only: audio for the two score cases, STL to GLB so a model can
# be turned in the browser, and spicelib so a SPICE netlist can be drawn as a
# schematic. Nothing a run depends on.
RUN apt-get update && apt-get install -y --no-install-recommends abcmidi fluidsynth fluid-soundfont-gm \
    && rm -rf /var/lib/apt/lists/* \
    && /opt/checkenv/bin/pip install --no-cache-dir trimesh spicelib==1.6.3

# Text shaping. hb-shape and fribidi so the shaper and the bidi algorithm can
# be driven from a shell as well as from Python; python-bidi is the UBA
# implementation itself.
#
# The Arabic face is pinned to one release and unpacked by hand instead of
# taken from apt. The bilingual sign case is graded by comparing the model's
# diagnostic table against the glyph names and clusters HarfBuzz actually
# produces, and a font substitution renames the glyphs — a right answer would
# then read as a wrong one. The checksum is of the font, not the archive.
ARG NASKH_VERSION=2.019
ARG NASKH_SHA256=2d5d78e9cc27d7193926c7e460314c9da7dbec1268494dbf117adc53c171ac06
RUN apt-get update && apt-get install -y --no-install-recommends \
      libharfbuzz-bin libfribidi-bin \
    && rm -rf /var/lib/apt/lists/* \
    && /opt/checkenv/bin/pip install --no-cache-dir python-bidi==0.6.6 \
    && mkdir -p /usr/share/fonts/truetype/noto-pinned \
    && curl -fsSL -o /tmp/naskh.zip \
       "https://github.com/notofonts/arabic/releases/download/NotoNaskhArabic-v${NASKH_VERSION}/NotoNaskhArabic-v${NASKH_VERSION}.zip" \
    && /opt/checkenv/bin/python3 -c "import shutil, zipfile; z = zipfile.ZipFile('/tmp/naskh.zip'); src = z.open('NotoNaskhArabic/hinted/ttf/NotoNaskhArabic-Regular.ttf'); dst = open('/usr/share/fonts/truetype/noto-pinned/NotoNaskhArabic-Regular.ttf', 'wb'); shutil.copyfileobj(src, dst)" \
    && echo "${NASKH_SHA256}  /usr/share/fonts/truetype/noto-pinned/NotoNaskhArabic-Regular.ttf" | sha256sum -c - \
    && rm -f /tmp/naskh.zip && fc-cache -f > /dev/null
ENV NASKH_FONT=/usr/share/fonts/truetype/noto-pinned/NotoNaskhArabic-Regular.ttf

# Rigid-body physics. MuJoCo renders off-screen through OSMesa: there is no GPU
# in here, and the software rasteriser is the only context that exists. Set on
# the image rather than in the case's render command so a model's own script
# works unchanged.
RUN apt-get update && apt-get install -y --no-install-recommends libosmesa6 \
    && rm -rf /var/lib/apt/lists/* \
    && /opt/checkenv/bin/pip install --no-cache-dir mujoco==3.13.0
ENV MUJOCO_GL=osmesa

CMD ["pi", "--version"]
