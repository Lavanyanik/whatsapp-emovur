import asyncio
import json
import sys
from pathlib import Path
# Ensure project root is on sys.path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from httpx import AsyncClient
from app.main import app

async def main():
    async with AsyncClient(app=app, base_url='http://test') as ac:
        resp = await ac.post('/messages', json={
            'to': '+919876543212',
            'type': 'text',
            'text': {'body': 'Hello from inproc test'}
        }, timeout=20)
        print('status', resp.status_code)
        try:
            print('body', resp.json())
        except Exception:
            print('text', resp.text)

if __name__ == '__main__':
    asyncio.run(main())
