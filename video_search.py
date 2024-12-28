from typing import Dict

from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import whisper
import torch
from pytubefix import YouTube
import time
from getpass import getpass
import fetch_helpers

# need to not have this publicly exposed
PINECONE_API_KEY = "FAKE_KEY"

import pinecone  # !pip install pinecone-client
# import os
from pinecone import Pinecone, ServerlessSpec

# to bypass SSL problem on local run
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

class EndpointHandler():
    def __init__(self, path=""):
        # load the model
        WHISPER_MODEL_NAME = "tiny.en"
        SENTENCE_TRANSFORMER_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f'whisper will use: {device}')

        t0 = time.time()
        self.whisper_model = whisper.load_model(WHISPER_MODEL_NAME).to(device)
        t1 = time.time()

        total = t1 - t0
        print(f'Finished loading whisper_model in {total} seconds')

        t0 = time.time()
        self.sentence_transformer_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL_NAME)
        t1 = time.time()

        total = t1 - t0
        print(f'Finished loading sentence_transformer_model in {total} seconds')

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

def train_model(channel_url, model_id = "multi-qa-mpnet-base-dot-v1"):
    if channel_url == "demo":
        video_urls = ["https://www.youtube.com/watch?v=w4CMaKF_IXI", "https://www.youtube.com/watch?v=PQtMTPhmQwM"]
    else:
        video_urls = fetch_helpers.fetch_all_videos_yt(channel_url)
    # check if change (set comparison)
    # test the handler
    handler = EndpointHandler(path="")
    payload = {"video_urls": video_urls, "trying_live": True}
    payload_pred = handler(payload)
    sentence_transformer_model = SentenceTransformer(model_id)
    dimensions = sentence_transformer_model.get_sentence_embedding_dimension()
    index_id = "search-" + channel_url
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
    upload_transcripts_to_vector_db(payload_pred.get('encoded_segments'), pinecone_index, sentence_transformer_model)

def query_model(query, pinecone_index, sentence_transformer_model):
  encoded_query = sentence_transformer_model.encode(query).tolist()
  # print(encoded_query)
  return pinecone_index.query(vector=encoded_query, top_k=5,
                              include_metadata=True)

def query(query_phrase, channel_url, model_id = "multi-qa-mpnet-base-dot-v1"):
    index_id = "search-" + channel_url
    pc = Pinecone(
        api_key=PINECONE_API_KEY
    )
    pinecone_index = pc.Index(index_id)
    sentence_transformer_model = SentenceTransformer(model_id)
    results = query_model(query_phrase, pinecone_index, sentence_transformer_model)
    return results['matches']


# train_model(channel_url="demo")
# print(query("maple syrup", channel_url="demo"))
# print("BREAK")
# print(query("crispy exterior", channel_url="demo"))






