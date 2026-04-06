<<<<<<< HEAD
import os
import json
import wave
import base64
import sqlite3
import urllib.parse
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

BASE        = os.path.dirname(os.path.abspath(__file__))
PASTA_AUDIO = os.path.join(BASE, "Audio")
PASTA_TG    = os.path.join(BASE, "TextGrid")
PASTA_EMU   = os.path.join(BASE, "emu_final")
PASTA_SSFF  = os.path.join(BASE, "emuDB", "kawahiva_emuDB", "0000_ses")
BANCO_DADOS = os.path.join(BASE, "corpus.db")

app.mount("/EMU-webApp", StaticFiles(directory=PASTA_EMU, html=True), name="emu")


def ok(callback_id: str, data, tipo: str = "") -> dict:
    """Monta resposta no formato exato que o EMU espera."""
    r = {"callbackID": callback_id, "status": {"type": "SUCCESS", "message": ""}, "data": data}
    if tipo:
        r["type"] = tipo
    return r


def ler_annot_json(nome: str) -> dict | None:
    c = os.path.join(PASTA_SSFF, f"{nome}_bndl", f"{nome}_annot.json")
    if os.path.exists(c):
        with open(c, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def ler_wav_info(nome: str) -> tuple:
    for ext in ["wav", "WAV"]:
        c = os.path.join(PASTA_AUDIO, f"{nome}.{ext}")
        if os.path.exists(c):
            try:
                with wave.open(c, "rb") as w:
                    return w.getframerate(), w.getnframes()
            except: pass
    return 44100, 0


def ler_ssff_base64(nome: str) -> list:
    ssff = []
    for ext in ["fms", "f0", "rms"]:
        c = os.path.join(PASTA_SSFF, f"{nome}_bndl", f"{nome}.{ext}")
        if os.path.exists(c) and os.path.getsize(c) > 50:
            with open(c, "rb") as f:
                ssff.append({
                    "encoding": "BASE64",
                    "data": base64.b64encode(f.read()).decode("ascii"),
                    "fileExtension": ext
                })
    return ssff


def db_config() -> dict:
    return {
        "name": "Kawahiva", "UUID": "kawahiva-corpus-2026",
        "mediafileExtension": "wav",
        "ssffTrackDefinitions": [
            {"name": "FORMANTS", "columnName": "fm",  "fileExtension": "fms"},
            {"name": "PITCH",    "columnName": "F0",  "fileExtension": "f0"},
            {"name": "RMS",      "columnName": "rms", "fileExtension": "rms"}
        ],
        "levelDefinitions": [
            {"name": "words",  "type": "SEGMENT",
             "attributeDefinitions": [{"name": "words",  "type": "STRING"}]},
            {"name": "phones", "type": "SEGMENT",
             "attributeDefinitions": [{"name": "phones", "type": "STRING"}]}
        ],
        "linkDefinitions": [],
        "EMUwebAppConfig": {
            "perspectives": [
                {
                    "name": "Espectrograma",
                    "signalCanvases": {"order": ["OSCI", "SPEC"], "assign": [], "contourLims": []},
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Formantes",
                    "signalCanvases": {
                        "order": ["OSCI", "SPEC"],
                        "assign": [{"signalCanvasName": "SPEC", "ssffTrackName": "FORMANTS"}],
                        "contourLims": [{"ssffTrackName": "FORMANTS", "minContourIdx": 0, "maxContourIdx": 3}]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Pitch",
                    "signalCanvases": {
                        "order": ["OSCI", "PITCH"],
                        "assign": [],
                        "contourLims": [{"ssffTrackName": "PITCH", "minContourIdx": 0, "maxContourIdx": 0}]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Completo",
                    "signalCanvases": {
                        "order": ["OSCI", "SPEC", "PITCH", "RMS"],
                        "assign": [{"signalCanvasName": "SPEC", "ssffTrackName": "FORMANTS"}],
                        "contourLims": [
                            {"ssffTrackName": "FORMANTS", "minContourIdx": 0, "maxContourIdx": 3},
                            {"ssffTrackName": "PITCH",    "minContourIdx": 0, "maxContourIdx": 0}
                        ]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                }
            ],
            "restrictions": {
                "showPerspectivesSidebar": True,
                "editItemSize": True, "editItemName": True,
                "deleteItemBoundary": True, "deleteItem": True,
                "deleteLevel": False, "addItem": True
            },
            "activeButtons": {
                "specSettings": True, "search": True,
                "connect": False, "openMenu": False,
                "downloadTextGrid": False, "downloadAnnotation": False,
                "saveBundle": False, "openDemoDB": False,
                "resizeSingleLevel": True, "resizePerspectives": True
            }
        }
    }


# ── HTTP ──────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/arquivos")
def listar():
    if not os.path.exists(BANCO_DADOS): return []
    conn = sqlite3.connect(BANCO_DADOS)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM corpus ORDER BY vernacula")
    linhas = cursor.fetchall()
    conn.close()
    return [dict(l) for l in linhas]

@app.get("/audio/{n}")
def audio(n: str, request: Request):
    nome = urllib.parse.unquote(n)
    caminho = os.path.join(PASTA_AUDIO, f"{nome}.wav")
    if not os.path.exists(caminho):
        caminho = os.path.join(PASTA_AUDIO, f"{nome}.WAV")
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404)
    tamanho = os.path.getsize(caminho)
    rh = request.headers.get("range")
    hdrs = {"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}
    if rh:
        try:
            i_s, f_s = rh.strip().replace("bytes=", "").split("-")
            ini = int(i_s); fim = int(f_s) if f_s else tamanho - 1
        except: raise HTTPException(status_code=416)
        ck = fim - ini + 1
        def gen():
            with open(caminho, "rb") as f:
                f.seek(ini)
                rem = ck
                while rem > 0:
                    b = f.read(min(65536, rem))
                    if not b: break
                    rem -= len(b); yield b
        hdrs.update({"Content-Range": f"bytes {ini}-{fim}/{tamanho}", "Content-Length": str(ck)})
        return StreamingResponse(gen(), status_code=206, media_type="audio/wav", headers=hdrs)
    hdrs["Content-Length"] = str(tamanho)
    return FileResponse(caminho, media_type="audio/wav", headers=hdrs)

@app.get("/textgrid/{n}")
def tg(n: str):
    nome = urllib.parse.unquote(n)
    c = os.path.join(PASTA_TG, f"{nome}.TextGrid")
    if not os.path.exists(c): raise HTTPException(status_code=404)
    return FileResponse(c, media_type="text/plain; charset=utf-8")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/emu_ws/{bundle_name}")
async def emu_ws(websocket: WebSocket, bundle_name: str):
    await websocket.accept()
    nome     = urllib.parse.unquote(bundle_name)
    base_url = str(websocket.url).replace("ws://", "http://").replace("wss://", "https://")
    base_url = base_url.split("/emu_ws/")[0]
    print(f"🔌 WS: {nome}")

    try:
        while True:
            raw  = await websocket.receive_text()
            msg  = json.loads(raw)
            tipo = msg.get("type", "")
            cid  = msg.get("callbackID", "")

            print(f"  → {tipo} (cid={cid[:8] if cid else '?'})")

            if tipo == "GETPROTOCOL":
                await websocket.send_text(json.dumps(ok(cid, {
                    "protocol": "EMU-webApp-websocket-protocol",
                    "version":  "0.0.2"
                })))

            elif tipo == "GETDOUSERMANAGEMENT":
                await websocket.send_text(json.dumps(ok(cid, "NO")))

            elif tipo == "GETGLOBALDBCONFIG":
                await websocket.send_text(json.dumps(ok(cid, db_config())))

            elif tipo == "GETBUNDLELIST":
                await websocket.send_text(json.dumps(ok(cid,
                    [{"name": nome, "session": "0000"}]
                )))

            elif tipo == "GETBUNDLE":
                sr, _ = ler_wav_info(nome)
                annot = ler_annot_json(nome) or {
                    "name": nome, "annotates": f"{nome}.wav",
                    "sampleRate": sr, "levels": [], "links": []
                }
                ssff = ler_ssff_base64(nome)
                print(f"  📦 {len(annot.get('levels',[]))} níveis | SSFF: {[s['fileExtension'] for s in ssff]}")

                await websocket.send_text(json.dumps(ok(cid, {
                    "mediaFile": {
                        "encoding": "GETURL",
                        "data": f"{base_url}/audio/{urllib.parse.quote(nome)}"
                    },
                    "annotation": annot,
                    "ssffFiles":  ssff
                }, tipo)))

            elif tipo == "DISCONNECTWARNING":
                await websocket.send_text(json.dumps(ok(cid, "BYE!")))
                break

            else:
                print(f"  ⚠️  tipo desconhecido: {tipo}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ WS erro: {e}")
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    porta = int(os.environ.get("PORT", 8000))
    print(f"🚀 Servidor Kawahiva iniciado na porta {porta}")
    uvicorn.run(app, host="0.0.0.0", port=porta)
=======
import os
import json
import wave
import base64
import sqlite3
import urllib.parse
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

BASE        = os.path.dirname(os.path.abspath(__file__))
PASTA_AUDIO = os.path.join(BASE, "Audio")
PASTA_TG    = os.path.join(BASE, "TextGrid")
PASTA_EMU   = os.path.join(BASE, "emu_final")
PASTA_SSFF  = os.path.join(BASE, "emuDB", "kawahiva_emuDB", "0000_ses")
BANCO_DADOS = os.path.join(BASE, "corpus.db")

app.mount("/EMU-webApp", StaticFiles(directory=PASTA_EMU, html=True), name="emu")


def ok(callback_id: str, data, tipo: str = "") -> dict:
    """Monta resposta no formato exato que o EMU espera."""
    r = {"callbackID": callback_id, "status": {"type": "SUCCESS", "message": ""}, "data": data}
    if tipo:
        r["type"] = tipo
    return r


def ler_annot_json(nome: str) -> dict | None:
    c = os.path.join(PASTA_SSFF, f"{nome}_bndl", f"{nome}_annot.json")
    if os.path.exists(c):
        with open(c, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def ler_wav_info(nome: str) -> tuple:
    for ext in ["wav", "WAV"]:
        c = os.path.join(PASTA_AUDIO, f"{nome}.{ext}")
        if os.path.exists(c):
            try:
                with wave.open(c, "rb") as w:
                    return w.getframerate(), w.getnframes()
            except: pass
    return 44100, 0


def ler_ssff_base64(nome: str) -> list:
    ssff = []
    for ext in ["fms", "f0", "rms"]:
        c = os.path.join(PASTA_SSFF, f"{nome}_bndl", f"{nome}.{ext}")
        if os.path.exists(c) and os.path.getsize(c) > 50:
            with open(c, "rb") as f:
                ssff.append({
                    "encoding": "BASE64",
                    "data": base64.b64encode(f.read()).decode("ascii"),
                    "fileExtension": ext
                })
    return ssff


def db_config() -> dict:
    return {
        "name": "Kawahiva", "UUID": "kawahiva-corpus-2026",
        "mediafileExtension": "wav",
        "ssffTrackDefinitions": [
            {"name": "FORMANTS", "columnName": "fm",  "fileExtension": "fms"},
            {"name": "PITCH",    "columnName": "F0",  "fileExtension": "f0"},
            {"name": "RMS",      "columnName": "rms", "fileExtension": "rms"}
        ],
        "levelDefinitions": [
            {"name": "words",  "type": "SEGMENT",
             "attributeDefinitions": [{"name": "words",  "type": "STRING"}]},
            {"name": "phones", "type": "SEGMENT",
             "attributeDefinitions": [{"name": "phones", "type": "STRING"}]}
        ],
        "linkDefinitions": [],
        "EMUwebAppConfig": {
            "perspectives": [
                {
                    "name": "Espectrograma",
                    "signalCanvases": {"order": ["OSCI", "SPEC"], "assign": [], "contourLims": []},
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Formantes",
                    "signalCanvases": {
                        "order": ["OSCI", "SPEC"],
                        "assign": [{"signalCanvasName": "SPEC", "ssffTrackName": "FORMANTS"}],
                        "contourLims": [{"ssffTrackName": "FORMANTS", "minContourIdx": 0, "maxContourIdx": 3}]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Pitch",
                    "signalCanvases": {
                        "order": ["OSCI", "PITCH"],
                        "assign": [],
                        "contourLims": [{"ssffTrackName": "PITCH", "minContourIdx": 0, "maxContourIdx": 0}]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                },
                {
                    "name": "Completo",
                    "signalCanvases": {
                        "order": ["OSCI", "SPEC", "PITCH", "RMS"],
                        "assign": [{"signalCanvasName": "SPEC", "ssffTrackName": "FORMANTS"}],
                        "contourLims": [
                            {"ssffTrackName": "FORMANTS", "minContourIdx": 0, "maxContourIdx": 3},
                            {"ssffTrackName": "PITCH",    "minContourIdx": 0, "maxContourIdx": 0}
                        ]
                    },
                    "levelCanvases": {"order": ["words", "phones"]},
                    "twoDimCanvases": {"order": []}
                }
            ],
            "restrictions": {
                "showPerspectivesSidebar": True,
                "editItemSize": True, "editItemName": True,
                "deleteItemBoundary": True, "deleteItem": True,
                "deleteLevel": False, "addItem": True
            },
            "activeButtons": {
                "specSettings": True, "search": True,
                "connect": False, "openMenu": False,
                "downloadTextGrid": False, "downloadAnnotation": False,
                "saveBundle": False, "openDemoDB": False,
                "resizeSingleLevel": True, "resizePerspectives": True
            }
        }
    }


# ── HTTP ──────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))

@app.get("/arquivos")
def listar():
    if not os.path.exists(BANCO_DADOS): return []
    conn = sqlite3.connect(BANCO_DADOS)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM corpus ORDER BY vernacula")
    linhas = cursor.fetchall()
    conn.close()
    return [dict(l) for l in linhas]

@app.get("/audio/{n}")
def audio(n: str, request: Request):
    nome = urllib.parse.unquote(n)
    caminho = os.path.join(PASTA_AUDIO, f"{nome}.wav")
    if not os.path.exists(caminho):
        caminho = os.path.join(PASTA_AUDIO, f"{nome}.WAV")
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404)
    tamanho = os.path.getsize(caminho)
    rh = request.headers.get("range")
    hdrs = {"Access-Control-Allow-Origin": "*", "Accept-Ranges": "bytes"}
    if rh:
        try:
            i_s, f_s = rh.strip().replace("bytes=", "").split("-")
            ini = int(i_s); fim = int(f_s) if f_s else tamanho - 1
        except: raise HTTPException(status_code=416)
        ck = fim - ini + 1
        def gen():
            with open(caminho, "rb") as f:
                f.seek(ini)
                rem = ck
                while rem > 0:
                    b = f.read(min(65536, rem))
                    if not b: break
                    rem -= len(b); yield b
        hdrs.update({"Content-Range": f"bytes {ini}-{fim}/{tamanho}", "Content-Length": str(ck)})
        return StreamingResponse(gen(), status_code=206, media_type="audio/wav", headers=hdrs)
    hdrs["Content-Length"] = str(tamanho)
    return FileResponse(caminho, media_type="audio/wav", headers=hdrs)

@app.get("/textgrid/{n}")
def tg(n: str):
    nome = urllib.parse.unquote(n)
    c = os.path.join(PASTA_TG, f"{nome}.TextGrid")
    if not os.path.exists(c): raise HTTPException(status_code=404)
    return FileResponse(c, media_type="text/plain; charset=utf-8")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/emu_ws/{bundle_name}")
async def emu_ws(websocket: WebSocket, bundle_name: str):
    await websocket.accept()
    nome     = urllib.parse.unquote(bundle_name)
    base_url = str(websocket.url).replace("ws://", "http://").replace("wss://", "https://")
    base_url = base_url.split("/emu_ws/")[0]
    print(f"🔌 WS: {nome}")

    try:
        while True:
            raw  = await websocket.receive_text()
            msg  = json.loads(raw)
            tipo = msg.get("type", "")
            cid  = msg.get("callbackID", "")

            print(f"  → {tipo} (cid={cid[:8] if cid else '?'})")

            if tipo == "GETPROTOCOL":
                await websocket.send_text(json.dumps(ok(cid, {
                    "protocol": "EMU-webApp-websocket-protocol",
                    "version":  "0.0.2"
                })))

            elif tipo == "GETDOUSERMANAGEMENT":
                await websocket.send_text(json.dumps(ok(cid, "NO")))

            elif tipo == "GETGLOBALDBCONFIG":
                await websocket.send_text(json.dumps(ok(cid, db_config())))

            elif tipo == "GETBUNDLELIST":
                await websocket.send_text(json.dumps(ok(cid,
                    [{"name": nome, "session": "0000"}]
                )))

            elif tipo == "GETBUNDLE":
                sr, _ = ler_wav_info(nome)
                annot = ler_annot_json(nome) or {
                    "name": nome, "annotates": f"{nome}.wav",
                    "sampleRate": sr, "levels": [], "links": []
                }
                ssff = ler_ssff_base64(nome)
                print(f"  📦 {len(annot.get('levels',[]))} níveis | SSFF: {[s['fileExtension'] for s in ssff]}")

                await websocket.send_text(json.dumps(ok(cid, {
                    "mediaFile": {
                        "encoding": "GETURL",
                        "data": f"{base_url}/audio/{urllib.parse.quote(nome)}"
                    },
                    "annotation": annot,
                    "ssffFiles":  ssff
                }, tipo)))

            elif tipo == "DISCONNECTWARNING":
                await websocket.send_text(json.dumps(ok(cid, "BYE!")))
                break

            else:
                print(f"  ⚠️  tipo desconhecido: {tipo}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ WS erro: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    porta = int(os.environ.get("PORT", 8000))
    print(f"🚀 Servidor Kawahiva iniciado na porta {porta}")
    uvicorn.run(app, host="0.0.0.0", port=porta)
>>>>>>> 79c30e579f212599309cbfc8c9df2f170da1352d
