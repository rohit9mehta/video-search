import boto3
import json
import sys
from youtube_transcript_api import YouTubeTranscriptApi
from botocore.exceptions import NoCredentialsError

# --- S3 CONFIG: Reference from app.py ---
S3_BUCKET_NAME = "video-search-training-bucket"
S3_REGION = "us-east-2"

s3_client = boto3.client('s3', region_name=S3_REGION)

def fetch_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        # Format as list of {time, text}
        formatted = [{"time": int(item['start']), "text": item['text']} for item in transcript]
        return formatted
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None

def upload_to_s3(data, video_id):
    key = f"transcripts/{video_id}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=json.dumps(data),
            ContentType='application/json'
        )
        print(f"Uploaded transcript to s3://{S3_BUCKET_NAME}/{key}")
    except NoCredentialsError:
        print("AWS credentials not found.")
    except Exception as e:
        print(f"Error uploading to S3: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_and_upload_transcript.py <youtube_video_id>")
        sys.exit(1)
    video_id = sys.argv[1]
    transcript = fetch_transcript(video_id)
    if transcript:
        upload_to_s3(transcript, video_id) 