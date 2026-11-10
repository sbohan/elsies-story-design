"""Build index.html from src/index.src.html, inlining the brand fonts as data URIs.

Paperink and Lazy Dog are licensed display fonts taken from elsiesstory.org; they are
inlined so the page renders correctly wherever it's hosted.
"""
import base64, pathlib
root = pathlib.Path(__file__).parent
fonts = [("Paperink", "Paperink-Regular.woff2"), ("Lazy Dog", "LazydogRegular.woff2")]
css = "".join(
    '@font-face { font-family: "%s"; src: url(data:font/woff2;base64,%s) format("woff2"); font-weight: 400; font-style: normal; font-display: swap; }\n'
    % (name, base64.b64encode((root / "assets/fonts" / f).read_bytes()).decode())
    for name, f in fonts
)
src = (root / "src/index.src.html").read_text()
assert "/*@FONTS@*/" in src
(root / "index.html").write_text(src.replace("/*@FONTS@*/", css))
print("built index.html", (root / "index.html").stat().st_size, "bytes")
