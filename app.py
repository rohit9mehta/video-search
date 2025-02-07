from typing import Dict

from sentence_transformers import SentenceTransformer
from tqdm import tqdm
# import whisper
# import torch
from pytubefix import YouTube
# import yt_dlp
from getpass import getpass
from flask import Flask, redirect, request, session, url_for
from flask_cors import CORS
import scrapetube
import boto3
import pinecone  # !pip install pinecone-client
import os
from pinecone import Pinecone, ServerlessSpec
import ssl
import json
from botocore.exceptions import NoCredentialsError
import shutil
import random
import time
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'  # Use a secure, random key

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for testing on HTTP

CORS(app)
# Mock database to store processed videos (use a database like DynamoDB in production)
PROCESSED_VIDEOS = set()

# AWS Configuration
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
tokens_table = dynamodb.Table('UserTokens')

# S3 bucket configuration
S3_BUCKET_NAME = "video-search-training-bucket"
S3_REGION = "us-east-2"

def get_google_client_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-2')
    response = client.get_secret_value(SecretId='google-client-secrets')
    return json.loads(response['SecretString'])

# Scopes needed for accessing captions
CLIENT_SECRETS = get_google_client_secrets()
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

@app.route('/')
def home():
    return "Hello, CORS is configured!"

# Step 1: Login Route
@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS,
        scopes=SCOPES,
        redirect_uri='http://localhost:5000/oauth2callback'
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(auth_url)

# Step 2: OAuth Callback
@app.route('/oauth2callback')
def oauth2callback():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS,
        scopes=SCOPES,
        redirect_uri='http://localhost:5000/oauth2callback'
    )
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials

    user_info = get_user_info(credentials)
    # Store tokens securely in DynamoDB
    tokens_table.put_item(Item={
        'user_id': user_info['email'],
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat()
    })
    
    return jsonify({"message": "Authentication successful!", "user": user_info})

def get_user_info(credentials):
    youtube = build('youtube', 'v3', credentials=credentials)
    response = youtube.channels().list(part='snippet', mine=True).execute()
    return response['items'][0]['snippet']

def get_stored_credentials(user_id):
    response = tokens_table.get_item(Key={'user_id': user_id})
    if 'Item' not in response:
        return None

    data = response['Item']
    credentials = Credentials(
        token=data['token'],
        refresh_token=data['refresh_token'],
        token_uri=data['token_uri'],
        client_id=data['client_id'],
        client_secret=data['client_secret'],
        scopes=data['scopes']
    )

    # Check if the token is expired
    if datetime.fromisoformat(data['expiry']) <= datetime.utcnow():
        try:
            credentials.refresh(boto3.Session())  # Refresh the token
            # Update DynamoDB with the new token
            tokens_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET token = :t, expiry = :e",
                ExpressionAttributeValues={
                    ':t': credentials.token,
                    ':e': credentials.expiry.isoformat()
                }
            )
        except Exception as e:
            print(f"Error refreshing token for {user_id}: {e}")
            return None

    return credentials

# # Fetch API key from AWS Secrets Manager
# def get_youtube_api_key():
#     client = boto3.client('secretsmanager', region_name='us-east-2')
#     secret_name = "youtube-data-api-key"

#     response = client.get_secret_value(SecretId=secret_name)
#     secret = json.loads(response['SecretString'])
#     return secret['youtube_api_key']

def get_pinecone_api_key():
    client = boto3.client('secretsmanager', region_name='us-east-2')
    secret_name = "pinecone-secret"

    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response['SecretString'])
    return secret['pinecone_api_key']

# Initialize S3 client
s3_client = boto3.client(
    's3',
    region_name=S3_REGION
)

# to bypass SSL problem on local run
ssl._create_default_https_context = ssl._create_unverified_context

def fetch_all_videos_yt(channel_url):
    # TODO
    videos = scrapetube.get_channel(channel_url=channel_url)
    # need to preface each with 'https://www.youtube.com/watch?v=' 
    return [video['videoId'] for video in videos]
# print(fetch_all_videos_yt("https://www.youtube.com/@rohitmehta5258"))

# Get captions for a given YouTube video
def get_captions(video_id, credentials):
    try:
        creds = get_stored_credentials(user_id)
        if not creds:
            return redirect('/login')  # Redirect if not authorized
        youtube = build('youtube', 'v3', credentials=credentials)
        # Get captions list
        captions = youtube.captions().list(
            part='id,snippet',
            videoId=video_id
        ).execute()

        if captions['items']:
            caption_id = captions['items'][0]['id']
            # Download captions
            caption = youtube.captions().download(
                id=caption_id,
                tfmt='srt'
            ).execute()
            return caption
        else:
            return None
    except Exception as e:
        print(f"Error fetching captions for video {video_id}: {e}")
        return None

class EndpointHandler():
    def __init__(self, path=""):
        # load the model
        SENTENCE_TRANSFORMER_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"
        print("Loading SentenceTransformer model locally...")
        self.sentence_transformer_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)

    def __call__(self, data: Dict[str, str]) -> Dict:
        video_urls = data.get("video_urls", [])
        encoded_segments = []

        for video_url in video_urls:
            video_id = video_url.split("v=")[-1]
            captions = get_captions(video_id, credentials)

            if captions:
                print(f"Processing captions for {video_id}")
                encoded_segments.extend(self.process_captions(captions, video_id))
            else:
                print(f"No captions found for {video_id}")
                # transcript_data = self.transcribe_video(video_url)
                # encoded_segments.extend(self.encode_sentences(self.combine_transcripts([transcript_data])))
        return {"encoded_segments": encoded_segments}
    
    def encode_sentences(self, transcripts, batch_size=64):
        """
        Encoding all of our segments at once or storing them locally would require too much compute or memory.
        So we do it in batches of 64
        :param transcripts:
        :param batch_size:
        :return:
        """
        # loop through in batches of 64
        all_batches = []
        for i in tqdm(range(0, len(transcripts), batch_size)):
            # find end position of batch (for when we hit end of data)
            i_end = min(len(transcripts), i + batch_size)
            # extract the metadata like text, start/end positions, etc
            batch_meta = [{
                **row
            } for row in transcripts[i:i_end]]
            # extract only text to be encoded by embedding model
            batch_text = [
                row['text'] for row in batch_meta
            ]
            # create the embedding vectors
            batch_vectors = self.sentence_transformer_model.encode(batch_text).tolist()

            batch_details = [
                {
                    **batch_meta[x],
                    'vectors':batch_vectors[x]
                } for x in range(0, len(batch_meta))
            ]
            all_batches.extend(batch_details)

        return all_batches
    
    def process_captions(self, srt_data, video_id):
        """
        Process captions in SRT format to extract timestamps and encode sentences.
        """
        captions = []
        entries = srt_data.strip().split("\n\n")

        for entry in entries:
            parts = entry.strip().split("\n")
            if len(parts) >= 3:
                timestamp = parts[1]
                text = " ".join(parts[2:])
                print(f"Processing caption: {text}")
                captions.append({
                    "id": f"{video_id}-t{timestamp}",
                    "video_id": video_id,
                    "start": self.convert_timestamp_to_seconds(timestamp),
                    "text": text,
                    "url": f"https://www.youtube.com/watch?v={video_id}&t={self.convert_timestamp_to_seconds(timestamp)}"
                })

        # Encode captions using SentenceTransformer
        encoded_captions = self.encode_sentences(captions)
        return encoded_captions

    def convert_timestamp_to_seconds(self, timestamp):
        """
        Converts SRT timestamp format (00:01:23,456 or 00:01:23) to seconds.
        """
        try:
            if ',' in timestamp:
                h, m, s = timestamp.split(":")
                s, ms = s.split(",")
                return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
            else:
                h, m, s = timestamp.split(":")
                return int(h) * 3600 + int(m) * 60 + int(s)
        except ValueError as e:
            print(f"Invalid timestamp format: {timestamp}")
            return 0  # Default to 0 if invalid format


# payload = {"video_urls": ["https://www.youtube.com/watch?v=w4CMaKF_IXI", "https://www.youtube.com/watch?v=PQtMTPhmQwM"], "trying_live": True} # I Tried Every Fast Food Chicken Tender In America

def upload_transcripts_to_vector_db(transcripts_for_upload, pinecone_index, sentence_transformer_model, batch_size=64):
  # loop through in batches of batch_size to encode and insert
  for i in tqdm(range(0, len(transcripts_for_upload), batch_size)):
      # find end position of batch (for when we hit end of data)
      i_end = min(len(transcripts_for_upload)-1, i+batch_size)
      # extract the metadata like text, start/end positions, etc
      batch_meta = [{
          **transcripts_for_upload[x]
      } for x in range(i, i_end)]
      # extract only text to be encoded by embedding model
      batch_text = [
          row['text'] for row in transcripts_for_upload[i:i_end]
      ]
      # create the embedding vectors
      batch_embeds = sentence_transformer_model.encode(batch_text).tolist()
      # extract IDs to be attached to each embedding and metadata
      batch_ids = [
          row['id'] for row in transcripts_for_upload[i:i_end]
      ]
      # 'upsert' (insert) IDs, embeddings, and metadata to index
      to_upsert = list(zip(
          batch_ids, batch_embeds, batch_meta
      ))
      pinecone_index.upsert(to_upsert)
    #   print(f'Uploaded Batches: {i} to {i_end}')

@app.route('/train', methods=['POST'])
def train_model(demo_url = None):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required."}), 401
        credentials = get_stored_credentials(user_id)
        if not credentials:
            return jsonify({"error": "Invalid or expired token."}), 401
        # fetch videos
        if demo_url and demo_url == "demo":
            video_urls = ["w4CMaKF_IXI", "PQtMTPhmQwM"]
        else:
            data = request.get_json()
            channel_url = data.get('channel_url')
            video_urls = fetch_all_videos_yt(channel_url)
        # filter out already processed videos
        new_videos = [url for url in video_urls if url not in PROCESSED_VIDEOS]
        if not new_videos:
            return jsonify({"message": "No new videos to process"}), 200
        # Process each video
        handler = EndpointHandler(path="")
        payload = {"video_urls": new_videos}
        processed_data = handler(payload)
        # Pinecone integration  
        dimensions = handler.sentence_transformer_model.get_sentence_embedding_dimension()
        index_id = "search-" + channel_url
        PINECONE_API_KEY = get_pinecone_api_key()
        pc = Pinecone(
            api_key=PINECONE_API_KEY
        )
        if index_id not in pc.list_indexes():
            pc.create_index(
                name=index_id,
                dimension=dimensions,
                metric="dotproduct",
                spec=ServerlessSpec(cloud="aws",region="us-east-1")
            )
        pinecone_index = pc.Index(index_id)
        # pinecone_index.describe_index_stats()
        upload_transcripts_to_vector_db(processed_data["encoded_segments"], pinecone_index, handler.sentence_transformer_model)

        # Update processed videos
        PROCESSED_VIDEOS.update(new_videos)
        return jsonify({
            "message": f"Processed {len(new_videos)} new video(s). Model retrained."
        })
    except Exception as e:
        print("Error in /train endpoint:", e)  # Debug print
        return jsonify({"error": str(e)}), 500


def query_pinecone_model(query, pinecone_index, sentence_transformer_model):
  encoded_query = sentence_transformer_model.encode(query).tolist()
  # print(encoded_query)
  return pinecone_index.query(vector=encoded_query, top_k=3,
                              include_metadata=True)

@app.route('/query', methods=['GET'])
def query_model(demo_phrase = None, demo_url = None):
    try:
        if demo_phrase and demo_url:
            query_phrase = demo_phrase
            channel_url = demo_url
        else:
            query_phrase = request.args.get('query_phrase')
            if not query_phrase:
                return jsonify({"error": "Query phrase is required"}), 400
            channel_url = request.args.get('channel_url')
            if not channel_url:
                return jsonify({"error": "Channel url is required"}), 400
        index_id = "search-" + channel_url
        PINECONE_API_KEY = get_pinecone_api_key()
        pc = Pinecone(
            api_key=PINECONE_API_KEY
        )
        pinecone_index = pc.Index(index_id)
        sentence_transformer_model = SentenceTransformer("multi-qa-mpnet-base-dot-v1")
        results = query_pinecone_model(query_phrase, pinecone_index, sentence_transformer_model)
        return jsonify(results['matches'])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
# if __name__ == '__main__':
#     app.run(port=8080, debug=True)
# with app.app_context():
#     train_model(demo_url="demo")
#     print(query_model(demo_phrase="maple syrup", demo_url="demo"))
# print("BREAK")
# print(query("crispy exterior", channel_url="demo"))





