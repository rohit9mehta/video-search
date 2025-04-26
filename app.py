from typing import Dict

from sentence_transformers import SentenceTransformer
from tqdm import tqdm
# import whisper
# import torch
from pytubefix import YouTube
# import yt_dlp
from getpass import getpass
from flask import Flask, redirect, request, session, url_for, jsonify
from flask_cors import CORS
import scrapetube
import boto3
import pinecone  # !pip install pinecone-client
import os
from pinecone import Pinecone, ServerlessSpec
import ssl
import json
import shutil
import random
import time
import requests
import os
from datetime import datetime
import logging
import sys
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from threading import Thread

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
# Add file handler for logging
log_file_handler = logging.FileHandler('app.log')
log_file_handler.setLevel(logging.DEBUG)
app.logger.addHandler(log_file_handler)
app.logger.setLevel(logging.DEBUG)
app.secret_key = 'YOUR_SECRET_KEY'  # Use a secure, random key
app.config['SESSION_COOKIE_SECURE'] = True  # For HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for testing on HTTP

CORS(app, supports_credentials=True, origins="https://aivideo.planeteria.com")
# Mock database to store processed videos (use a database like DynamoDB in production)
PROCESSED_VIDEOS = set()

# AWS Configuration
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
tokens_table = dynamodb.Table('UserTokens')

# S3 bucket configuration
S3_BUCKET_NAME = "video-search-training-bucket"
S3_REGION = "us-east-2"


@app.route('/')
def home():
    return "Hello, CORS is configured!"


def get_pinecone_api_key():
    try:
        client = boto3.client('secretsmanager', region_name='us-east-2')
        
        # List all secrets and their ARNs
        secrets = client.list_secrets()
        app.logger.debug("Available secrets:")
        for secret in secrets['SecretList']:
            app.logger.debug(f"Name: {secret['Name']}, ARN: {secret['ARN']}")
        
        secret_name = "pinecone-secret"
        app.logger.debug(f"Attempting to access secret: {secret_name}")
        
        response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret['pinecone_api_key']
    except Exception as e:
        app.logger.error(f"Error type: {type(e)}")
        app.logger.error(f"Error message: {str(e)}")
        import traceback
        app.logger.error(f"Full traceback: {traceback.format_exc()}")
        raise

# Initialize S3 client
s3_client = boto3.client(
    's3',
    region_name=S3_REGION
)

def fetch_all_videos_yt(channel_url):
    # TODO
    videos = list(scrapetube.get_channel(channel_url=channel_url))[:5]
    # need to preface each with 'https://www.youtube.com/watch?v=' 
    return [video['videoId'] for video in videos]
# print(fetch_all_videos_yt("https://www.youtube.com/@rohitmehta5258"))

# Get captions for a given YouTube video
def get_captions(video_id):
    try:
        ytt_api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username="rqdaovtb",
                proxy_password="oufjkm011cad",
            )
        )
        transcript = ytt_api.fetch(video_id, languages=['en'])
        if transcript:
            # Convert transcript to SRT-like format for compatibility with existing code
            srt_content = []
            for i, snippet in enumerate(transcript.snippets, 1):
                start = snippet.start
                end = start + snippet.duration
                start_str = f"{int(start // 3600):02d}:{int((start % 3600) // 60):02d}:{int(start % 60):02d},{int((start % 1) * 1000):03d}"
                end_str = f"{int(end // 3600):02d}:{int((end % 3600) // 60):02d}:{int(end % 60):02d},{int((end % 1) * 1000):03d}"
                srt_content.append(f"{i}")
                srt_content.append(f"{start_str} --> {end_str}")
                srt_content.append(snippet.text)
                srt_content.append("")
            return "\n".join(srt_content)
        else:
            print(f"No transcripts found for video {video_id}, skipping.")
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
            video_id = video_url.split("v=")[-1] if "v=" in video_url else video_url
            captions = get_captions(video_id)

            if captions:
                print(f"Processing captions for {video_id}")
                encoded_segments.extend(self.process_captions(captions, video_id))
            else:
                print(f"No captions found for {video_id}, skipping to next video")
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
        Handles timestamps with --> separator.
        """
        try:
            # Extract start timestamp if --> is present
            if '-->' in timestamp:
                timestamp = timestamp.split('-->')[0].strip()
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
          'id': transcripts_for_upload[x]['id'],
          'video_id': transcripts_for_upload[x]['video_id'],
          'start': transcripts_for_upload[x]['start'],
          'text': transcripts_for_upload[x]['text'],
          'url': transcripts_for_upload[x]['url']
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

def sanitize_index_name(url):
    """Convert a URL into a valid Pinecone index name."""
    # Remove common URL parts
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    # Remove everything after the first slash
    url = url.split('/')[0]
    # Replace invalid characters with dash
    url = re.sub(r'[^a-z0-9-]', '-', url.lower())
    # Ensure it starts with a letter (Pinecone requirement)
    if not url[0].isalpha():
        url = 'idx-' + url
    # Truncate if too long (Pinecone has a length limit)
    return url[:62]

@app.route('/api/train', methods=['POST'])
def train_model(demo_url = None):
    try:      
        start_time = time.time()
        print(f"Starting train_model at {datetime.now()}")
        # fetch videos
        if demo_url and demo_url == "demo":
            video_urls = ["w4CMaKF_IXI", "PQtMTPhmQwM"]
            index_id = "demo-index"
        else:
            data = request.get_json()
            channel_url = data.get('channel_url')
            print(f"Fetching videos for channel {channel_url} at {time.time() - start_time:.2f} seconds")
            video_urls = fetch_all_videos_yt(channel_url)
            print(f"Fetched {len(video_urls)} videos at {time.time() - start_time:.2f} seconds")
            # Sanitize the channel URL for use as index name
            index_id = sanitize_index_name(channel_url)
            
        print(f"Using Pinecone index name: {index_id} at {time.time() - start_time:.2f} seconds")  # Debug print
        
        # filter out already processed videos
        new_videos = [url for url in video_urls if url not in PROCESSED_VIDEOS]
        print(f"Filtered to {len(new_videos)} new videos at {time.time() - start_time:.2f} seconds")
        if not new_videos:
            print(f"No new videos to process, returning at {time.time() - start_time:.2f} seconds")
            return jsonify({"message": "No new videos to process"}), 200
            
        # Process each video asynchronously
        print(f"Starting asynchronous processing for {len(new_videos)} videos at {time.time() - start_time:.2f} seconds")
        handler = EndpointHandler(path="")
        payload = {"video_urls": new_videos}
        def process_videos():
            try:
                process_start = time.time()
                print(f"Background thread started at {datetime.now()}")
                processed_data = handler(payload)
                print(f"Videos processed in background at {time.time() - process_start:.2f} seconds")
                # Pinecone integration
                dimensions = handler.sentence_transformer_model.get_sentence_embedding_dimension()
                PINECONE_API_KEY = get_pinecone_api_key()
                pc = Pinecone(api_key=PINECONE_API_KEY)
                existing_indexes = pc.list_indexes()
                if index_id not in existing_indexes:
                    print(f"Creating new Pinecone index: {index_id} at {time.time() - process_start:.2f} seconds")
                    try:
                        pc.create_index(
                            name=index_id,
                            dimension=dimensions,
                            metric="dotproduct",
                            spec=ServerlessSpec(cloud="aws",region="us-east-1")
                        )
                        print(f"Successfully created Pinecone index: {index_id} at {time.time() - process_start:.2f} seconds")
                    except Exception as e:
                        print(f"Failed to create Pinecone index {index_id}: {str(e)} at {time.time() - process_start:.2f} seconds")
                        if 'ALREADY_EXISTS' in str(e) or '409' in str(e):
                            print(f"Index {index_id} already exists. Proceeding with existing index at {time.time() - process_start:.2f} seconds")
                        else:
                            print("Checking if index already exists with compatible settings...")
                            if index_id in pc.list_indexes():
                                index_info = pc.describe_index(index_id)
                                if index_info.dimension == dimensions and index_info.metric == "dotproduct":
                                    print(f"Index {index_id} already exists with compatible settings. Proceeding... at {time.time() - process_start:.2f} seconds")
                                else:
                                    print(f"WARNING: Index {index_id} exists but with incompatible settings (dimension: {index_info.dimension}, metric: {index_info.metric}). This may cause issues. at {time.time() - process_start:.2f} seconds")
                            else:
                                print(f"WARNING: Could not create index {index_id} and it does not exist. Proceeding may fail. at {time.time() - process_start:.2f} seconds")
                else:
                    print(f"Index {index_id} already exists. Verifying compatibility... at {time.time() - process_start:.2f} seconds")
                    index_info = pc.describe_index(index_id)
                    if index_info.dimension == dimensions and index_info.metric == "dotproduct":
                        print(f"Index {index_id} is compatible. Proceeding... at {time.time() - process_start:.2f} seconds")
                    else:
                        print(f"WARNING: Index {index_id} exists but with incompatible settings (dimension: {index_info.dimension}, metric: {index_info.metric}). This may cause issues. at {time.time() - process_start:.2f} seconds")
                pinecone_index = pc.Index(index_id)
                print(f"Uploading data to Pinecone at {time.time() - process_start:.2f} seconds")
                upload_transcripts_to_vector_db(processed_data["encoded_segments"], pinecone_index, handler.sentence_transformer_model)
                # Update processed videos
                PROCESSED_VIDEOS.update(new_videos)
                print(f"Processed {len(new_videos)} new video(s). Model retrained. Total time: {time.time() - process_start:.2f} seconds")
            except Exception as e:
                print(f"Error in background processing: {str(e)}")
                import traceback
                print(f"Traceback in background: {traceback.format_exc()}")
        Thread(target=process_videos).start()
        print(f"Response returned at {time.time() - start_time:.2f} seconds")
        return jsonify({
            "message": f"Processing started for {len(new_videos)} new video(s)."
        })
    except Exception as e:
        print(f"Error in /train endpoint: {str(e)} at {time.time() - start_time if 'start_time' in locals() else 0:.2f} seconds")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


def query_pinecone_model(query, pinecone_index, sentence_transformer_model):
  encoded_query = sentence_transformer_model.encode(query).tolist()
  # print(encoded_query)
  return pinecone_index.query(vector=encoded_query, top_k=3,
                              include_metadata=True)

@app.route('/api/query', methods=['GET'])
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
        index_id = sanitize_index_name(channel_url)
        PINECONE_API_KEY = get_pinecone_api_key()
        pc = Pinecone(
            api_key=PINECONE_API_KEY
        )
        pinecone_index = pc.Index(index_id)
        sentence_transformer_model = SentenceTransformer("multi-qa-mpnet-base-dot-v1")
        results = query_pinecone_model(query_phrase, pinecone_index, sentence_transformer_model)
        app.logger.debug(f"Raw results from Pinecone: {results}")
        # Clean the results to handle None values
        cleaned_matches = []
        matches = results.get('matches', [])
        app.logger.debug(f"Number of matches: {len(matches)}")
        for match in matches:
            if match is None:
                app.logger.debug("Encountered a None match, skipping.")
                continue
            if not isinstance(match, dict):
                app.logger.debug(f"Match is not a dictionary, type: {type(match)}, attempting to convert.")
                # Convert ScoredVector to dict if possible
                try:
                    match_dict = {
                        'id': getattr(match, 'id', ''),
                        'score': getattr(match, 'score', 0.0),
                        'metadata': getattr(match, 'metadata', {}),
                        'values': getattr(match, 'values', [])
                    }
                    cleaned_match = {}
                    for key, value in match_dict.items():
                        if value is None:
                            cleaned_match[key] = ""
                        else:
                            cleaned_match[key] = value
                    # Round down the timestamp in the URL if it exists in metadata
                    if 'metadata' in cleaned_match and 'url' in cleaned_match['metadata']:
                        url = cleaned_match['metadata']['url']
                        if '&t=' in url:
                            try:
                                timestamp_str = url.split('&t=')[1]
                                timestamp_float = float(timestamp_str)
                                rounded_timestamp = int(timestamp_float)
                                cleaned_match['metadata']['url'] = url.split('&t=')[0] + '&t=' + str(rounded_timestamp)
                            except (ValueError, IndexError):
                                app.logger.debug(f"Failed to parse or round timestamp in URL: {url}")
                    cleaned_matches.append(cleaned_match)
                    app.logger.debug(f"Successfully converted match to dict: {cleaned_match}")
                except Exception as e:
                    app.logger.debug(f"Failed to convert match to dict: {str(e)}")
                    continue
            else:
                cleaned_match = {}
                for key, value in match.items():
                    if value is None:
                        cleaned_match[key] = ""
                    else:
                        cleaned_match[key] = value
                # Round down the timestamp in the URL if it exists in metadata
                if 'metadata' in cleaned_match and 'url' in cleaned_match['metadata']:
                    url = cleaned_match['metadata']['url']
                    if '&t=' in url:
                        try:
                            timestamp_str = url.split('&t=')[1]
                            timestamp_float = float(timestamp_str)
                            rounded_timestamp = int(timestamp_float)
                            cleaned_match['metadata']['url'] = url.split('&t=')[0] + '&t=' + str(rounded_timestamp)
                        except (ValueError, IndexError):
                            app.logger.debug(f"Failed to parse or round timestamp in URL: {url}")
                cleaned_matches.append(cleaned_match)
        app.logger.debug(f"Number of cleaned matches: {len(cleaned_matches)}")
        return jsonify(cleaned_matches)
    except Exception as e:
        app.logger.error(f"Error in /api/query endpoint: {str(e)}")
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

def ensure_table_exists():
    try:
        # Check if table exists
        dynamodb.Table('UserTokens').table_status
        print("UserTokens table exists")
    except Exception as e:
        try:
            print("Creating UserTokens table...")
            # Create the table
            table = dynamodb.create_table(
                TableName='UserTokens',
                KeySchema=[
                    {
                        'AttributeName': 'user_id',
                        'KeyType': 'HASH'  # Partition key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'  # String
                    }
                ],
                BillingMode='PAY_PER_REQUEST'  # On-demand capacity
            )
            # Don't wait for the table, just log that we started creation
            print("UserTokens table creation initiated")
        except Exception as create_error:
            print(f"Error creating table: {str(create_error)}")
            # Continue anyway - we'll handle table not existing in the routes

if __name__ == '__main__':
    ensure_table_exists()
    app.run(host='0.0.0.0', port=5000, debug=True)
# if __name__ == '__main__':
#     app.run(port=8080, debug=True)
# with app.app_context():
#     train_model(demo_url="demo")
#     print(query_model(demo_phrase="maple syrup", demo_url="demo"))
# print("BREAK")
# print(query("crispy exterior", channel_url="demo"))





