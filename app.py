from typing import Dict

from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import whisper
import torch
from pytubefix import YouTube
import time
from getpass import getpass
from flask import Flask, request, jsonify
import scrapetube
import boto3
import pinecone  # !pip install pinecone-client
import os
from pinecone import Pinecone, ServerlessSpec
import ssl
import json
from botocore.exceptions import NoCredentialsError
import pickle

app = Flask(__name__)
# Mock database to store processed videos (use a database like DynamoDB in production)
PROCESSED_VIDEOS = set()

# S3 bucket configuration
S3_BUCKET_NAME = "video-search-training-bucket"
S3_REGION = "us-east-2"

def get_aws_credentials():
    client = boto3.client('secretsmanager', region_name='us-east-2')
    secret_name = "my-aws-credentials-secret"

    response = client.get_secret_value(SecretId=secret_name)
    secrets = json.loads(response['SecretString'])
    return secrets['aws_access_key_id'], secrets['aws_secret_access_key']

def get_pinecone_api_key():
    client = boto3.client('secretsmanager', region_name='us-east-2')
    secret_name = "pinecone-secret"

    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response['SecretString'])
    return secret['pinecone_api_key']

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=get_aws_credentials()[0],
    aws_secret_access_key=get_aws_credentials()[1],
    region_name=S3_REGION
)

def upload_to_s3(file_path, s3_key=None):
    """Uploads a file to the specified S3 bucket."""
    if not s3_key:
        # Derive the S3 key from the local file name
        s3_key = os.path.basename(file_path)
    try:
        s3_client.upload_file(file_path, S3_BUCKET_NAME, s3_key)
        print(f"Uploaded {file_path} to {S3_BUCKET_NAME}/{s3_key}")
    except NoCredentialsError:
        print("Credentials not available.")
    except Exception as e:
        print(f"Error uploading to S3: {e}")

def download_from_s3(s3_key, local_path=None):
    """Downloads a file from S3 to the specified local path."""
    if not local_path:
        # Derive the local file name from the S3 key
        local_path = os.path.basename(s3_key)
    try:
        s3_client.download_file(S3_BUCKET_NAME, s3_key, local_path)
        print(f"Downloaded {S3_BUCKET_NAME}/{s3_key} to {local_path}")
    except Exception as e:
        print(f"Error downloading from S3: {e}")

# to bypass SSL problem on local run
ssl._create_default_https_context = ssl._create_unverified_context

# gather all YouTube video links from channel
def fetch_all_videos_yt(channel_url):
    # TODO
    videos = scrapetube.get_channel(channel_url=channel_url)
    # need to preface each with 'https://www.youtube.com/watch?v=' 
    return [video['videoId'] for video in videos]

# print(fetch_all_videos_yt("https://www.youtube.com/@MusicForTheSoul11/"))

class EndpointHandler():
    def __init__(self, path=""):
        # load the model
        WHISPER_MODEL_NAME = "tiny.en"
        SENTENCE_TRANSFORMER_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f'whisper will use: {self.device}')

        # Load Whisper Model
        whisper_path = os.path.join(path, "whisper_model.pt")
        if os.path.exists(whisper_path):
            print("Loading Whisper model from S3...")
            download_from_s3("models/whisper_model.pt", whisper_path)
            self.whisper_model = whisper.load_model(whisper_path).to(self.device)
        else:
            print("Loading Whisper model locally...")
            self.whisper_model = whisper.load_model(WHISPER_MODEL_NAME).to(self.device)
            self.whisper_model.save(whisper_path)
            upload_to_s3(whisper_path, "models/whisper_model.pt")

        transformer_path = os.path.join(path, "sentence_transformer")
        if os.path.exists(transformer_path):
            print("Loading SentenceTransformer model from S3...")
            download_from_s3("models/sentence_transformer", transformer_path)
        else:
            print("Loading SentenceTransformer model locally...")
            self.sentence_transformer_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)
            self.sentence_transformer_model.save(transformer_path)
            upload_to_s3(transformer_path, "models/sentence_transformer")

    def __call__(self, data: Dict[str, str]) -> Dict:
        """
        Args:
            data (:obj:):
                includes the URL to video for transcription
        Return:
            A :obj:`dict`:. transcribed dict
        """
        # process input
        # print('data', data)

        # if "inputs" not in data:
        #     raise Exception(f"data is missing 'inputs' key which  EndpointHandler expects. Received: {data}"
        #                     f" See: https://huggingface.co/docs/inference-endpoints/guides/custom_handler#2-create-endpointhandler-cp")
        video_urls = data.pop("video_urls", None)
        query = data.pop("query", None)
        trying_live = data.pop("trying_live", None)
        encoded_segments = {}
        if video_urls:
          videos_with_transcript = [self.transcribe_video(video_url) for video_url in video_urls]
          encode_transcript = data.pop("encode_transcript", True)
          if encode_transcript:
              encoded_segments = self.combine_transcripts(videos_with_transcript)
              if trying_live:
                return {
                    "encoded_segments": encoded_segments
                }
              encoded_segments = {
                  "encoded_segments": self.encode_sentences(encoded_segments)
              }
          return {
              **videos_with_transcript,
              **encoded_segments
          }
        elif query:
            query = [{"text": query, "id": ""}]
            encoded_segments = self.encode_sentences(query)

            return {
                "encoded_segments": encoded_segments
            }

    def transcribe_video(self, video_url):
        decode_options = {
            # Set language to None to support multilingual,
            # but it will take longer to process while it detects the language.
            # Realized this by running in verbose mode and seeing how much time
            # was spent on the decoding language step
            "language": "en",
            "verbose": True
        }
        yt = YouTube(video_url)
        video_info = {
            'id': yt.video_id,
            'thumbnail': yt.thumbnail_url,
            'title': yt.title,
            'views': yt.views,
            'length': yt.length,
            # Althhough, this might seem redundant since we already have id
            # but it allows the link to the video be accessed in 1-click in the API response
            'url': f"https://www.youtube.com/watch?v={yt.video_id}"
        }
        stream = yt.streams.filter(only_audio=True)[0]
        path_to_audio = f"{yt.video_id}.mp3"
        stream.download(filename=path_to_audio)
        t0 = time.time()
        transcript = self.whisper_model.transcribe(path_to_audio, **decode_options)
        t1 = time.time()
        for segment in transcript['segments']:
            # Remove the tokens array, it makes the response too verbose
            segment.pop('tokens', None)

        total = t1 - t0
        print(f'Finished transcription in {total} seconds')

        # postprocess the prediction
        return {"transcript": transcript, 'video': video_info}

    def transcribe_video(self, video_url):
        decode_options = {"language": "en", "verbose": True}
        yt = YouTube(video_url)
        video_info = {
            'id': yt.video_id,
            'thumbnail': yt.thumbnail_url,
            'title': yt.title,
            'views': yt.views,
            'length': yt.length,
            'url': f"https://www.youtube.com/watch?v={yt.video_id}"
        }
        stream = yt.streams.filter(only_audio=True)[0]
        path_to_audio = f"{yt.video_id}.mp3"
        stream.download(filename=path_to_audio)
        transcript = self.whisper_model.transcribe(path_to_audio, **decode_options)
        for segment in transcript['segments']:
            segment.pop('tokens', None)
        return {"transcript": transcript, 'video': video_info}
    
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

    @staticmethod
    def combine_transcripts(videos, window=6, stride=3):
        """

        :param video:
        :param window: number of sentences to combine
        :param stride: number of sentences to 'stride' over, used to create overlap
        :return:
        """
        new_transcript_segments = []

        for video in videos:
          video_info = video['video']
          transcript_segments = video['transcript']['segments']
          for i in tqdm(range(0, len(transcript_segments), stride)):
              i_end = min(len(transcript_segments), i + window)
              text = ' '.join(transcript['text']
                              for transcript in
                              transcript_segments[i:i_end])
              # TODO: Should int (float to seconds) conversion happen at the API level?
              start = int(transcript_segments[i]['start'])
              end = int(transcript_segments[i]['end'])
              new_transcript_segments.append({
                  **video_info,
                  **{
                      'start': start,
                      'end': end,
                      'title': video_info['title'],
                      'text': text,
                      'id': f"{video_info['id']}-t{start}",
                      'url': f"https://youtu.be/{video_info['id']}?t={start}",
                      'video_id': video_info['id'],
                  }
              })
        return new_transcript_segments

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
def train_model():
    try:
        data = request.get_json()
        channel_url = data.get('channel_url')
        if channel_url == "demo":
            video_urls = ["https://www.youtube.com/watch?v=w4CMaKF_IXI", "https://www.youtube.com/watch?v=PQtMTPhmQwM"]
        else:
            video_urls = fetch_all_videos_yt(channel_url)
        # filter out already processed videos
        new_videos = [url for url in video_urls if url not in PROCESSED_VIDEOS]
        if not new_videos:
            return jsonify({"message": "No new videos to process"}), 200
        # Process each video
        handler = EndpointHandler(path="")
        payload = {"video_urls": new_videos, "trying_live": True}
        processed_data = handler(payload)

        # Pinecone integration
        sentence_transformer_model = handler.sentence_transformer_model
        model_path = "trained_model_" + channel_url
        sentence_transformer_model.save(model_path)
        upload_to_s3(model_path, "models/trained_model.zip")
        
        dimensions = sentence_transformer_model.get_sentence_embedding_dimension()
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
                spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        pinecone_index = pc.Index(index_id)
        # pinecone_index.describe_index_stats()
        upload_transcripts_to_vector_db(processed_data.get('encoded_segments'), pinecone_index, sentence_transformer_model)

        # Update processed videos
        PROCESSED_VIDEOS.update(new_videos)
        return jsonify({
            "message": f"Processed {len(new_videos)} new video(s). Model retrained."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def query_pinecone_model(query, pinecone_index, sentence_transformer_model):
  encoded_query = sentence_transformer_model.encode(query).tolist()
  # print(encoded_query)
  return pinecone_index.query(vector=encoded_query, top_k=5,
                              include_metadata=True)

@app.route('/query', methods=['GET'])
def query_model():
    try:
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
    app.run(host='0.0.0.0', port=5000)
# train_model(channel_url="demo")
# print(query("maple syrup", channel_url="demo"))
# print("BREAK")
# print(query("crispy exterior", channel_url="demo"))






