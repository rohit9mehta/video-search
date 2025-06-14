from typing import Dict

from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from pytubefix import YouTube
from getpass import getpass
from flask import Flask, redirect, request, session, url_for, jsonify
from flask_cors import CORS
import scrapetube
import boto3
import pinecone
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
from dotenv import load_dotenv
import openai
import pdfplumber
import hashlib
import io
import fitz  # PyMuPDF

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))

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

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- CUSTOMER KEY MANAGEMENT ---
CUSTOMER_KEYS_TABLE_NAME = 'CustomerKeys'

def ensure_customer_keys_table_exists():
    try:
        dynamodb.Table(CUSTOMER_KEYS_TABLE_NAME).table_status
        print(f"{CUSTOMER_KEYS_TABLE_NAME} table exists")
    except Exception as e:
        try:
            print(f"Creating {CUSTOMER_KEYS_TABLE_NAME} table...")
            table = dynamodb.create_table(
                TableName=CUSTOMER_KEYS_TABLE_NAME,
                KeySchema=[
                    {'AttributeName': 'customer_key', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'customer_key', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            print(f"{CUSTOMER_KEYS_TABLE_NAME} table creation initiated")
        except Exception as create_error:
            print(f"Error creating table: {str(create_error)}")


def is_valid_customer_key(customer_key, channel_url):
    try:
        table = dynamodb.Table(CUSTOMER_KEYS_TABLE_NAME)
        resp = table.get_item(Key={'customer_key': customer_key})
        item = resp.get('Item')
        if not item:
            return False
        allowed_channels = item.get('allowed_channels', [])
        return channel_url in allowed_channels
    except Exception as e:
        print(f"Error validating customer key: {e}")
        return False

# --- END CUSTOMER KEY MANAGEMENT ---

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

# Get captions for a given video (YouTube or Vimeo)
def get_captions(video_id, platform='youtube'):
    try:
        if platform == 'youtube':
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
                print(f"No transcripts found for YouTube video {video_id}, skipping.")
                return None
        elif platform == 'vimeo':
            # Placeholder for Vimeo caption fetching
            # This would require Vimeo's API or a similar service to fetch captions
            print(f"Fetching captions for Vimeo video {video_id} is not implemented yet.")
            return None
    except Exception as e:
        print(f"Error fetching captions for {platform} video {video_id}: {e}")
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
            if 'youtube.com' in video_url:
                video_id = video_url.split("v=")[-1] if "v=" in video_url else video_url
                captions = get_captions(video_id, platform='youtube')
            elif 'vimeo.com' in video_url:
                video_id = video_url.split('/')[-1] if '/' in video_url else video_url
                captions = get_captions(video_id, platform='vimeo')
            else:
                print(f"Unsupported video URL: {video_url}")
                continue

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

def upload_transcripts_to_vector_db(transcripts_for_upload, pinecone_index, sentence_transformer_model, batch_size=64):
    # Collect enriched segments by video_id for S3 upload
    segments_by_video = {}
    for segment in transcripts_for_upload:
        video_id = segment.get('video_id')
        if not video_id:
            continue
        if video_id not in segments_by_video:
            segments_by_video[video_id] = []
        segments_by_video[video_id].append(segment)

    # Loop through in batches of batch_size to encode and insert into Pinecone
    for i in tqdm(range(0, len(transcripts_for_upload), batch_size)):
        i_end = min(len(transcripts_for_upload), i + batch_size)
        batch_meta = [{
            'id': transcripts_for_upload[x]['id'],
            'video_id': transcripts_for_upload[x]['video_id'],
            'start': transcripts_for_upload[x]['start'],
            'text': transcripts_for_upload[x]['text'],
            'url': transcripts_for_upload[x]['url']
        } for x in range(i, i_end)]
        batch_text = [row['text'] for row in transcripts_for_upload[i:i_end]]
        batch_embeds = sentence_transformer_model.encode(batch_text).tolist()
        batch_ids = [row['id'] for row in transcripts_for_upload[i:i_end]]
        # Add embeddings to batch_meta for S3
        for idx, meta in enumerate(batch_meta):
            meta['embedding'] = batch_embeds[idx]
        to_upsert = list(zip(batch_ids, batch_embeds, batch_meta))
        pinecone_index.upsert(to_upsert)
    #   print(f'Uploaded Batches: {i} to {i_end}')

    # Save enriched segments to S3 (one file per video_id)
    for video_id, segments in segments_by_video.items():
        # Add embeddings to all segments (if not already present)
        for segment in segments:
            if 'embedding' not in segment and 'vectors' in segment:
                segment['embedding'] = segment['vectors']
        s3_key = f"transcripts/{video_id}.json"
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(segments),
                ContentType='application/json'
            )
            print(f"Uploaded enriched transcript to s3://{S3_BUCKET_NAME}/{s3_key}")
        except Exception as e:
            print(f"Error uploading enriched transcript to S3 for {video_id}: {e}")

def sanitize_index_name(url):
    """Convert a URL into a valid Pinecone index name."""
    # Remove common URL parts
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    # Split into domain and path, keep the path for YouTube URLs
    parts = url.split('/', 1)
    if len(parts) > 1 and 'youtube.com' in parts[0]:
        url = parts[1].replace('/', '-')
    else:
        url = parts[0]
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
            customer_key = None
            channel_url = "demo"
            pdfs_by_video = {}
        else:
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                customer_key = request.form.get('customer_key')
                channel_url = request.form.get('channel_url')
                # Parse pdfs[VIDEO_ID] fields
                pdfs_by_video = {}
                for key in request.files:
                    if key.startswith('pdfs[') and key.endswith(']'):
                        video_id = key[5:-1]
                        pdfs_by_video.setdefault(video_id, []).append(request.files[key])
            else:
                data = request.get_json()
                customer_key = data.get('customer_key')
                channel_url = data.get('channel_url')
                # For JSON, expect { video_id: [pdf_url, ...] }
                pdfs_by_video = data.get('pdfs_by_video', {})
            if not customer_key or not channel_url:
                return jsonify({"error": "customer_key and channel_url are required"}), 400
            if not is_valid_customer_key(customer_key, channel_url):
                return jsonify({"error": "Unauthorized: invalid customer_key for channel_url"}), 401
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
        def process_videos_and_pdfs():
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
                # --- PDF PROCESSING ---
                for video_id in new_videos:
                    video_id = video_id.split("v=")[-1] if "v=" in video_id else video_id
                    pdf_files = pdfs_by_video.get(video_id, [])
                    # If JSON, pdf_files are URLs (now implemented: download and process)
                    print(f"pdf_files: {pdf_files}")
                    for pdf_file in pdf_files:
                        if isinstance(pdf_file, str):
                            pdf_url = pdf_file
                            if not pdf_url.lower().endswith('.pdf'):
                                print(f"Skipping non-PDF URL: {pdf_url}")
                                continue
                            try:
                                resp = requests.get(pdf_url)
                                if resp.status_code != 200:
                                    print(f"Failed to download PDF from {pdf_url}: {resp.status_code}")
                                    continue
                                pdf_bytes = resp.content
                                pdf_name = pdf_url.split('/')[-1]
                            except Exception as e:
                                print(f"Error downloading PDF from {pdf_url}: {e}")
                                continue
                        else:
                            pdf_name = pdf_file.filename
                            pdf_bytes = pdf_file.read()
                        pdf_id = hashlib.sha256(pdf_bytes).hexdigest()[:16]
                        s3_pdf_key = f"pdfs/{video_id}/{pdf_id}.pdf"
                        # Upload original PDF to S3
                        try:
                            s3_client.put_object(
                                Bucket=S3_BUCKET_NAME,
                                Key=s3_pdf_key,
                                Body=pdf_bytes,
                                ContentType='application/pdf'
                            )
                            print(f"Uploaded PDF to s3://{S3_BUCKET_NAME}/{s3_pdf_key}")
                        except Exception as e:
                            print(f"Error uploading PDF to S3: {e}")
                            continue
                        # Extract and segment PDF
                        pdf_segments = []
                        try:
                            pages = extract_pdf_text_pymupdf(pdf_bytes)
                            for page_num, text in enumerate(pages, 1):
                                if not text.strip():
                                    continue
                                chunk_size = 512
                                chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                                for chunk_idx, chunk in enumerate(chunks):
                                    print(f"PDF segment (page {page_num}, chunk {chunk_idx}): {chunk[:100]}")
                                    seg_id = f"{pdf_id}-p{page_num}-c{chunk_idx}"
                                    pdf_segments.append({
                                        "id": seg_id,
                                        "source_type": "pdf",
                                        "pdf_id": pdf_id,
                                        "pdf_name": pdf_name,
                                        "video_id": video_id,
                                        "page_number": page_num,
                                        "chunk_number": chunk_idx,
                                        "text": chunk,
                                        "citation": f"PDF: {pdf_name}, page {page_num}",
                                    })
                        except Exception as e:
                            print(f"Error extracting text from PDF: {e}")
                            continue
                        # Encode PDF segments
                        if pdf_segments:
                            for batch_start in range(0, len(pdf_segments), 64):
                                batch = pdf_segments[batch_start:batch_start+64]
                                batch_text = [seg['text'] for seg in batch]
                                batch_vectors = handler.sentence_transformer_model.encode(batch_text).tolist()
                                for i, seg in enumerate(batch):
                                    seg['embedding'] = batch_vectors[i]
                            # Upsert to Pinecone
                            to_upsert = [
                                (seg['id'], seg['embedding'], {
                                    'source_type': seg['source_type'],
                                    'pdf_id': seg['pdf_id'],
                                    'pdf_name': seg['pdf_name'],
                                    'video_id': seg['video_id'],
                                    'page_number': seg['page_number'],
                                    'chunk_number': seg['chunk_number'],
                                    'citation': seg['citation'],
                                    'text': seg['text'],
                                })
                                for seg in pdf_segments
                            ]
                            pinecone_index.upsert(to_upsert)
                            # Store enriched PDF segments in S3
                            s3_pdf_seg_key = f"pdf_segments/{video_id}/{pdf_id}.json"
                            try:
                                s3_client.put_object(
                                    Bucket=S3_BUCKET_NAME,
                                    Key=s3_pdf_seg_key,
                                    Body=json.dumps(pdf_segments),
                                    ContentType='application/json'
                                )
                                print(f"Uploaded PDF segments to s3://{S3_BUCKET_NAME}/{s3_pdf_seg_key}")
                            except Exception as e:
                                print(f"Error uploading PDF segments to S3: {e}")
                # --- END PDF PROCESSING ---
                # Generate and upload summary for each video
                for video_id in new_videos:
                    generate_and_upload_summary(video_id)
                # Update processed videos
                PROCESSED_VIDEOS.update(new_videos)
                print(f"Processed {len(new_videos)} new video(s). Model retrained. Total time: {time.time() - process_start:.2f} seconds")
            except Exception as e:
                print(f"Error in background processing: {str(e)}")
                import traceback
                print(f"Traceback in background: {traceback.format_exc()}")
        import io
        Thread(target=process_videos_and_pdfs).start()
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
  # Query with top_k=10 since we only need a maximum of 10 results after filtering
  results = pinecone_index.query(vector=encoded_query, top_k=10, include_metadata=True)
  # Filter matches with score >= 22.5
  filtered_matches = [match for match in results.get('matches', []) if match.get('score', 0.0) >= 22.5]
  # Sort by score in descending order
  filtered_matches.sort(key=lambda x: x.get('score', 0.0), reverse=True)
  # Return the filtered and sorted results (will be empty if no matches meet the threshold)
  results['matches'] = filtered_matches
  return results

@app.route('/api/query', methods=['GET'])
def query_model(demo_phrase = None, demo_url = None):
    try:
        if demo_phrase and demo_url:
            query_phrase = demo_phrase
            channel_url = demo_url
            customer_key = None
        else:
            query_phrase = request.args.get('query_phrase')
            channel_url = request.args.get('channel_url')
            customer_key = request.args.get('customer_key')
            if not customer_key or not channel_url:
                return jsonify({"error": "customer_key and channel_url are required"}), 400
            if not is_valid_customer_key(customer_key, channel_url):
                return jsonify({"error": "Unauthorized: invalid customer_key for channel_url"}), 401
            if not query_phrase:
                return jsonify({"error": "Query phrase is required"}), 400
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
                    # --- Citation logic for PDF and video ---
                    meta = cleaned_match.get('metadata', {})
                    if meta.get('source_type') == 'pdf':
                        pdf_name = meta.get('pdf_name', '')
                        page_number = meta.get('page_number', '')
                        cleaned_match['citation'] = f"PDF: {pdf_name}, page {page_number}"
                    elif 'url' in meta:
                        url = meta['url']
                        if '&t=' in url:
                            try:
                                timestamp_str = url.split('&t=')[1]
                                timestamp_float = float(timestamp_str)
                                rounded_timestamp = int(timestamp_float)
                                cleaned_match['metadata']['url'] = url.split('&t=')[0] + '&t=' + str(rounded_timestamp)
                                cleaned_match['citation'] = cleaned_match['metadata']['url']
                            except (ValueError, IndexError):
                                app.logger.debug(f"Failed to parse or round timestamp in URL: {url}")
                                cleaned_match['citation'] = url
                        else:
                            cleaned_match['citation'] = url
                    else:
                        cleaned_match['citation'] = ""
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
                # --- Citation logic for PDF and video ---
                meta = cleaned_match.get('metadata', {})
                if meta.get('source_type') == 'pdf':
                    pdf_name = meta.get('pdf_name', '')
                    page_number = meta.get('page_number', '')
                    cleaned_match['citation'] = f"PDF: {pdf_name}, page {page_number}"
                elif 'url' in meta:
                    url = meta['url']
                    if '&t=' in url:
                        try:
                            timestamp_str = url.split('&t=')[1]
                            timestamp_float = float(timestamp_str)
                            rounded_timestamp = int(timestamp_float)
                            cleaned_match['metadata']['url'] = url.split('&t=')[0] + '&t=' + str(rounded_timestamp)
                            cleaned_match['citation'] = cleaned_match['metadata']['url']
                        except (ValueError, IndexError):
                            app.logger.debug(f"Failed to parse or round timestamp in URL: {url}")
                            cleaned_match['citation'] = url
                    else:
                        cleaned_match['citation'] = url
                else:
                    cleaned_match['citation'] = ""
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
    # Ensure CustomerKeys table exists too
    ensure_customer_keys_table_exists()

@app.route('/api/train_video', methods=['POST'])
def train_single_video():
    try:
        start_time = time.time()
        print(f"Starting train_single_video at {datetime.now()}")
        # Accept both JSON and multipart/form-data
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            customer_key = request.form.get('customer_key')
            channel_url = request.form.get('channel_url')
            video_url = request.form.get('video_url')
            pdf_files = request.files.getlist('pdfs')  # List of FileStorage
        else:
            data = request.get_json()
            customer_key = data.get('customer_key')
            channel_url = data.get('channel_url')
            video_url = data.get('video_url')
            pdf_files = data.get('pdf_files', [])  # <-- FIX: get from JSON!
        if not customer_key or not channel_url or not video_url:
            return jsonify({"error": "customer_key, channel_url, and video_url are required"}), 400
        if not is_valid_customer_key(customer_key, channel_url):
            return jsonify({"error": "Unauthorized: invalid customer_key for channel_url"}), 401
        print(f"Processing video {video_url} for channel {channel_url} at {time.time() - start_time:.2f} seconds")
        # Sanitize the channel URL for use as index name
        index_id = sanitize_index_name(channel_url)
        print(f"Using Pinecone index name: {index_id} at {time.time() - start_time:.2f} seconds")
        # Extract video ID from URL if necessary
        video_id = video_url.split("v=")[-1] if "v=" in video_url else video_url
        # Check if video is already processed
        if video_id in PROCESSED_VIDEOS:
            print(f"Video {video_id} already processed, returning at {time.time() - start_time:.2f} seconds")
            return jsonify({"message": "Video already processed"}), 200
        # Process the video and PDFs asynchronously
        print(f"Starting processing for video {video_id} at {time.time() - start_time:.2f} seconds")
        handler = EndpointHandler(path="")
        payload = {"video_urls": [video_url]}
        def process_single_video_and_pdfs(pdf_files=pdf_files):
            try:
                process_start = time.time()
                print(f"Background thread for single video started at {datetime.now()}")
                processed_data = handler(payload)
                print(f"Video processed in background at {time.time() - process_start:.2f} seconds")
                # Pinecone integration
                dimensions = handler.sentence_transformer_model.get_sentence_embedding_dimension()
                PINECONE_API_KEY = get_pinecone_api_key()
                pc = Pinecone(api_key=PINECONE_API_KEY)
                existing_indexes = pc.list_indexes()
                if index_id not in existing_indexes:
                    print(f"Index {index_id} does not exist. Creating new index at {time.time() - process_start:.2f} seconds")
                    try:
                        pc.create_index(
                            name=index_id,
                            dimension=dimensions,
                            metric="dotproduct",
                            spec=ServerlessSpec(cloud="aws", region="us-east-1")
                        )
                        print(f"Successfully created Pinecone index: {index_id} at {time.time() - process_start:.2f} seconds")
                    except Exception as e:
                        print(f"Failed to create Pinecone index {index_id}: {str(e)} at {time.time() - process_start:.2f} seconds")
                        if 'ALREADY_EXISTS' in str(e) or '409' in str(e):
                            print(f"Index {index_id} already exists. Proceeding with existing index at {time.time() - process_start:.2f} seconds")
                        else:
                            print(f"WARNING: Could not create index {index_id}. Proceeding may fail. at {time.time() - process_start:.2f} seconds")
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
                # --- PDF PROCESSING ---
                print(f"PDF files to process: {pdf_files}")
                for pdf_file in pdf_files:
                    if isinstance(pdf_file, str):
                        pdf_url = pdf_file
                        if not pdf_url.lower().endswith('.pdf'):
                            print(f"Skipping non-PDF URL: {pdf_url}")
                            continue
                        try:
                            resp = requests.get(pdf_url)
                            if resp.status_code != 200:
                                print(f"Failed to download PDF from {pdf_url}: {resp.status_code}")
                                continue
                            pdf_bytes = resp.content
                            pdf_name = pdf_url.split('/')[-1]
                        except Exception as e:
                            print(f"Error downloading PDF from {pdf_url}: {e}")
                            continue
                    else:
                        pdf_name = pdf_file.filename
                        pdf_bytes = pdf_file.read()
                    pdf_id = hashlib.sha256(pdf_bytes).hexdigest()[:16]
                    s3_pdf_key = f"pdfs/{video_id}/{pdf_id}.pdf"
                    # Upload original PDF to S3
                    try:
                        s3_client.put_object(
                            Bucket=S3_BUCKET_NAME,
                            Key=s3_pdf_key,
                            Body=pdf_bytes,
                            ContentType='application/pdf'
                        )
                        print(f"Uploaded PDF to s3://{S3_BUCKET_NAME}/{s3_pdf_key}")
                    except Exception as e:
                        print(f"Error uploading PDF to S3: {e}")
                        continue
                    # Extract and segment PDF
                    pdf_segments = []
                    try:
                        pages = extract_pdf_text_pymupdf(pdf_bytes)
                        for page_num, text in enumerate(pages, 1):
                            if not text.strip():
                                continue
                            chunk_size = 512
                            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                            for chunk_idx, chunk in enumerate(chunks):
                                print(f"PDF segment (page {page_num}, chunk {chunk_idx}): {chunk[:100]}")
                                seg_id = f"{pdf_id}-p{page_num}-c{chunk_idx}"
                                pdf_segments.append({
                                    "id": seg_id,
                                    "source_type": "pdf",
                                    "pdf_id": pdf_id,
                                    "pdf_name": pdf_name,
                                    "video_id": video_id,
                                    "page_number": page_num,
                                    "chunk_number": chunk_idx,
                                    "text": chunk,
                                    "citation": f"PDF: {pdf_name}, page {page_num}",
                                })
                    except Exception as e:
                        print(f"Error extracting text from PDF: {e}")
                        continue
                    # Encode PDF segments
                    if pdf_segments:
                        for batch_start in range(0, len(pdf_segments), 64):
                            batch = pdf_segments[batch_start:batch_start+64]
                            batch_text = [seg['text'] for seg in batch]
                            batch_vectors = handler.sentence_transformer_model.encode(batch_text).tolist()
                            for i, seg in enumerate(batch):
                                seg['embedding'] = batch_vectors[i]
                        # Upsert to Pinecone
                        to_upsert = [
                            (seg['id'], seg['embedding'], {
                                'source_type': seg['source_type'],
                                'pdf_id': seg['pdf_id'],
                                'pdf_name': seg['pdf_name'],
                                'video_id': seg['video_id'],
                                'page_number': seg['page_number'],
                                'chunk_number': seg['chunk_number'],
                                'citation': seg['citation'],
                                'text': seg['text'],
                            })
                            for seg in pdf_segments
                        ]
                        pinecone_index.upsert(to_upsert)
                        # Store enriched PDF segments in S3
                        s3_pdf_seg_key = f"pdf_segments/{video_id}/{pdf_id}.json"
                        try:
                            s3_client.put_object(
                                Bucket=S3_BUCKET_NAME,
                                Key=s3_pdf_seg_key,
                                Body=json.dumps(pdf_segments),
                                ContentType='application/json'
                            )
                            print(f"Uploaded PDF segments to s3://{S3_BUCKET_NAME}/{s3_pdf_seg_key}")
                        except Exception as e:
                            print(f"Error uploading PDF segments to S3: {e}")
                # --- END PDF PROCESSING ---
                generate_and_upload_summary(video_id)
                # Update processed videos
                PROCESSED_VIDEOS.add(video_id)
                print(f"Processed video {video_id}. Total time: {time.time() - process_start:.2f} seconds")
            except Exception as e:
                print(f"Error in background processing of single video: {str(e)}")
                import traceback
                print(f"Traceback in background: {traceback.format_exc()}")
        import io
        Thread(target=process_single_video_and_pdfs).start()
        print(f"Response returned at {time.time() - start_time:.2f} seconds")
        return jsonify({
            "message": f"Processing started for video {video_id}."
        })
    except Exception as e:
        print(f"Error in /train_video endpoint: {str(e)} at {time.time() - start_time if 'start_time' in locals() else 0:.2f} seconds")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/llm_chat', methods=['POST'])
def llm_chat():
    try:
        data = request.get_json()
        question = data.get('question')
        video_id = data.get('video_id')
        if not question or not video_id:
            return jsonify({"error": "Missing question or video_id"}), 400

        # Download enriched transcript from S3
        s3_key = f"transcripts/{video_id}.json"
        transcript_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        transcript_data = json.loads(transcript_obj['Body'].read().decode('utf-8'))

        # Use precomputed embeddings for each segment
        model_name = "multi-qa-mpnet-base-dot-v1"
        sentence_transformer_model = SentenceTransformer(model_name)
        question_embedding = sentence_transformer_model.encode([question])[0]

        # Compute similarity for each segment using precomputed embedding
        best_score = float('-inf')
        best_segment = None
        for segment in transcript_data:
            segment_text = segment.get('text', '')
            segment_embedding = segment.get('embedding') or segment.get('vectors')
            if not segment_text or not segment_embedding:
                continue
            # Use dot product (since Pinecone index uses dotproduct)
            score = sum(q * s for q, s in zip(question_embedding, segment_embedding))
            if score > best_score:
                best_score = score
                best_segment = segment

        # Compose context (truncate if too long for LLM)
        transcript_text = " ".join([line['text'] for line in transcript_data])
        max_context = 3000  # chars, adjust as needed
        if len(transcript_text) > max_context:
            transcript_text = transcript_text[:max_context] + "..."

        prompt = (
            f"You are an expert video assistant. "
            f"Given the following transcript, answer the user's question as helpfully as possible.\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )

        # Use new OpenAI API (openai>=1.0.0)
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()

        # Only provide the video link if the best score exceeds the threshold
        THRESHOLD = 20  # Adjust as needed
        timestamp = None
        if best_segment and best_score > THRESHOLD:
            timestamp = int(best_segment.get('start', 0))

        return jsonify({
            "answer": answer,
            "timestamp": timestamp
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/summary', methods=['GET'])
def get_video_summary():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "Missing video_id"}), 400
    s3_key = f"summaries/{video_id}.json"
    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        summary_data = json.loads(obj['Body'].read().decode('utf-8'))
        return jsonify(summary_data)
    except Exception as e:
        return jsonify({"error": f"Summary not found for video {video_id}: {str(e)}"}), 404

def generate_and_upload_summary(video_id):
    try:
        s3_key = f"transcripts/{video_id}.json"
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        transcript = json.loads(obj["Body"].read().decode("utf-8"))
        transcript_text = " ".join([seg["text"] for seg in transcript])
        max_context = 3000
        if len(transcript_text) > max_context:
            transcript_text = transcript_text[:max_context] + "..."
        prompt = (
            "Summarize the following YouTube video transcript in a concise paragraph for a general audience:\n\n"
            f"{transcript_text}\n\nSummary:"
        )
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.2,
        )
        summary = response.choices[0].message.content.strip()
        summary_obj = {"video_id": video_id, "summary": summary}
        summary_key = f"summaries/{video_id}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=summary_key,
            Body=json.dumps(summary_obj),
            ContentType="application/json"
        )
        print(f"Summary uploaded to s3://{S3_BUCKET_NAME}/{summary_key}")
    except Exception as e:
        print(f"Error generating/uploading summary for {video_id}: {e}")

def extract_pdf_text_pymupdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_pages = []
    for page in doc:
        text = page.get_text()
        all_pages.append(text)
    return all_pages  # List of strings, one per page

def print_index_info(pc, index_id):
    try:
        index_info = pc.describe_index(index_id)
        print(f"Index {index_id} info: dimension={index_info.dimension}, metric={index_info.metric}")
    except Exception as e:
        print(f"Could not retrieve index info for {index_id}: {e}")

if __name__ == '__main__':
    ensure_table_exists()
    app.run(host='0.0.0.0', port=5000, debug=True)