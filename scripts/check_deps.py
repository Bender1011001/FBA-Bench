try:
    import fastapi
    print("fastapi:", fastapi.__version__)
except ImportError as e:
    print("fastapi MISSING:", e)
try:
    import uvicorn
    print("uvicorn OK")
except ImportError as e:
    print("uvicorn MISSING:", e)
try:
    import websockets
    print("websockets OK")
except ImportError as e:
    print("websockets MISSING:", e)
try:
    import starlette
    print("starlette OK")
except ImportError as e:
    print("starlette MISSING:", e)
