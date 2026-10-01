"""A2A Client for interacting with the SRAG A2A Server.

Discovers the SRAG agent via its Agent Card, connects over the A2A protocol
(HTTP JSON-RPC / REST), and sends natural-language queries.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path so package imports work cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure UTF-8 on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.client.errors import A2AClientError, AgentCardResolutionError
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role, SendMessageRequest


DEFAULT_SERVER_URL = os.getenv("A2A_SERVER_URL", "http://localhost:8001")


async def ask_srag_agent(
    query: str,
    server_url: str = DEFAULT_SERVER_URL,
) -> str | None:
    """Send a natural-language query to the SRAG A2A server and return the response text.

    Steps:
    1. Resolve & validate the Agent Card from `/.well-known/agent-card.json`.
    2. Instantiate the A2A client using the discovered card & protocol interface.
    3. Construct a SendMessageRequest with role=ROLE_USER and unique message ID.
    4. Send the message and await the A2A response event stream.
    5. Extract and return the final text response.
    """
    print(f"\n[A2A Client] Target Server URL : {server_url}")
    print(f"[A2A Client] User Query        : {query}\n")

    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            # Step 1: Discover Agent Card from /.well-known/agent-card.json
            print("[A2A Client] Step 1: Fetching Agent Card from /.well-known/agent-card.json...")
            resolver = A2ACardResolver(http_client, server_url)
            try:
                card = await resolver.get_agent_card()
            except httpx.ConnectError:
                print(
                    f"\n[ERROR] Unable to connect to A2A server at {server_url}.\n"
                    f"Please ensure the A2A server is running:\n"
                    f"  uv run python a2a_server.py\n"
                )
                return None
            except AgentCardResolutionError as e:
                print(f"\n[ERROR] Failed to resolve Agent Card: {e}\n")
                return None

            print(f"[A2A Client] Discovered Agent  : {card.name} (v{card.version})")
            if card.skills:
                skill_names = [s.name for s in card.skills]
                print(f"[A2A Client] Available Skills  : {skill_names}")
            print(f"[A2A Client] Interfaces        : {[(i.protocol_binding, i.url) for i in card.supported_interfaces]}")

            # Step 2: Initialize A2A Client from the Agent Card
            print("\n[A2A Client] Step 2: Creating A2A client from discovered Agent Card...")
            config = ClientConfig(httpx_client=http_client)
            client = await create_client(card, client_config=config)

            # Step 3: Build A2A SendMessageRequest
            print("[A2A Client] Step 3: Sending SendMessageRequest...")
            user_message = new_text_message(
                text=query,
                role=Role.ROLE_USER,
            )
            request = SendMessageRequest(message=user_message)

            # Step 4: Stream/receive response from A2A server
            final_text: str | None = None
            async for response in client.send_message(request):
                if response.HasField("message"):
                    final_text = get_message_text(response.message)
                elif response.HasField("task"):
                    task = response.task
                    print(f"[A2A Client] Task update: state={task.status.state}")
                    if task.artifacts:
                        for artifact in task.artifacts:
                            print(f"[A2A Client] Artifact: {artifact.name}")

            # Step 5: Return result
            if final_text is not None:
                print("\n" + "=" * 65)
                print("A2A Server Response:")
                print(final_text)
                print("=" * 65 + "\n")
                return final_text
            else:
                print("\n[WARNING] Received empty response from A2A server.\n")
                return None

    except A2AClientError as e:
        print(f"\n[ERROR] A2A Client Error: {e}\n")
        return None
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during A2A communication: {type(e).__name__}: {e}\n")
        return None


async def main():
    """CLI entrypoint for testing the A2A client."""
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "How many tables in the db retrun only table count?"
    await ask_srag_agent(query)


if __name__ == "__main__":
    asyncio.run(main())
