import os
import asyncio
from telethon import TelegramClient, errors
from telethon.tl.types import InputPeerChannel, Message
from dotenv import load_dotenv
import uuid

load_dotenv()  # Load environment variables from .env.


# Progress callback function
def progress_callback(current, total):
    percent = (current / total) * 100
    print(f"\rDownload progress: {percent:.2f}% ({current}/{total} bytes)", end="", flush=True)


async def download_media_with_retry(client: TelegramClient, message: Message, folder: str):
    """Download media and handle errors with retry."""
    medias = []

    if message.media:
        os.makedirs(folder, exist_ok=True)

        if message.grouped_id:
            # Fetch messages in the same media group
            all_messages = await client.get_messages(message.peer_id, min_id=message.id - 100, max_id=message.id + 100)
            medias = [m for m in all_messages if m.grouped_id == message.grouped_id]
        else:
            medias.append(message)

        for media in medias:
            file_path = None
            if media.photo or media.video:
                while True:
                    try:
                        # Download the media with progress callback
                        file_path = await client.download_media(media, progress_callback=progress_callback)
                        print(f"\nMedia downloaded to {file_path}")
                        # Rename the file to a unique name
                        os.rename(file_path, os.path.join(folder, str(uuid.uuid4())[:5] + os.path.basename(file_path)))
                        break  # Exit loop if successful
                    except errors.FloodWaitError as e:
                        print(f"FloodWaitError: Must wait for {e.seconds} seconds.")
                        await asyncio.sleep(e.seconds)  # Wait for the specified time
                    except Exception as e:
                        print(f"Error occurred while downloading: {e}")
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                        break


async def process_message_link(client: TelegramClient, message_link: str):
    """Process a single message link and download the associated media."""
    try:
        # Identify if it's a private or public link
        if "/c/" in message_link:
            # Handle private group/channel link
            parts = message_link.split("/")
            protected_group = int(parts[-2])
            id_filter = int(parts[-1])

            # Resolve the entity of the private group/channel by ID
            entity = await client.get_entity(InputPeerChannel(protected_group, 0))  # If access_hash needed, get it

        else:
            # Handle public channel link
            parts = message_link.split("/")
            channel_name = parts[-2]
            id_filter = int(parts[-1])

            # Resolve the entity of the public channel by its username
            entity = await client.get_entity(channel_name)

        # Fetch the specific message by ID
        message = await client.get_messages(entity, ids=id_filter)

        # Create a folder for the downloads
        folder = f"downloads/{entity.id}"
        if message.grouped_id:
            folder += f"/{message.grouped_id}"

        # Download the media
        await download_media_with_retry(client, message, folder)

    except errors.FloodWaitError as e:
        print(f"Flood wait error: Retry after {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)  # Wait before retrying
    except Exception as e:
        print(f"An error occurred while processing {message_link}: {e}")


async def main():
    # Load your Telegram API credentials from environment variables
    api_id = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    phone_number = os.environ.get("PHONE_NUMBER")

    # Read message links from the file
    message_links: list[str] = []
    with open("links.txt", "r") as reader:
        message_links = [link.strip() for link in reader if link.strip()]

    # Create the Telegram client and start the session
    client = TelegramClient("session_name", api_id, api_hash)
    await client.start(phone=phone_number)

    try:
        # Process each message link
        for message_link in message_links:
            print(f"Processing message link: {message_link}")
            await process_message_link(client, message_link)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Disconnect the client
        await client.disconnect()


# Run the main function
asyncio.run(main())
