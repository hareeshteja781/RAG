# Enterprise RAG Frontend v2

This is a redesigned plain HTML/CSS/JavaScript frontend for the Enterprise RAG application.

## Run locally

From this folder:

```powershell
python -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500
```

The frontend expects the FastAPI backend at:

```text
http://127.0.0.1:8000/
```

You can override it before loading the page with `window.API_BASE` if needed.
