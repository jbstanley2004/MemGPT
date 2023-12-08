import asyncio
import json
import traceback

import websockets

from memgpt.server.server import SyncServer
from memgpt.server.websocket_interface import SyncWebSocketInterface
from memgpt.server.constants import DEFAULT_PORT
import memgpt.server.websocket_protocol as protocol
import memgpt.system as system
import memgpt.constants as memgpt_constants


class WebSocketServer:
    def __init__(self, host="localhost", port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.interface = SyncWebSocketInterface()
        self.server = SyncServer(default_interface=self.interface)

    def initialize_server(self):
        print("Server is initializing...")
        print(f"Listening on {self.host}:{self.port}...")

    async def start_server(self):
        self.initialize_server()
        # Can play with ping_interval and ping_timeout
        # See: https://websockets.readthedocs.io/en/stable/topics/timeouts.html
        # and https://github.com/cpacker/MemGPT/issues/471
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever

    def run(self):
        return self.start_server()  # Return the coroutine

    async def handle_client(self, websocket, path):
        self.interface.register_client(websocket)
        try:
            # async for message in websocket:
            while True:
                message = await websocket.recv()

                # Assuming the message is a JSON string
                try:
                    data = json.loads(message)
                except:
                    print(f"[server] bad data from client:\n{data}")
                    await websocket.send(protocol.server_command_response(f"Error: bad data from client - {str(data)}"))
                    continue

                if "type" not in data:
                    print(f"[server] bad data from client (JSON but no type):\n{data}")
                    await websocket.send(protocol.server_command_response(f"Error: bad data from client - {str(data)}"))

                elif data["type"] == "command":
                    # Create a new agent
                    if data["command"] == "create_agent":
                        try:
                            # self.agent = self.create_new_agent(data["config"])
                            self.server.create_agent(user_id="NULL", agent_config=data["config"])
                            await websocket.send(protocol.server_command_response("OK: Agent initialized"))
                        except Exception as e:
                            self.agent = None
                            print(f"[server] self.create_new_agent failed with:\n{e}")
                            print(f"{traceback.format_exc()}")
                            await websocket.send(protocol.server_command_response(f"Error: Failed to init agent - {str(e)}"))

                    else:
                        print(f"[server] unrecognized client command type: {data}")
                        await websocket.send(protocol.server_error(f"unrecognized client command type: {data}"))

                elif data["type"] == "user_message":
                    user_message = data["message"]

                    if "agent_id" not in data or data["agent_id"] is None:
                        await websocket.send(protocol.server_agent_response_error("agent_name was not specified in the request"))
                        continue

                    await websocket.send(protocol.server_agent_response_start())
                    try:
                        # self.run_step(user_message)
                        self.server.user_message(user_id="NULL", agent_id=data["agent_id"], message=user_message)
                    except Exception as e:
                        print(f"[server] self.server.user_message failed with:\n{e}")
                        print(f"{traceback.format_exc()}")
                        await websocket.send(protocol.server_agent_response_error(f"server.user_message failed with: {e}"))
                    await asyncio.sleep(1)  # pause before sending the terminating message, w/o this messages may be missed
                    await websocket.send(protocol.server_agent_response_end())

                # ... handle other message types as needed ...
                else:
                    print(f"[server] unrecognized client package data type: {data}")
                    await websocket.send(protocol.server_error(f"unrecognized client package data type: {data}"))

        except websockets.exceptions.ConnectionClosed:
            print(f"[server] connection with client was closed")
        finally:
            self.interface.unregister_client(websocket)


if __name__ == "__main__":
    server = WebSocketServer()
    asyncio.run(server.run())
