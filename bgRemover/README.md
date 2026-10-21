# bgRemover

A small Flask web app that removes the background from an uploaded image using
[rembg](https://github.com/danielgatis/rembg). The result is returned as a
transparent PNG download.

Based on the [original tutorial](https://youtu.be/cw34KMPSt4k) by
[rembg's author](https://github.com/danielgatis).

## Run it

```bash
cd bgRemover
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5100>, choose an image, and download the result.
On the first run rembg downloads the `u2net` model (~170 MB) and caches it in
your home directory; later runs start instantly.

## Docker

The included `Dockerfile` expects the model to be present locally so the image
does not download it at runtime:

```bash
# download https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
docker build -t bgremover .
docker run -p 5100:5100 bgremover
```

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Flask routes: upload form and PNG response |
| `basic.py` | Minimal script version of the removal step |
| `templates/index.html` | Upload page |
| `requirements.txt` | Flask, rembg, Pillow |
| `Dockerfile` | Container image with a pre-baked model |
