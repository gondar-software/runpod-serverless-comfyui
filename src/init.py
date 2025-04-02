import runpod
from runpod.serverless.utils import rp_upload
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import base64
from io import BytesIO
from PIL import video

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 50))
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = int(os.environ.get("COMFY_API_AVAILABLE_MAX_RETRIES", 500))
# Time to wait between poll attempts in milliseconds
COMFY_POLLING_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 250))
# Maximum number of poll attempts
COMFY_POLLING_MAX_RETRIES = int(os.environ.get("COMFY_POLLING_MAX_RETRIES", 500))
# Host where ComfyUI is running
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")
# Workflow path
COMFY_WORKFLOW_PATH = os.environ.get("COMFY_WORKFLOW_PATH", "/workspace/workflow.json")
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"
COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output")
BASE_URL = os.environ.get("BASE_URL", "example.png")

# def validate_input(job_input):
#     """
#     Validates the input for the handler function.

#     Args:
#         job_input (dict): The input data to validate.

#     Returns:
#         tuple: A tuple containing the validated data and an error message, if any.
#                The structure is (validated_data, error_message).
#     """
#     # Validate if job_input is provided
#     if job_input is None:
#         return None, "Please provide input"

#     # Check if input is a string and try to parse it as JSON
#     if isinstance(job_input, str):
#         try:
#             job_input = json.loads(job_input)
#         except json.JSONDecodeError:
#             return None, "Invalid JSON format in input"

#     # Validate 'workflow' in input
#     workflow = job_input.get("workflow")
#     if workflow is None:
#         return None, "Missing 'workflow' parameter"

#     # Validate 'videos' in input, if provided
#     videos = job_input.get("videos")
#     if videos is not None:
#         if not isinstance(videos, list) or not all(
#             "name" in video and "video" in video for video in videos
#         ):
#             return (
#                 None,
#                 "'videos' must be a list of objects with 'name' and 'video' keys",
#             )

#     # Return validated data and no error
#     return {"workflow": workflow, "videos": videos}, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """

    for i in range(retries):
        try:
            response = requests.get(url)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print(f"runpod-worker-comfy - API is reachable")
                return True
        except requests.RequestException as e:
            # If an exception occurs, the server may not be ready
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(
        f"runpod-worker-comfy - Failed to connect to server at {url} after {retries} attempts."
    )
    return False


def upload_videos(videos):
    """
    Upload a list of base64 encoded videos to the ComfyUI server using the /upload/video endpoint.

    Args:
        videos (list): A list of dictionaries, each containing the 'name' of the video and the 'video' as a base64 encoded string.
        server_address (str): The address of the ComfyUI server.

    Returns:
        list: A list of responses from the server for each video upload.
    """
    if not videos:
        return {"status": "success", "message": "No videos to upload", "details": []}

    responses = []
    upload_errors = []

    print(f"runpod-worker-comfy - video(s) upload")

    for video in videos:
        name = video["name"]
        video_data = video["video"]
        blob = base64.b64decode(video_data)

        # Prepare the form data
        files = {
            "video": (name, BytesIO(blob), "video/png"),
            "overwrite": (None, "true"),
        }

        # POST request to upload the video
        response = requests.post(f"http://{COMFY_HOST}/upload/video", files=files)
        if response.status_code != 200:
            upload_errors.append(f"Error uploading {name}: {response.text}")
        else:
            responses.append(f"Successfully uploaded {name}")

    if upload_errors:
        print(f"runpod-worker-comfy - video(s) upload with errors")
        return {
            "status": "error",
            "message": "Some videos failed to upload",
            "details": upload_errors,
        }

    print(f"runpod-worker-comfy - video(s) upload complete")
    return {
        "status": "success",
        "message": "All videos uploaded successfully",
        "details": responses,
    }


def queue_workflow(workflow):
    """
    Queue a workflow to be processed by ComfyUI

    Args:
        workflow (dict): A dictionary containing the workflow to be processed

    Returns:
        dict: The JSON response from ComfyUI after processing the workflow
    """

    # The top level element "prompt" is required by ComfyUI
    data = json.dumps({"prompt": workflow}).encode("utf-8")

    req = urllib.request.Request(f"http://{COMFY_HOST}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    with urllib.request.urlopen(f"http://{COMFY_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def base64_encode(img_path):
    """
    Returns base64 encoded video.

    Args:
        img_path (str): The path to the video

    Returns:
        str: The base64 encoded video
    """
    with video.open(img_path) as img:
        # Convert RGBA/PNG to RGB/JPEG (removes alpha channel if needed)
        if img.mode in ('RGBA', 'LA'):
            img = img.convert('RGB')
        
        # Save to JPEG in memory
        jpg_buffer = BytesIO()
        img.save(jpg_buffer, format='JPEG', quality=85)
        
        # Encode to Base64
        return base64.b64encode(jpg_buffer.getvalue()).decode('utf-8')


def main():
    """
    The main function that handles a job of generating an video.

    This function validates the input, sends a prompt to ComfyUI for processing,
    polls ComfyUI for result, and retrieves generated videos.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated videos.
    """

    # Make sure that the input is valid
    # validated_data, error_message = validate_input(job_input)
    # if error_message:
    #     return {"error": error_message}

    with open(COMFY_WORKFLOW_PATH, 'r', encoding='utf-8') as file:
        query = json.load(file)
    query["111"]["inputs"]["url_or_path"] = BASE_URL

    validated_data = {
        "workflow": query
    }

    # Extract validated data
    workflow = validated_data["workflow"]
    # videos = validated_data.get("videos")

    # Make sure that the ComfyUI API is available
    check_server(
        f"http://{COMFY_HOST}",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    )

    # Upload videos if they exist
    # upload_result = upload_videos(videos)

    # if upload_result["status"] == "error":
    #     return upload_result

    # Queue the workflow
    try:
        queued_workflow = queue_workflow(workflow)
        prompt_id = queued_workflow["prompt_id"]
        print(f"runpod-worker-comfy - queued workflow with ID {prompt_id}")
    except Exception as e:
        return {"error": f"Error queuing workflow: {str(e)}"}

    # Poll for completion
    print(f"runpod-worker-comfy - wait until video generation is complete")
    retries = 0
    try:
        while retries < COMFY_POLLING_MAX_RETRIES:
            history = get_history(prompt_id)

            # Exit the loop if we have found the history
            if prompt_id in history and history[prompt_id].get("outputs"):
                break
            else:
                # Wait before trying again
                time.sleep(COMFY_POLLING_INTERVAL_MS / 1000)
                retries += 1
        else:
            return {"error": "Max retries reached while waiting for video generation"}
    except Exception as e:
        return {"error": f"Error waiting for video generation: {str(e)}"}

    for filename in os.listdir(COMFY_OUTPUT_PATH):
        file_path = os.path.join(COMFY_OUTPUT_PATH, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

    print("Initialization is finished")


# Start the handler only if this script is run directly
if __name__ == "__main__":
    main()
