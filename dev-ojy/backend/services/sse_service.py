from sse_starlette.sse import EventSourceResponse
import asyncio

hospital_connections = {}
amb_connections = {}
#sse send
async def send_hospital_sse(hospitalid: int, event: str ,data: str):
    queue = hospital_connections.get(hospitalid)

    if queue:
        await queue.put({
            "event": event,
            "data": data
        })

async def execute_hospital_sse(hospital):
    hospitalid = hospital["hospitalid"]

    queue = asyncio.Queue()

    hospital_connections[hospitalid] = queue

    async def event_generator():
        try:
            while True:
                msg = await queue.get()

                yield{
                    "event": msg["event"],
                    "data": msg["data"] 
                }
        except asyncio.CancelledError:
            hospital_connections.pop(hospitalid,None)
    
    return EventSourceResponse(event_generator())

#sse send
async def send_amb_sse(ambid: int, event: str, data: str):
    queue = amb_connections.get(ambid)

    if queue:
        await queue.put({
            "event": event,
            "data": data
        })

async def execute_amb_sse(amb):
    ambid = amb["ambid"]

    queue = asyncio.Queue()

    amb_connections[ambid] = queue

    async def event_generator():
        try:
            while True:
                msg = await queue.get()

                yield{
                    "event": msg["event"],
                    "data": msg["data"] 
                }
        except asyncio.CancelledError:
            amb_connections.pop(ambid,None)
    
    return EventSourceResponse(event_generator())

