import os
import asyncio
from telethon import TelegramClient, errors
from telethon.tl.types import InputMessagesFilterVideo, Message
from dotenv import load_dotenv
from time import sleep
import uuid

load_dotenv()  # Load environment variables from .env.


# Progress callback function
def progress_callback(current, total):
    percent = (current / total) * 100
    print(f"\rDownload progress: {percent:.2f}% ({current}/{total} bytes)", end="", flush=True)


async def download_media_with_retry(client: TelegramClient, message: Message, folder: str, protected_group, id_filter):
    """Download media and handle flood wait errors by retrying."""
    medias = []

    if message.media:
        os.makedirs(folder, exist_ok=True)

        if message.grouped_id:
            all_messages = await client.get_messages(protected_group, min_id=id_filter - 100, max_id=id_filter + 100)
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
                        print(f"Media downloaded to {file_path}")
                        os.rename(file_path, os.path.join(folder, str(uuid.uuid4())[0:5] + os.path.basename(file_path)))
                        break  # Exit loop if successful
                    except errors.FloodError as e:
                        print(f"FloodWaitError: Must wait for 60 seconds.")
                        await asyncio.sleep(60)  # Wait for the specified time
                    except Exception as e:
                        print(f"Error occurred while downloading: {e}")
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                        break


async def main():

    # Replace these with your own values
    api_id = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    phone_number = os.environ.get("PHONE_NUMBER")

    message_links: list[str] = []
    with open("links.txt", "r") as reader:
        message_links = reader.read().split("\n")

    for message_link in message_links:
        print(f"download link :{message_link}")
        protected_group = message_link.split("/")[-2]
        if protected_group.isnumeric():
            protected_group = int(protected_group)

        id_filter = int(message_link.split("/")[-1])

        # Create the client and connect
        client = TelegramClient("session_name", api_id, api_hash)
        await client.start(phone=phone_number)

        try:
            # Fetch the specific message by ID
            message = await client.get_messages(protected_group, ids=id_filter)

            folder = f"downloads/{protected_group}"
            if message.grouped_id:
                folder += f"/{message.grouped_id}"

            await download_media_with_retry(client, message, folder, protected_group, id_filter)

        except errors.FloodWaitError as e:
            print(f"Flood wait error: Retry after {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)  # Wait before retrying
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Disconnect the client
            await client.disconnect()


# Run the main function
asyncio.run(main())
