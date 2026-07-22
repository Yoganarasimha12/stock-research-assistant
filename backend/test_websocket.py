import asyncio
import websockets
import json

async def test():
    url = "ws://localhost:8000/companies/AAPL/ws"
    print(f"Connecting to {url}...\n")

    async with websockets.connect(url) as ws:

        # Question 1
        print("=== Question 1 ===")
        await ws.send(json.dumps({"question": "What are Apple main risks?"}))

        full_answer = ""
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "sources":
                print(f"[{len(msg['sources'])} sources retrieved]")
            elif msg["type"] == "token":
                print(msg["token"], end="", flush=True)
                full_answer += msg["token"]
            elif msg["type"] == "done":
                print("\n")
                break
            elif msg["type"] == "error":
                print(f"ERROR: {msg['message']}")
                return

        # Question 2 — follow-up that references Q1
        print("=== Question 2 (follow-up) ===")
        await ws.send(json.dumps({
            "question": "Tell me more about the geopolitical risks you mentioned"
        }))

        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "sources":
                print(f"[{len(msg['sources'])} sources retrieved]")
            elif msg["type"] == "token":
                print(msg["token"], end="", flush=True)
            elif msg["type"] == "done":
                print("\n")
                break

        # Question 3 — another follow-up
        print("=== Question 3 (follow-up) ===")
        await ws.send(json.dumps({
            "question": "Which of those risks is most likely to affect revenue?"
        }))

        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "sources":
                print(f"[{len(msg['sources'])} sources retrieved]")
            elif msg["type"] == "token":
                print(msg["token"], end="", flush=True)
            elif msg["type"] == "done":
                print("\n")
                break

asyncio.run(test())