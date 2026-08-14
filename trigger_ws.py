import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Listening for messages for 5 seconds...")
            for _ in range(20):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"Received: hw_connected={data.get('hardware_connected')} movement={data.get('movement')} HR={data.get('heartRate')} BR={data.get('breathingRate')}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for message...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(test_ws())
