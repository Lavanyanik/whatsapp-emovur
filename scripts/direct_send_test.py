import asyncio
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.routers.whatsapp import send_message_route
from app.schemas import MessageRequest

async def main():
    payload = MessageRequest(
        to='+919999999996',
        type='text',
        text={'body': 'Hello from direct_send_test'},
    )
    result = await send_message_route(payload)
    print('RESULT', result)

if __name__ == '__main__':
    asyncio.run(main())
