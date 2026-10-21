# Custom Tools

A small collection of focused utilities. Every tool lives in its own folder,
has its own README, and can be used on its own — nothing here shares a runtime
or a dependency set.

## Tools

| Tool | Platform | What it does | Docs |
| --- | --- | --- | --- |
| **bgRemover** | Web (Flask) | Upload an image and get it back with the background removed, powered by [rembg](https://github.com/danielgatis/rembg). | [`bgRemover/README.md`](bgRemover/README.md) |
| **opacityControl** | Windows desktop | Make a chosen application window transparent while keeping it fully interactive, and lock it in place when it is positioned. | [`opacityControl/README.md`](opacityControl/README.md) |

## Repository layout

```
customTools/
├── bgRemover/          Flask background-removal web app
│   ├── app.py
│   ├── templates/
│   └── ...
├── opacityControl/     Windows transparency utility
│   ├── main.py
│   ├── opacity_control/    core, UI and Windows backend
│   ├── tests/
│   ├── PRD.md
│   └── AGENTS.md
├── LICENSE             MIT
└── README.md
```

## Quick start

Each tool documents its own setup. In short:

**bgRemover**

```bash
cd bgRemover
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5100>. The first run downloads the `u2net` model;
see [`bgRemover/README.md`](bgRemover/README.md) for details.

**opacityControl**

```powershell
cd opacityControl
python main.py
```

Windows 10/11, Python 3.10+, no third-party packages. Pick a window, set the
opacity, lock it in place, and press `Ctrl+Alt+Esc` (or the panel's
**Restore & Exit Mode** button) to restore it.

## Development

Tests are per tool and need no third-party packages:

```powershell
cd opacityControl
python -m unittest discover -s tests -v
```

`opacityControl/AGENTS.md` documents the conventions for that tool.

## Adding a new tool

1. Create a folder named after the tool.
2. Add a `README.md` covering what it does, requirements, and how to run it.
3. Keep its dependencies isolated (its own `requirements.txt` / project file).
4. Add a row to the tool table above.

## License

Released under the MIT License. See [`LICENSE`](LICENSE).
